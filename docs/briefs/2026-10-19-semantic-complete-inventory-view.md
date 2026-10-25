# Semantic complete inventory view

## Intent and authorization

A COMPLETE global inventory is every row/root/group/order and the facts needed
for global eligibility, selection and truthful reporting. It is not a full case
archive. Provide that small readable inventory while retaining full raw case and
proof detail for selected-root current deep reads. This is explicitly a semantic
projection, NOT lossless or native/raw-equivalent inspection. Native will not have
read every omitted detail. Do not claim all business facts are preserved in view.

Brief/framing review ONLY: no plan, prototype, code, installation or paid test.
The lossless M0 is FAILED/STOP (13 to11 pages). V22 remains FAILED unchanged.
No alternate codec loop, cap increase, auto-continuation or retroactive PASS.

## Product and trust boundaries

Every global group, row, duplicate occurrence, root and order stays visible,
including held/deferred roots. Engine-provided current eligibility/assignment
state/completeness/hold/error/reason, owner/component scope, contacts/subject/date/
wait/escalation/material task facts and exact workset selection stay explicit.
Held/deferred roots cannot act. Selected-root fresh deep reads BEFORE effects
remain mandatory, with all current engine guards and six phases unchanged.

Raw public stdout/protected discovery.json/raw receipt remain byte-identical.
A separate private view is bound to raw hash/schema/owner/process-start/nonce/
native invocation. Existing raw transport/owner/process/hash validation is
preserved (`operator_health.py:104`, `operator_discovery_receipt.py:574`). An
independent consumer recomputes the exact approved projection AND full inventory
universe/group/order/occurrence/workset parity from raw, not producer attestations.
No stronger upstream authenticity is invented: nested engine hashes remain opaque
engine assertions, not independently authenticated original MIME/header bytes.
Native sees engine decisions; the kernel does not re-derive them from proof.

KEEP below means exact typed current value visible, including absence/null.
RAW REF means exact retained detail, mapped by source group/row identity and
schema-defined field path, available for selected-root deep reads; not an action
permission. A shared schema legend can define paths once, without hundreds of
per-field pointers. No root or global inventory row becomes a digest-only entry.
A visible identity legend may give exact root/actor/space strings once with clear
typed short IDs at every original occurrence; all resolve within the view.

## Field-by-field global versus selected-detail classification

