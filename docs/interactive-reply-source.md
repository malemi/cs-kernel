# Interactive reply source routing

The current kernel delegates mailbox drafts to the Desktop engine. The
[mailbox draft lifecycle](draft-lifecycle.md) owns current preparation, recovery,
send and recoverable deletion semantics. `cs draft-reply` uses
`drafts.compose_reply`; `cs draft-send` addresses a current opaque mailbox handle.
Missing or externally sent drafts are not recreated. The engine owns provider
mutations and exact Sent confirmation.

The November 6 [core plan](execution-plans/2026-11-06-interactive-reply-core-main.md)
and [workflow plan](execution-plans/2026-11-06-interactive-reply-m5-main.md) preserve
historical source evidence for the superseded paired-copy design. Their
`draft-retire`, mirror publication, `--resume-draft` and `--operator-request`
contracts are historical and do not describe current commands. Main does not
restore that implementation. The [main integration plan](execution-plans/2026-11-25-mailbox-main-integration.md)
binds the combined source checks.

The independent embedded `prepare_reply` helper prepares an engine draft under
its authenticated managed contract; see the
[embedded source boundary](desktop-operator-source.md). It is separate from the
normal native CLI. Source integration alone changes no installed package,
recipient authority, runtime budget or recurring schedule.
