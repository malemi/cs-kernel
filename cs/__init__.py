"""cs — the shared kernel of the <company>-cs customer-service operators.

The engine daemon (zylch-server@<uid>, the mrcall-desktop engine) is the
body: mail archive, entity memory, tasks, trained writing voice,
draft/send. Claude Code is the brain. cs is thin transport + operator
discipline: producer worklist (plan), per-candidate dossier (threads /
recent contact / tasks / CRM), campaign lifecycles, and a gated chat
surface for engine-side drafting. Contextual mail is composed ONLY by
the engine; only fixed-template bulk is cs-owned (send_mail / sms).

Per-company variance is DECLARED, never coded: it comes from the stamped
clone's manifest.toml (cs/manifest.py) through Settings (cs/config.py).
This package contains no company literal — see the kernel CLAUDE.md
(the charter) and the CI grep gate. The module path `cs` is FROZEN, and
the console script `cs` is a second door onto the same `cs.cli:main`.
Permission rules match command text, so clone permission strings
enumerate every spelling that reaches it (six in the deny sets, four in
the allow list — see the kernel CLAUDE.md); `prog_name` is display-only.
"""
