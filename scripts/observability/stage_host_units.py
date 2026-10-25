"""Stage owner-bound units, exact engine pin changes and rollback; never install them."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_private(path):
    try:
        return path.read_bytes()
    except PermissionError:
        return subprocess.check_output(["sudo", "-n", "cat", str(path)], timeout=10)


def quote(value):
    text = str(value)
    if any(ord(c) < 32 for c in text):
        raise ValueError("Invalid unit value")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def unit_path(value):
    text = str(value)
    if not text.startswith("/") or not re.fullmatch(r"[A-Za-z0-9_./-]+", text):
        raise ValueError("Unsupported unit path")
    return text


def write(path, data):
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    path.chmod(0o600)


def unit(
    description, user, command, *, cwd=None, environment=(), envfile=None, writable=(), after=()
):
    lines = [
        "[Unit]",
        "Description=" + description,
        "After=" + " ".join(("network-online.target", *after)),
        "",
        "[Service]",
        "Type=simple",
        "User=" + user,
        "UMask=0077",
    ]
    if cwd:
        lines.append("WorkingDirectory=" + unit_path(cwd))
    for setting in environment:
        lines.append("Environment=" + quote(setting))
    if envfile:
        lines.append("EnvironmentFile=" + unit_path(envfile))
    lines.extend(
        [
            "ExecStart=" + " ".join(quote(s) for s in command),
            "Restart=on-failure",
            "RestartSec=10",
            "NoNewPrivileges=true",
            "PrivateTmp=true",
            "ProtectSystem=strict",
            "ProtectHome=read-only",
        ]
    )
    for path in writable:
        lines.append("ReadWritePaths=" + quote(path))
    lines.extend(["", "[Install]", "WantedBy=multi-user.target", ""])
    return "\n".join(lines)


def stage(bindings, activation, proofs, output):
    if output.exists() or not output.is_absolute():
        raise ValueError("Stage output must be a new absolute private directory")
    output.mkdir(parents=True, mode=0o700)
    spec = importlib.util.spec_from_file_location(
        "observability_engine_adopter", Path(__file__).with_name("adopt_engine.py")
    )
    adopter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adopter)
    engines = []
    installs = []
    proof_paths = json.loads(
        subprocess.check_output(
            [
                "sudo",
                "-n",
                "python3",
                "-c",
                "import json,sys; from pathlib import Path; print(json.dumps([str(p) for p in sorted(Path(sys.argv[1]).glob('*/proof.json'))]))",
                str(proofs),
            ],
            text=True,
            timeout=10,
        )
    )
    if len(proof_paths) != 6:
        raise ValueError("Expected six reviewed company engine proofs")
    for item in proof_paths:
        path = Path(item)
        proof = json.loads(read_private(path))
        row = proof["runtime"]
        uid = row["uid"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", uid):
            raise ValueError("Invalid runtime identity")
        manifest_sha = sha(
            json.dumps(proof["candidate_manifest"], sort_keys=True, separators=(",", ":")).encode()
        )
        root = Path("/home/mrcalld/releases") / (
            "operator-observability-" + sha(uid.encode())[:12] + "-" + manifest_sha[:12]
        )
        original = read_private(Path(row["winning_pin"]))
        if sha(original) != proof["winning_pin_sha256"]:
            raise ValueError("Live winning pin differs from reviewed before-image")
        rendered = adopter.render_pin(
            original, row["pythonpath"], str(root) + ":" + row["pythonpath"]
        )
        local = output / "engines" / uid
        write(local / "winning-pin.before", original)
        write(local / "winning-pin.after", rendered)
        engines.append(
            {
                "uid": uid,
                "unit": row["unit"],
                "user": row["user"],
                "interpreter": row["interpreter"],
                "source_candidate": str(path.parent),
                "final_root": str(root),
                "candidate_manifest_sha256": manifest_sha,
                "old_pythonpath": row["pythonpath"],
                "new_pythonpath": str(root) + ":" + row["pythonpath"],
                "winning_pin": row["winning_pin"],
                "before_sha256": sha(original),
                "after_sha256": sha(rendered),
                "pin_mode": proof["winning_pin_mode"],
                "staged_before": str(local / "winning-pin.before"),
                "staged_after": str(local / "winning-pin.after"),
                "rollback": "restore exact staged_before bytes/mode, then restart this unit only",
            }
        )
    profiles = []
    routes = []
    for profile in bindings["profiles"]:
        role, uid = profile["id"], profile["uid"]
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", role):
            raise ValueError("Invalid role")
        engine = next(row for row in engines if row["uid"] == uid)
        root = Path(profile["state_dir"]) / "observability"
        deployment = root / "deployment"
        source = activation / role
        local = output / "profiles" / role
        for name in ("primary.json", "monitor.json", "desktop.env"):
            write(local / name, read_private(source / name))
            installs.append(
                {
                    "source": str(local / name),
                    "destination": str(deployment / name),
                    "owner": "mal",
                    "mode": "0600",
                }
            )
        env = read_private(source / "desktop.env").decode()
        token_lines = [
            line for line in env.splitlines() if line.startswith("OPERATOR_READER_TOKEN=")
        ]
        if len(token_lines) != 1 or not re.fullmatch(
            r"OPERATOR_READER_TOKEN=[A-Za-z0-9_-]{32,256}", token_lines[0]
        ):
            raise ValueError("Invalid private reader credential reference")
        write(local / "reader.env", token_lines[0] + "\n")
        reader_env = Path("/etc/operator-observability") / (role + "-reader.env")
        installs.append(
            {
                "source": str(local / "reader.env"),
                "destination": str(reader_env),
                "owner": engine["user"],
                "mode": "0600",
            }
        )
        smtp = "operator-owner-notice-" + role + ".service"
        monitor = "operator-evidence-monitor-" + role + ".service"
        reader = "operator-log-reader-" + role + ".service"
        python = str(Path(profile["repo"]) / ".venv/bin/python")
        common = dict(
            user="mal",
            cwd=profile["repo"],
            envfile=deployment / "desktop.env",
            writable=(root,),
            environment=("PYTHONDONTWRITEBYTECODE=1", "PYTHONUNBUFFERED=1"),
        )
        definitions = {
            smtp: unit(
                "Owner-bound operational SMTP notices",
                command=(
                    python,
                    "-m",
                    "cs.monitor_notify",
                    "--config",
                    str(deployment / "primary.json"),
                ),
                **common,
            ),
            monitor: unit(
                "Independent owner-bound evidence monitor",
                command=(
                    python,
                    "-m",
                    "cs.monitor_cli",
                    "run",
                    "--config",
                    str(deployment / "monitor.json"),
                ),
                after=(smtp,),
                # Legacy retention creates locks/archives next to the cron log;
                # the observer must write this one owner-bound state directory.
                **{**common, "writable": (profile["state_dir"],)},
            ),
            reader: unit(
                "Independent owner-bound engine diagnostic reader",
                engine["user"],
                (
                    engine["interpreter"],
                    "-m",
                    "zylch.observability_reader",
                    "--profile-dir",
                    "/home/mrcalld/.zylch/profiles/" + uid,
                    "--owner-uid",
                    uid,
                    "--token-env",
                    "OPERATOR_READER_TOKEN",
                    "--port",
                    str(profile["reader_port"]),
                ),
                envfile=reader_env,
                environment=(
                    "PYTHONDONTWRITEBYTECODE=1",
                    "PYTHONUNBUFFERED=1",
                    "PYTHONPATH=" + engine["new_pythonpath"],
                    "HOME=/home/mrcalld/.zylch/profiles/" + uid,
                ),
                writable=("/home/mrcalld/.zylch/profiles/" + uid,),
            ),
        }
        for name, text in definitions.items():
            write(output / "units" / name, text)
            installs.append(
                {
                    "source": str(output / "units" / name),
                    "destination": "/etc/systemd/system/" + name,
                    "owner": "root",
                    "mode": "0644",
                }
            )
        routes.extend(
            [
                f"handle_path /_operator-diagnostics/{uid}/* {{\n    request_body {{\n        max_size 256KB\n    }}\n    reverse_proxy 127.0.0.1:{profile['reader_port']}\n}}\n",
                f"handle_path /_operator-notices/{profile['monitor_id']}/* {{\n    request_body {{\n        max_size 256KB\n    }}\n    reverse_proxy 127.0.0.1:{profile['smtp_port']}\n}}\n",
            ]
        )
        profiles.append(
            {
                "role": role,
                "uid": uid,
                "deployment": str(deployment),
                "units": {"smtp": smtp, "monitor": monitor, "reader": reader},
                "reader_env": str(reader_env),
                "writable_state": str(root),
            }
        )
    write(output / "caddy-routes.snippet", "\n".join(routes))
    summary = {
        "activated": False,
        "engines": engines,
        "profiles": profiles,
        "installs": installs,
        "caddy_snippet": str(output / "caddy-routes.snippet"),
        "source_bindings_sha256": sha(read_private(activation / "bindings.json")),
    }
    write(output / "stage.json", json.dumps(summary, indent=2) + "\n")
    artifacts = {
        str(p.relative_to(output)): {"sha256": sha(p.read_bytes()), "mode": "0600"}
        for p in output.rglob("*")
        if p.is_file()
    }
    write(output / "artifact-manifest.json", json.dumps(artifacts, indent=2) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activation", type=Path, required=True)
    parser.add_argument("--proofs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    bindings = json.loads(read_private(args.activation / "bindings.json"))
    result = stage(bindings, args.activation, args.proofs, args.output)
    print(
        json.dumps(
            {
                "activated": False,
                "engines": len(result["engines"]),
                "profiles": result["profiles"],
                "artifact_manifest": str(args.output / "artifact-manifest.json"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
