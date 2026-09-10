"""Company project memory: engine-backed records and explicit local working copies."""
from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

import jinja2

from . import _time, config
from .project_documents import Documents, ProjectError, digest, metadata, safe_ancestors, slug
from .project_working import checkout, import_projects, save


def _template_root() -> Path:
    return Path(__file__).parent / "templates" / "project_memory"


def title_from_slug(slug: str) -> str:
    """`acme-corp` -> `Acme Corp`. A starting point for the human title, which
    the operator overrides with --title when the real name has punctuation or
    a legal form (`Acme Corp S.p.A.`)."""
    return " ".join(part.capitalize() for part in slug.split("-") if part)


def render_scaffold(dest: Path, render_vars: dict) -> list[Path]:
    """Render every template into `dest`. Returns the files written, in order.

    Kept separate from the command so a test can exercise the rendering without
    driving argparse or a manifest.
    """
    root = _template_root()
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(root)),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.StrictUndefined,
    )
    written: list[Path] = []
    for tpl in sorted(root.rglob("*")):
        if tpl.is_dir():
            continue
        rel = tpl.relative_to(root)
        out = dest / rel
        if out.suffix == ".j2":
            out = out.with_suffix("")
        out.parent.mkdir(parents=True, exist_ok=True)
        if tpl.suffix == ".j2":
            out.write_text(
                env.get_template(str(rel)).render(**render_vars), encoding="utf-8"
            )
        else:
            out.write_bytes(tpl.read_bytes())
        written.append(out)

    # `meetings/` must survive a commit even while empty, or the scaffold's
    # append-only half silently disappears from git and the next session does
    # not know where meeting notes go.
    meetings = dest / "meetings"
    meetings.mkdir(parents=True, exist_ok=True)
    keep = meetings / ".gitkeep"
    keep.write_text("", encoding="utf-8")
    written.append(keep)
    return written


def _new(client, settings, args):
    name = slug(args.name)
    client.page('list', limit=1)
    render_vars = {
        'project_name': name,
        'project_title': (args.title or '').strip() or title_from_slug(name),
        'today': _time.local_date(_time.now_utc(), settings.timezone),
        'owner_account': (getattr(args, 'account', None)
                          or settings.founder_sweep_account or settings.email_address),
    }
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        written = render_scaffold(root, render_vars)
        files = {path.relative_to(root).as_posix(): path.read_bytes() for path in written}
    response = client.request('create', space_id=client.space_id, project=name,
                              files={path: base64.b64encode(data).decode('ascii') for path, data in files.items()})
    received = response.get('files')
    if response.get('project') != name or not isinstance(received, list) or len(received) != len(files):
        raise ProjectError('Invalid project creation response. Check cs project files before retrying.')
    verified_paths = set()
    for item in received:
        metadata(item, name)
        path = item['path']
        if path not in files or path in verified_paths or item['sha256'] != digest(files[path]):
            raise ProjectError('Project creation verification failed. Check cs project files before retrying.')
        _, data = client.read(name, path, item['revision'])
        if data != files[path]:
            raise ProjectError('Project creation read-back verification failed.')
        verified_paths.add(path)
    print(f'Created {name} in company memory ({len(files)} files).')
    print(f'Open its status: cs project show {name}')
    print(f'Edit a working copy: cs project checkout {name} ./project-{name}')


def cmd_project(args):
    try:
        if not Path('manifest.toml').is_file():
            raise ProjectError('Run cs project from the clone directory containing manifest.toml.')
        settings = config.load()
        client = Documents(settings)
        action = args.paction
        if action == 'new':
            _new(client, settings, args)
        elif action in ('list', 'files', 'history'):
            params = {}
            if action != 'list':
                params['project'] = slug(args.name)
            if action == 'history':
                params['path'] = args.path
            result = client.page(action, limit=args.limit, offset=args.offset, **params)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                for item in result['items']:
                    if action == 'list':
                        print(item['project'])
                    else:
                        print(f"{item['path']}  revision {item['revision']}  {item['size']} bytes  {item['created_at']}")
                print(f"Showing {len(result['items'])} of {result['total']} (offset {result['offset']}).")
        elif action == 'show':
            result, data = client.read(args.name, args.path, args.revision)
            if args.output:
                destination = safe_ancestors(args.output)
                with destination.open('xb') as stream:
                    stream.write(data)
                print(f'Wrote {len(data)} bytes to {destination}.')
            elif args.json:
                print(json.dumps(result, indent=2))
            else:
                try:
                    text = data.decode('utf-8')
                except UnicodeDecodeError:
                    raise ProjectError('Binary document: use --output FILE for byte-exact export.') from None
                if any(ord(c) < 32 and c not in '\n\r\t' for c in text) or '\x7f' in text:
                    raise ProjectError('Binary or control-character document: use --output FILE.')
                print(text, end='' if text.endswith('\n') else '\n')
        elif action == 'checkout':
            checkout(client, args.name, args.directory)
        elif action == 'save':
            save(client, args.directory, args.commit)
        elif action == 'import':
            import_projects(client, args.directory, args.name, args.all, args.commit)
        return 0
    except (ProjectError, OSError) as exc:
        print(f'Project operation refused: {exc}', file=sys.stderr)
        return 1


def cmd_project_new(args):
    """Compatibility entry point; all commands share validation and error handling."""
    args.paction = 'new'
    return cmd_project(args)


def add_subparsers(sub):
    project = sub.add_parser('project', help='shared company project documents')
    actions = project.add_subparsers(dest='paction', required=True)
    new = actions.add_parser('new', help='create project index, status and timeline in company memory')
    new.add_argument('name')
    new.add_argument('--title')
    for action in ('list', 'files', 'history'):
        parser = actions.add_parser(action, help='list project metadata' if action == 'list' else f'list project {action}')
        if action != 'list':
            parser.add_argument('name')
        if action == 'history':
            parser.add_argument('path')
        parser.add_argument('--limit', type=int, default=50)
        parser.add_argument('--offset', type=int, default=0)
        parser.add_argument('--json', action='store_true')
    show = actions.add_parser('show', help='read one document (status.md by default)')
    show.add_argument('name')
    show.add_argument('path', nargs='?', default='status.md')
    show.add_argument('--revision', type=int)
    output = show.add_mutually_exclusive_group()
    output.add_argument('--json', action='store_true')
    output.add_argument('--output')
    fetch = actions.add_parser('checkout', help='download a new working copy for editing')
    fetch.add_argument('name')
    fetch.add_argument('directory')
    put = actions.add_parser('save', help='preview changes to a working copy')
    put.add_argument('directory')
    put.add_argument('--commit', action='store_true', help='save changes to company memory')
    migrate = actions.add_parser('import', help='preview a non-destructive legacy project import')
    migrate.add_argument('directory')
    selection = migrate.add_mutually_exclusive_group()
    selection.add_argument('--name')
    selection.add_argument('--all', action='store_true', help='import immediate project subdirectories')
    migrate.add_argument('--commit', action='store_true', help='import and verify bytes in company memory')
    project.set_defaults(func=cmd_project)
