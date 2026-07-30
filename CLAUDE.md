# CLAUDE.md — cs-kernel

The shared KERNEL of the `<company>-cs` customer-service operators.
Distribution **`cs-kernel`**, import package **`cs`**. A stamped clone has
**no `cs/` source directory**: it pip-installs this kernel from a git tag
(`requirements.txt` pin), so `.venv/bin/python -m cs …` resolves from
site-packages and a clone *cannot* drift a package whose source it does
not hold. Upgrades are a pin bump + `pip install`, never a cherry-pick.

Design source of truth: the brief `cs-kernel-manifest-separation.md`
(in the meta-repo, `docs/briefs/`). The two existing clones — A (the
mother) and B (the first child) — are the permanent test fixture: every
kernel change must keep `kernel + manifest(X) ≡ X` on observable surfaces
(collaudo, brief §6).

## The charter (anti-fork rules — enforced by review + CI)

1. **No company literal anywhere in `cs/`** — no mailbox, slug, drive
   scope, campaign name, brand, or absolute path. CI gate (must stay
   empty):

   ```bash
   grep -rEi 'mrcall\.ai|cafe124|124-cs|centralix|/home/mal|CAFE124|\bHB\b' cs/
   ```

   Platform names are allowed where they name shared infrastructure the
   kernel drives (the mrcall-desktop *engine*, the `mrcall.search_businesses`
   RPC method, the `mrcall-tracking` *adapter id*) — those are the same for
   every clone. Company *hosts/domains/values* are not: they live in the
   manifest.

2. **Everything company-shaped comes from `Settings`** (← `manifest.toml`
   ← env layers). About to write `if company == …`? Stop: it is a manifest
   field or an adapter. Identity prints, the SELF cc, state paths, the
   drive-scope message, the From display name — all derive from Settings.
   (Firebase app names are the one deliberate exception: fixed neutral
   kernel constants — the per-clone swap was proven pointless.)

3. **Rule of two.** A capability enters the kernel only when ≥2 companies
   need it; a single company's need lives in that clone's `ext/` (which
   the kernel tolerates and NEVER imports). Campaign packs respect the
   same split: pack CONTENT is company data in the clone
   (`campaigns/<name>/`), the RUNNER is kernel code (`cs/campaign_pack.py`
   + the `send_reminder`/`send_sms` handlers in `cs/campaign.py`).

4. **The invariants are code, not config** (never manifest fields):
   - Identity is always the company's own support mailbox (daemon gates
     `token.sub == OWNER_ID`; SMTP logs in with the mailbox's own creds).
   - Contextual/free-form generation ONLY via the engine; only
     fixed-template bulk is cs-owned (`send_mail.py`, `sms.py`).
   - The headless cron is draft-only via the wrapper's `--disallowed-tools`
     re-deny set (template-side, baked verbatim) — not a knob.
   - Policy/voice/signature live in engine `USER_NOTES`, outside every repo.
   - **Gmail Sent/All Mail is the dedup ground truth** — never the engine
     archive (`emails.search folder:sent` misses hand-sent mail and drops
     threads when the customer replies last). No dedup-source knob exists.
   - **Module path `cs` is frozen**; every clone permission string is the
     literal `.venv/bin/python -m cs …`. `prog_name` is display-only.
   - Engine RPC response shapes are kernel-owned (`emails.search→{threads}`,
     `list_by_thread→{emails}`, `tasks/campaign.*/drafts.list→bare arrays`,
     `settings.get→{values}`).
   - The accounts registry never mixes another project's mail domain.
   - Never auto-commit; **stamp-before-send** for pack senders; RATE_CAP +
     CS_PAUSE + Sent-dedup-first before any real send; escalate on
     uncertainty.

5. **Ports, not switches.** CRM (`cs/crm/`) and producer (`cs/ingest/`)
   are explicit registries of one-function adapter modules; an unknown
   adapter name fails LOUD at config load. `lookup`/`fetch` never raise —
   they degrade with an actionable note that the CLI surfaces. The dossier
   VERDICT stays CRM-agnostic.

## Layout

```
cs/
├── config.py        Settings: manifest + layered env (see module docstring)
├── manifest.py      manifest.toml schema + loader + Settings overrides
├── cli.py           the verbs (argparse; prog from Settings)
├── campaign.py      two lifecycles + pack senders (Gmail-Sent dedup)
├── campaign_pack.py pack loader/renderer (campaigns/<name>/ in the clone)
├── sms.py           generic SMS via the manifest [sms] proxy
├── send_mail.py     the ONLY module allowed to import smtplib
├── gmail_archive.py Gmail IMAP ground truth (sent_to/correspondence/inbound_since)
├── gmail_drafts.py  append-only Gmail Drafts review surface (SMTP-free)
├── crm/             port + adapters: starchat, shopify, none
├── ingest/          port + adapters: mrcall-tracking, none
├── project_memory.py `cs project new`: stamps a project's written memory
│                    (index + status + timeline + meetings/) under docs/projects/
├── rpc.py auth.py resolve.py drive.py review.py state.py filter.py _time.py
└── scripts/find_profile_uid.py   clone-onboarding setup tool
```

Two template roots, and the distinction is load-bearing:
`templates/project/` is stamped **once per clone** by `cs init` / `cs update`;
`templates/project_memory/` is stamped **once per project** by `cs project new`.
Each needs its own `package-data` glob in `pyproject.toml` or the verb ships
without its templates.

NOT in this repo (template/clone side): `.claude/` (skills, commands,
settings.json), the cron wrapper `bin/cs_operator_cron.sh` (its deny body
is an invariant baked by the template), `company/*.md` prose slots,
`campaigns/` pack content, `manifest.toml` itself, docs/customers, `ext/`.

## Versioning & release

Semver tags `v0.MINOR.PATCH`; clones pin **tags only**, never branches.
PATCH = behavior-identical fix (cheap re-pin); MINOR = new manifest field /
adapter / behavior change (full re-collaudo). Every tag gets a CHANGELOG
entry naming what changed and **which clones must re-collaudo** at which
tier (brief §6.6). Never push without the operator's explicit ok.

## Tests

```bash
bash tests/run.sh      # grep gate, boundary greps, clean-venv install,
                       # full --help tree, config semantics, pack loader
```

The golden pack gate (byte-equality of a pack's builders vs a clone's
reference module) is env-driven so clone copy never enters this repo:

```bash
CS_GOLDEN_REF_BUILDERS=<clone>/…/reference_builders.py \
CS_GOLDEN_PACK_DIR=<clone>/campaigns/<pack> \
python tests/test_golden_pack.py
```

Semantic tests only — no mock theatre. Anything touching send paths,
campaign, gmail_archive, send_mail or permissions additionally requires
the full collaudo suite on BOTH clones before the tag ships (brief §6.6).