| Raw field/path | Treatment | Global decision/report impact and required safeguard |
| --- | --- | --- |
| root.owner_uid/nonce/ancestry.pid+started_ticks/exit_code | KEEP | Current actor/run identity and technical failure remain explicit. |
| root.output_sha256 | RAW REF; pinned raw hash in envelope | Existing transport equality is independently checked. Digest spelling does not explain global eligibility; no new proof-authenticity claim. |
| discovery group names/order/row counts/empty groups | KEEP | Preserve whole universe and every occurrence, including a root appearing in several groups. |
| assignment_incomplete/note/read_incomplete/crm_note | KEEP | No technical error or incomplete authority becomes silent success. |
| row.email/name/subject/last_inbound_date/days_waiting/thread_key/state/reason/_workset_revision | KEEP | Contact, age, engine state, global reason and current revision determine triage/report. |
| escalated_at/escalated_owner/escalated_reason/days_escalated | KEEP | Preserve who owns escalation and why; cannot be replaced by boolean. |
| operational_fixture_discovery.message_id/provider_folder/provider_uid/provider_uidvalidity/owner_uid/body_sha256 | KEEP | Preserve protected-original protocol exactly, without priority/selection changes. |
| assignment.version/actor_uid/space_id/thread_key/authoritative_thread_key/component_thread_keys/component_scope_present/source_owner_uid | KEEP | Preserve engine authority version, ownership and ALL component roots/scope; visible legend allowed, never external lookup to know a global root. |
| assignment.complete/authority_complete/state/hold_auto_reply/hold_scope/reason | KEEP | These authoritative current global decisions stay exact. No per-observation inference substitutes for them. |
| assignment.task/events | KEEP null/empty; otherwise classify material facts prospectively or REFUSE compact route | No unknown task/event can be silently hidden. Actual V22 task=null/events=[]; future nonempty material shape needs reviewed schema before compact use. |
| assignment.current_inbound/covered_inbound | KEEP null/empty; unknown nonempty shape REFUSE | Inbound metadata could contain material state; no blanket omission. Actual V22 empty. |
| assignment.current_message_ids/covered_message_ids | RAW REF with visible exact counts, not global roots | Message-level case detail does not change the engine's visible current authority/hold judgement. Selected-root fresh dossier must inspect applicable current/covered messages before effects; global report cannot claim message-level resolution from counts. Root/component universe still KEEP. |
| assignment.provenance[].basis/owner/reason | KEEP | Human/ownership basis and reasons may affect eligibility/reporting; repetition is not irrelevance. |
| assignment.route_digest | RAW REF | Technical engine commitment retained under existing transport trust. Visible actor/root/scope/state/hold/reason and current engine action checks preserve decision boundary; no new route-authentication claim. |
| assignment.reply_evidence: container order/count and nonempty indicator | RAW REF plus visible count/detail reference | Whole per-observation case proof is retained. Global view uses current engine assignment state/hold/reason, supplemented by the visible per-observation semantic facts listed below, without re-deriving engine decisions. Report may say proof retained, never claim to have inspected or authenticated every observation. |
| reply_evidence.version/actor_uid/space_id/source_id/thread_key/complete/judgement/reason | KEEP every ordered semantic observation | Existing global state/reason does NOT establish that every material observation conflict/error is surfaced. Retain these facts explicitly, without aggregation or inferred conflict resolution; typed visible identity references may avoid repetition. No kernel re-derivation or action authority follows. |
| reply_evidence.digest | RAW REF | Opaque commitment, not human-readable global decision; no invented independent authenticity. |
| reply_evidence.source.actor_uid/mailbox_id/thread_key/observation_only | KEEP in semantic observation table | Preserve source ownership/root and observational limits so raw-detail deferral cannot hide those facts. |
| reply_evidence.source.message_id | RAW REF as selected-case message detail | Message navigation is selected-case detail; source/root/owner/judgement/reason remain visible. Fresh selected-root reads must resolve actual current messages before effects. |
| reply_evidence.source.provider.folder/uid/uidvalidity | RAW REF as selected-case provider detail | Provider originals remain retained and available to current selected-root reads/dedup; global row/root enumeration needs no per-observation UID. Protected fixture metadata above remains unchanged. |
| reply_evidence.source.route_digest/raw_header_digest/content_digest | RAW REF | Technical commitments do not explain global eligibility. Existing transport/projection validation retained, no original-header/MIME authenticity claim. |
| triage_workset.complete/limit/selected.thread_key+revision+sources | KEEP | Exact ordered current selection unchanged, no fixture priority. |
| triage_workset.deferred.thread_key+reason+sources, held.thread_key+reason+source+identity | KEEP | Every held/deferred occurrence, identity and reason explicit; no action outside selected set. |
| Any unknown field/unclassified nested shape, material conflict/error not faithfully represented by kept global AND observation semantic facts | REFUSE compact route | No silent discard, hash-away, inference or waiver. Existing strict full raw route remains available; otherwise stop unhealthy. |

Each RAW REF exclusion requires fresh reviewer challenge for global eligibility,
action and report sufficiency. In particular, the reviewer must decide whether
current visible engine authority/hold AND all observation semantic facts suffice to defer technical/message detail
until selected-root reads, rather than assume all proof is irrelevant. If such
sufficiency cannot be established, REVISE or KEEP that detail; no implementation
can silently broaden the exclusion. Engine decisions remain authoritative.

## Actual size attribution and future acceptance boundary

Bounded arithmetic (not another codec/prototype) is retained externally at
`/home/mal/.local/share/ordinary-assignment-recovery-resume/bounded-triage-workset-20261018/semantic-inventory-field-size-audit.json`.
Raw98,755 bytes/13 pages; compact full raw94,718/12 pages. Six-digest-only removal
leaves77,122/10 pages;214 explicit field pointers add17,059 bytes, giving94,181/12
pages. That narrower proposal is inadequate and stopped.

