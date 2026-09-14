# Vonage SIP

The installed CLI exposes `cs connection vonage` through the normal command
entry point. It is clone-scoped: `--account` is rejected. It uses Vonage's HTTPS
PSIP API directly; a separately installed vendor CLI is not required.

Declare `[connections.vonage]` in the clone manifest with `enabled = true`,
`api_key_env`, `api_secret_env`, `application_ids` (allowed voice application
UUIDs), and `region` (`eu`, `us`, or `ap`). Disabled is the default. Credential
fields are environment-variable names, never secret values. Exact references
resolve through this clone's captured env files, then the process environment;
there is no fallback to unreferenced provider variables. `CONNECTIONS`
cannot override the manifest binding. `cs config` reports only non-secret data.

`status`, `domains`, `show DOMAIN`, and `users DOMAIN` are read-only. The user
list excludes secrets. Requests use a fixed provider endpoint, Basic auth,
bounded timeouts, no redirects and no automatic retries. An empty successful
GET is incomplete evidence; only a 404 proves a missing domain.

`provision` previews creation of an application domain and digest user;
`allow-ip` previews an additive public IPv4 ACL update. `--help` owns arguments.
Commit requires `--commit`, a terminal, no pause file and no headless marker
(`CS_OPERATOR_HEADLESS` or `CS_HEADLESS_SEND`). Context is rechecked before
credential creation and each provider mutation. The rendered cron sets the
marker and denies both verbs in six command spellings. This is an operational
guard, not isolation against a process that can alter its own environment.

Agent-host permissions also apply. The stamped Claude settings deny the two
provider mutation verbs, including their preview forms, in interactive sessions
as well as cron. Human task authorization does not override that host policy.
An operator can run the installed CLI directly in an authorized terminal;
other agent hosts need their own permission to execute it. Never work around a
host denial through another command spelling or launcher.

Provision refuses existing domains. Its new credential file must be a direct
child of the clone's private, owned mode-0700 state directory; it is created
exclusively with mode 0600 before the first provider write. Partial failures
retain it for recovery. Provider errors never echo response bodies. ACL updates
preserve unrelated domain fields and refuse an existing open/private ACL.

PSIP has no documented conditional revision update: pre-write checks and
readback do not close the final concurrent-writer window. Coordinate dashboard
and API edits. Digest-user readback proves existence, not authentication.
Telephone-number association, PBX setup and a real call remain separate checks.

The canonical `cs-sip-trunk` template is shared by Claude Code, Codex and
OpenCode through project agent surfaces. It reads clone-owned
`company/sip-trunk.md` for business procedure and source documents. Customer
drafting still requires a dossier and the engine. Passwords remain outside
model prompts; the operator privately fills draft placeholders.

The released integration is installed in both maintained clones. Each clone
must enable its own binding; installing the shared code grants no provider
credentials. The [rollout plan](../execution-plans/2026-09-14-vonage-production-rollout.md)
owns deployment evidence. No Shopify or Faire implementation is included.

## What has been verified

On 2026-09-14, the installed CLI authenticated against the configured account,
listed domains and verified the allowed voice application. A real-provider
provision preview completed without writes or a generated credential file.
The second clone refused provider access because its binding is disabled.
Both package installations and independent lock-only rebuilds contain the exact
released template inventory; all three agent surfaces expose the same SIP skill.

Forty-one configuration, HTTP, provisioning and agent-surface tests passed,
including local-server mutation/readback, partial failures and headless refusal;
the full kernel suite passed at the release tag. No customer trunk was created,
password authentication exercised, PBX configured or test call placed as part
of this release validation.

## Requests this integration can handle

- Inspect the actual domain, allowed IPs, application and digest users.
- Prepare and apply an authorized new-domain configuration after confirming
  the PBX public IP and application.
- Preview and apply an additive public-IP ACL change on a supported existing
  application domain, preserving unrelated configuration.

Use `cs connection vonage status` first and the `cs-sip-trunk` skill for the
customer workflow. Report CLI success as configuration verification, not proof
that the customer's telephone service works.
