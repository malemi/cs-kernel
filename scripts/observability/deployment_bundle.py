#!/usr/bin/env python3
"""Stage private configuration and Kubernetes inputs; never activate resources."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import secrets
import sys
import time


def private_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")
    path.chmod(0o600)


def bundle(source: Path, bindings: dict, output: Path) -> dict:
    from cs.monitor_config import MonitorConfig, WatchdogConfig
    from cs.monitor_notify_config import NotifyConfig
    from cs.observability import owner_root

    if output.exists():
        raise ValueError("Private output already exists")
    profiles = bindings["profiles"]
    if not 1 <= len(profiles) <= 4:
        raise ValueError("One to four explicit owners required")
    for field in ("namespace", "node", "host", "desktop_host", "image_pull_secret"):
        if not re.fullmatch(r"[a-z0-9.-]{1,253}", bindings[field]):
            raise ValueError("Invalid fixed deployment binding")
    if not re.fullmatch(r"[A-Za-z0-9./_-]+@sha256:[a-f0-9]{64}", bindings["image"]):
        raise ValueError("Immutable reviewed runtime image required")
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    now = int(time.time())
    namespace, image = bindings["namespace"], bindings["image"]
    modules = [source / "cs" / "__init__.py", source / "cs" / "_version.py"]
    modules += sorted((source / "cs").glob("monitor*.py"))
    modules += sorted((source / "cs").glob("observability*.py"))
    code = {"cs__" + p.name: p.read_text() for p in modules}
    resources = [
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "operator-observability-source", "namespace": namespace},
            "data": code,
        }
    ]
    source_manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in modules}
    results = []
    for index, profile in enumerate(profiles):
        role, uid = profile["id"], profile["uid"]
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", role):
            raise ValueError("Invalid deployment role")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", uid):
            raise ValueError("Invalid fixed owner")
        state = Path(profile["state_dir"])
        repo = Path(profile["repo"])
        if not state.is_absolute() or not repo.is_absolute():
            raise ValueError("Absolute installed clone bindings required")
        monitor_id = secrets.token_hex(16)
        name = "operator-observability-" + role
        directory = output / role
        directory.mkdir(mode=0o700)
        remote = f"https://{bindings['host']}/_ops/{monitor_id}"
        token = {
            key: secrets.token_urlsafe(32)
            for key in (
                "MONITOR_WATCHDOG_TOKEN",
                "OWNER_NOTICE_TOKEN",
                "NTFY_PUBLISH_TOKEN",
                "OPERATOR_READER_TOKEN",
                "OPERATOR_TOPIC",
                "OPERATOR_SIGNING_KEY",
            )
        }
        reader_port, smtp_port = 18126 + index, 18136 + index
        reader_url = f"https://{bindings['desktop_host']}/_operator-diagnostics/{uid}"
        smtp_url = f"https://{bindings['desktop_host']}/_operator-notices/{monitor_id}/alerts"
        watchdog = dict(
            schema_version=1,
            monitor_id=monitor_id,
            owner_uid=uid,
            state_dir="/state/watchdog",
            token_env="MONITOR_WATCHDOG_TOKEN",
            expected_start_utc=now,
            grace_seconds=300,
            daily_alert_limit=6,
            port=8127,
            alert=dict(url=remote + "/alerts", token_env="NTFY_PUBLISH_TOKEN"),
        )
        notify = dict(
            schema_version=1,
            backend="ntfy",
            monitor_id=monitor_id,
            owner_uid=uid,
            state_dir="/state/inbox",
            token_env="NTFY_PUBLISH_TOKEN",
            topic_env="OPERATOR_TOPIC",
            signing_key_env="OPERATOR_SIGNING_KEY",
            port=8130,
            daily_limit=100 // len(profiles),
        )
        primary = dict(
            schema_version=1,
            backend="smtp",
            monitor_id=monitor_id,
            owner_uid=uid,
            state_dir=str(state / "observability" / "owner-notices"),
            token_env="OWNER_NOTICE_TOKEN",
            port=smtp_port,
            daily_limit=30,
        )
        monitor = dict(
            schema_version=1,
            monitor_id=monitor_id,
            owner_uid=uid,
            state_dir=str(state / "observability" / "monitor-state"),
            expected_start_utc=now,
            scan_seconds=60,
            alert=dict(url=smtp_url, token_env="OWNER_NOTICE_TOKEN"),
            watchdog=dict(url=remote + "/heartbeat", token_env="MONITOR_WATCHDOG_TOKEN"),
            components=[
                dict(
                    id="operator",
                    kind="kernel",
                    local_root=str(owner_root(state, uid)),
                    legacy_state_dir=str(state),
                    schedule=dict(
                        every_seconds=profile["every_seconds"],
                        grace_seconds=230,
                        anchor_utc=now,
                        cron=profile["cron"],
                        timezone=profile["timezone"],
                        pause_marker=str(state / "CS_PAUSE"),
                    ),
                ),
                dict(
                    id="engine",
                    kind="engine",
                    reader=dict(url=reader_url, token_env="OPERATOR_READER_TOKEN"),
                ),
            ],
        )
        WatchdogConfig.model_validate(watchdog)
        NotifyConfig.model_validate(notify)
        NotifyConfig.model_validate(primary)
        MonitorConfig.model_validate(monitor)
        for filename, value in (
            ("watchdog.json", watchdog),
            ("notify.json", notify),
            ("primary.json", primary),
            ("monitor.json", monitor),
        ):
            private_json(directory / filename, value)
        (directory / "desktop.env").write_text(
            "".join(
                key + "=" + token[key] + "\n"
                for key in ("MONITOR_WATCHDOG_TOKEN", "OWNER_NOTICE_TOKEN", "OPERATOR_READER_TOKEN")
            )
        )
        (directory / "desktop.env").chmod(0o600)
        private_json(
            directory / "owner-access.json",
            {
                "notifications": remote + "/inbox",
                "token_env": "NTFY_PUBLISH_TOKEN",
                "private_token": token["NTFY_PUBLISH_TOKEN"],
                "topic_url": "https://ntfy.sh/" + token["OPERATOR_TOPIC"],
            },
        )
        resources.append(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": name, "namespace": namespace},
                "type": "Opaque",
                "stringData": {
                    **{
                        k: token[k]
                        for k in (
                            "MONITOR_WATCHDOG_TOKEN",
                            "NTFY_PUBLISH_TOKEN",
                            "OPERATOR_TOPIC",
                            "OPERATOR_SIGNING_KEY",
                        )
                    },
                    "watchdog.json": json.dumps(watchdog),
                    "notify.json": json.dumps(notify),
                },
            }
        )
        env = [
            {"name": "PYTHONPATH", "value": "/source"},
            {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"},
            {"name": "HOME", "value": "/state"},
        ]
        mounts = [
            {"name": "source", "mountPath": "/source", "readOnly": True},
            {"name": "state", "mountPath": "/state"},
        ]
        security = {
            "runAsUser": 10001,
            "runAsGroup": 10001,
            "runAsNonRoot": True,
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        }
        commands = {
            "watchdog": [
                "python",
                "-m",
                "cs.monitor_cli",
                "watchdog",
                "--config",
                "/state/config/watchdog.json",
            ],
            "recipient": [
                "python",
                "-m",
                "cs.monitor_notify",
                "--config",
                "/state/config/notify.json",
            ],
            "proxy": ["python", "-m", "cs.monitor_proxy", "--listen", "0.0.0.0", "--port", "8080"],
        }
        containers = []
        references = {
            "watchdog": ("MONITOR_WATCHDOG_TOKEN", "NTFY_PUBLISH_TOKEN"),
            "recipient": ("NTFY_PUBLISH_TOKEN", "OPERATOR_TOPIC", "OPERATOR_SIGNING_KEY"),
            "proxy": (),
        }
        for component, command in commands.items():
            selected_env = env + [
                {"name": key, "valueFrom": {"secretKeyRef": {"name": name, "key": key}}}
                for key in references[component]
            ]
            containers.append(
                dict(
                    name=component,
                    image=image,
                    command=command,
                    env=selected_env,
                    volumeMounts=mounts,
                    securityContext=security,
                    resources={
                        "requests": {"cpu": "25m", "memory": "48Mi"},
                        "limits": {"cpu": "500m", "memory": "192Mi"},
                    },
                )
            )
        from deployment_init import INIT_SCRIPT

        init = INIT_SCRIPT
        labels = {"app.kubernetes.io/name": name}
        resources.append(
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": name, "namespace": namespace},
                "spec": {
                    "replicas": 1,
                    "strategy": {"type": "Recreate"},
                    "selector": {"matchLabels": labels},
                    "template": {
                        "metadata": {"labels": labels},
                        "spec": {
                            "automountServiceAccountToken": False,
                            "hostAliases": [{
                                "ip": str(ipaddress.IPv4Address(bindings["ingress_cluster_ip"])),
                                "hostnames": [bindings["host"]],
                            }],
                            "nodeSelector": {"kubernetes.io/hostname": bindings["node"]},
                            "imagePullSecrets": [{"name": bindings["image_pull_secret"]}],
                            "initContainers": [
                                {
                                    "name": "private-state",
                                    "image": image,
                                    "command": ["python", "-c", init],
                                    "volumeMounts": [
                                        {"name": "state", "mountPath": "/state"},
                                        {
                                            "name": "configuration",
                                            "mountPath": "/configuration",
                                            "readOnly": True,
                                        },
                                    ],
                                    "securityContext": {
                                        "runAsUser": 0,
                                        "allowPrivilegeEscalation": False,
                                        "readOnlyRootFilesystem": True,
                                        "capabilities": {"drop": ["ALL"], "add": ["CHOWN"]},
                                    },
                                    "resources": {
                                        "requests": {"cpu": "10m", "memory": "24Mi"},
                                        "limits": {"cpu": "100m", "memory": "64Mi"},
                                    },
                                }
                            ],
                            "containers": containers,
                            "volumes": [
                                {
                                    "name": "state",
                                    "hostPath": {
                                        "path": "/var/lib/operator-observability/" + monitor_id,
                                        "type": "DirectoryOrCreate",
                                    },
                                },
                                {
                                    "name": "configuration",
                                    "secret": {
                                        "secretName": name,
                                        "items": [
                                            {"key": "watchdog.json", "path": "watchdog.json"},
                                            {"key": "notify.json", "path": "notify.json"},
                                        ],
                                    },
                                },
                                {
                                    "name": "source",
                                    "configMap": {
                                        "name": "operator-observability-source",
                                        "items": [
                                            {"key": key, "path": "cs/" + key.removeprefix("cs__")}
                                            for key in code
                                        ],
                                    },
                                },
                            ],
                        },
                    },
                },
            }
        )
        from deployment_policy import isolation_policy

        resources.append(isolation_policy(namespace, name))
        resources.append(
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": name, "namespace": namespace},
                "spec": {"selector": labels, "ports": [{"port": 8080, "targetPort": 8080}]},
            }
        )
        resources.append(
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "name": name,
                    "namespace": namespace,
                    "annotations": {
                        "kubernetes.io/ingress.class": "nginx",
                        "nginx.ingress.kubernetes.io/use-regex": "true",
                        "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
                        "nginx.ingress.kubernetes.io/proxy-read-timeout": "4",
                        "nginx.ingress.kubernetes.io/proxy-send-timeout": "4",
                        "nginx.ingress.kubernetes.io/proxy-body-size": "256k",
                    },
                },
                "spec": {
                    "tls": [{"hosts": [bindings["host"]], "secretName": bindings["tls_secret"]}],
                    "rules": [
                        {
                            "host": bindings["host"],
                            "http": {
                                "paths": [
                                    {
                                        "path": "/_ops/" + monitor_id + "(/|$)(.*)",
                                        "pathType": "ImplementationSpecific",
                                        "backend": {
                                            "service": {"name": name, "port": {"number": 8080}}
                                        },
                                    }
                                ]
                            },
                        }
                    ],
                },
            }
        )
        results.append(
            {
                "id": role,
                "uid": uid,
                "monitor_id": monitor_id,
                "repo": str(repo),
                "state_dir": str(state),
                "reader_port": reader_port,
                "smtp_port": smtp_port,
                "reader_url": reader_url,
                "remote": remote,
                "resource": name,
            }
        )
    private_json(
        output / "resources.private.json", {"apiVersion": "v1", "kind": "List", "items": resources}
    )
    private_json(output / "source-manifest.json", source_manifest)
    private_json(output / "bindings.json", {"profiles": results, "namespace": namespace})
    return {"profiles": len(results), "source_files": len(modules), "activated": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source))
    print(json.dumps(bundle(args.source, json.loads(args.bindings.read_text()), args.output)))


if __name__ == "__main__":
    main()