Reply-evidence containers contribute50,171 bytes; removing them without retained
semantic global facts/references is not an approved view. Even blind deletion
leaves44,547 bytes/6 pages. There are37,480 optimistic duplicate-long-string bytes
in full raw, but legend overhead and retained global facts limit real savings.
No achieved1–2-page prediction exists. These are size attributions, not a passing
projection. Aim genuinely readable1–2 pages with the existing8192-byte pages and
8064 stride; if complete global context cannot fit, do not hide it to hit target.

Only a separately authorized/reviewed plan may define exact schema and an offline
actual-V22 gate. It must independently recompute full universe and approved field
projection, map every raw reference, reject unknowns/changed roots/groups/order/
selection/owner/hold/errors/bindings and require fresh semantic readability review.
Reviewer must trace every row/root/hold and selected root using only the view,
while selected detail remains explicitly uninspected until fresh deep reads.
Full native view inspection needs bounded matching paging and truthful remaining
offsets; no Read/dd mismatch, permission widening, synthetic events or polling.
No runtime work or paid acceptance follows from framing approval alone.

Framing revision: the previous whole-observation exclusion was REVISE because
existing peer merging may emit generic global reasons while retaining important
observation detail. This candidate therefore KEEPS every ordered observation
judgement/reason/completeness and source ownership/observation-only fact. It makes
no unproved upstream global-summary sufficiency claim. Remaining RAW REF fields
are message/provider navigation and opaque commitments, with fresh selected deep
reads unchanged. Actual page feasibility remains unestablished, not waived.


## Prospective practical-gate amendment: unchanged candidate only

The coordinator's two-page target was an internal feasibility target, not an
operator hard requirement. The existing semantic M0 candidate is42,598 view bytes
plus102 envelope bytes =42,700 native-needed bytes/six pages. Its historical
FAILED/STOP against16,256/two pages remains immutable; it is never relabelled PASS.
Report/hash and external artifacts are retained. No alternate codec, field
omission, candidate tuning or runtime adoption is authorized by this amendment.

Prospectively assess that SAME frozen candidate against at most SIX pages,
including all native-needed binding/envelope/legend/headers/notes, max48,512 bytes
under8192-byte pages/8064 stride, AND at least50% fewer pages than the13-page raw.
Actual six versus13 is53.85% fewer pages. This is an efficiency threshold, not a
prediction that the model will finish within its unchangedUSD4 budget. Native
V22 voluntarily skipped13 pages atUSD1.8873254; no budget-exhaustion terminal was
observed. Less text is a measured reduction, not evidence of future compliance.

Six pages can be practically assessable only if a fresh reviewer reads ENTIRE
unchanged view and traces holds, all global facts and both selected roots without
raw/Python decoding. Typed identity references must remain comprehensible across
pages. Future source-owned initial page plan and truthful remaining-offset hints
can make progress explicit; they are a separately reviewed runtime mechanism,
currently absent and cannot be treated as proof that this candidate works.
Existing budget/caps/guards/deep selected-root reads remain unchanged.

Same framing and plan reviewers must approve this prospective amendment before
finishing independent parity/negatives on the frozen candidate. Every approved
KEEP/RAW REF/universe/occurrence/order/workset rule still applies. Checker/test
source may be completed or repaired within a bounded handoff, but candidate
view/envelope/producer/input bytes must remain frozen. Any required candidate
change stops this scope. A fresh semantic reviewer is mandatory after all free
checks pass. No runtime/adoption/paid authority follows; root must see measured
complete envelope plus real independent and semantic verdicts first.


Prospective runtime measurement qualification: mandatory native envelope EOF plus
six view pages requires SEVEN separate dd calls, not six. Current observed
43,313 total native-needed bytes is about56% fewer than98,755 raw bytes; seven
versus13 calls is46.15% fewer calls. The earlier six-page/53.85% figure describes
aggregate byte capacity or view pages, never actual combined tool calls. Root
accepts this measured material reduction as the practical component criterion,
under unchangedUSD4 budget without a completion/compliance guarantee. Both artifact
EOF checks stay strong; no metric-driven transport complexity, field/schema loss,
cap/permission change or old M0 report rewrite. Prior failed gates remain historical.
This qualification requires plan review approval before M1 acceptance.
