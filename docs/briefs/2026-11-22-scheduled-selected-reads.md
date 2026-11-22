# Exact selected reads in scheduled operator runs

## Intent

Let a scheduled operator read the assignment for each conversation selected by its own run. It should not need to transcribe a message identifier from a large inventory. A literal dollar sign inside a quoted identifier must survive the normal read and native completion checks.

## Scope

Both clones use the same kernel and scheduled workflow. Use the current run's reserved selection for assignment reads. Keep manual exact-key reads compatible. Teach the scheduled workflow to defer campaign contacts outside the selected scope before requesting deep mail. Preserve independent receipt verification, exact root identity, the two-conversation limit and the engine's authority to hold a conversation. Keep failures visible in the existing diagnostics.

## Acceptance

- Through the scheduled caller, read both selected roots in order with exact identities even when their keys are long or contain a literal dollar sign. Stale, missing or invalid selection must fail before the engine call.
- An existing correctly single-quoted assignment command with a literal dollar sign is recognized as the same read by the native receipt consumers. Shell evaluation and other commands remain outside that recognition.
- The scheduled instructions use the bound selection and defer unrelated contacts. A read attempted outside selection still fails. Successful completion continues to require proof of the phases the operator actually performed.
- Demonstrate the change with offline fixtures and retained streams. Record residual independent failures from those streams. Use counts and finite codes only in shared evidence.

## Constraints and assumptions

The starting package is the privately installed v0.73.3. No paid run, live email effect, public release, permission expansion, engine change or mailbox ownership change belongs to this development work. Installation on either clone is a distinct release operation.
