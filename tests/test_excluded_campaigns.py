#!/usr/bin/env python3
"""`[campaigns].excluded_campaign` holds MORE THAN ONE campaign.

Why this exists: `mrcall-cs` finished two Centralix→Vonage campaigns —
`<name>` (cutover June) and `<name>-batch2` (finished July) — and the field
held exactly one string, matched with `==`. Only the first was excluded, so
for a month the general operator kept picking up the second one's
`handle_reply` actions. The engine registers no `campaign.close` RPC
(`create`, `list`, `add_contact`, `contacts`, `update_contact` only) and the
kernel filters on no `status` anywhere, so the exclusion list is the only
lever there is.

The shape is the one every other multi-value knob in `cs/config.py` already
uses — a comma-separated string with a `_set` property (`self_emails`,
`system_senders`, `send_guard_banned_phrases`). That choice is what makes it
backward compatible for free: a clone whose manifest holds a single bare name
parses to a one-element set and behaves exactly as before, with no edit and no
key rename, so no stamped clone breaks.

Matching stays EXACT per name. Prefix or substring matching would have made
this a one-character fix — `startswith` — and would then have silently
excluded every future `<name>-anything` campaign nobody meant to exclude. Two
explicit names is the honest configuration, and the prefix case below is the
assertion that keeps it that way.

Hermetic: stubs `cs.rpc.call_sync`; no engine, no mailbox, no network.
"""
from __future__ import annotations

import types

from cs import campaign, config, config_report, gmail_archive, manifest, rpc


# Deliberately generic names: this is the kernel, and a company literal here
# would fail the charter grep gate. The SHAPE is what the real incident had —
# a campaign and its `-batch2` sibling, which is exactly the prefix trap.
FIRST = "vendor-migration"
BATCH2 = "vendor-migration-batch2"
OTHER = "spring-welcome"


def _settings(excluded: str):
    """A settings stand-in that resolves `excluded_campaign_set` through the
    REAL property, not a re-implementation of it — a test that parses the
    string itself would pass while the shipped parser was broken."""
    ns = types.SimpleNamespace(
        excluded_campaign=excluded, dedup_days=30,
        timezone="Europe/Rome", sms_hour=18, reminder_max=3,
    )
    ns.excluded_campaign_set = config.Settings.excluded_campaign_set.fget(ns)
    return ns


def _parse(excluded: str) -> set[str]:
    return config.Settings.excluded_campaign_set.fget(
        types.SimpleNamespace(excluded_campaign=excluded)
    )


def test_parsing() -> None:
    # The old shape — one bare name — still means exactly that one campaign.
    assert _parse(FIRST) == {FIRST}
    # Several, with and without whitespace around the separators.
    assert _parse(f"{FIRST},{BATCH2}") == {FIRST, BATCH2}
    assert _parse(f"{FIRST}, {BATCH2}") == {FIRST, BATCH2}
    assert _parse(f"  {FIRST} ,  {BATCH2}  ") == {FIRST, BATCH2}
    # Empty, and the degenerate separator-only forms, mean "exclude nothing" —
    # never "exclude the empty-named campaign", which would match a contact
    # whose `_campaign_name` lookup came back blank.
    assert _parse("") == set()
    assert _parse("   ") == set()
    assert _parse(",") == set()
    assert _parse(f"{FIRST},,") == {FIRST}
    # Case is preserved: engine campaign names are identifiers, not prose.
    assert _parse("Vendor-Migration") == {"Vendor-Migration"}
    print("OK: parsing — one name, several, empty, whitespace, no empty member")


def test_prefix_is_not_a_match() -> None:
    """The whole reason this is a LIST and not a prefix rule."""
    s = _settings(FIRST)
    assert FIRST in s.excluded_campaign_set
    assert BATCH2 not in s.excluded_campaign_set, (
        "excluding %r must NOT also exclude %r — a prefix rule would silently "
        "exclude campaigns nobody named" % (FIRST, BATCH2)
    )
    # And the converse: the longer name alone does not exclude the shorter one.
    assert FIRST not in _settings(BATCH2).excluded_campaign_set
    print("OK: a shared prefix is not a match, in either direction")


def _stub_engine(campaign_names: list[str]) -> list[tuple]:
    """campaign.list returns the given campaigns; each has one contact."""
    calls: list[tuple] = []

    def fake_call_sync(settings, method, params, timeout=None):
        calls.append((method, params))
        if method == "campaign.list":
            return [{"id": f"camp-{n}", "name": n} for n in campaign_names]
        if method == "campaign.contacts":
            name = params["campaign_id"].removeprefix("camp-")
            return [{
                "id": f"contact-{name}", "email": f"person@{name}.test",
                "state": "sent", "dossier": {},
            }]
        if method.startswith("emails."):
            return {"threads": []}   # nobody has replied; keeps the sweep quiet
        raise AssertionError(f"unexpected RPC: {method} {params}")

    rpc.call_sync = fake_call_sync
    # Gmail is the dedup/reply ground truth and it is NOT what this test is
    # about: nobody has replied, so every surviving campaign yields the same
    # (empty) worklist and the only variable left is the exclusion.
    gmail_archive.inbound_since = lambda settings, email, after=None: []
    gmail_archive.sent_to = lambda settings, email, days: []
    return calls


def _pending_names(settings, names: list[str]) -> set[str]:
    _stub_engine(names)
    out = campaign.pending(settings)
    return {c["campaign"] for c in out["campaigns"]}


def test_pending_skips_every_excluded_name() -> None:
    names = [FIRST, BATCH2, OTHER]

    # Old shape: one excluded, and the batch2 sibling still reaches the operator
    # — which is precisely the month-long bug, reproduced.
    assert _pending_names(_settings(FIRST), names) == {BATCH2, OTHER}

    # Both listed: only the unrelated campaign survives.
    assert _pending_names(_settings(f"{FIRST}, {BATCH2}"), names) == {OTHER}

    # Nothing excluded.
    assert _pending_names(_settings(""), names) == {FIRST, BATCH2, OTHER}

    print("OK: pending() skips every listed name, and only those")


def test_contact_level_guards() -> None:
    """`_pack_send_preamble` (send_reminder / send_sms) and `send_first` carry
    their own copy of the check — a contact reached by id never goes through
    `pending()`, so a list that only worked there would leave both pack senders
    firing into a finished campaign."""
    s = _settings(f"{FIRST}, {BATCH2}")

    for name in (FIRST, BATCH2):
        _stub_engine([name])
        _c, _pack, err = campaign._pack_send_preamble(s, f"contact-{name}")
        assert err is not None and "excluded" in err["error"], (name, err)
        assert err["ok"] is False

        _stub_engine([name])
        out = campaign.send_first(s, f"contact-{name}", commit=False)
        assert out["ok"] is False and "excluded" in out["error"], (name, out)

    # The prefix trap at the contact level too: with ONLY the short name
    # excluded, the batch2 contact must get past the exclusion gate. It fails
    # later, on the missing pack — a different refusal, which is the point.
    s_one = _settings(FIRST)
    _stub_engine([BATCH2])
    out = campaign.send_first(s_one, f"contact-{BATCH2}", commit=False)
    assert out["ok"] is False, out
    assert "excluded" not in out["error"], (
        "a campaign sharing a prefix with an excluded one must not be refused "
        "as excluded: %r" % out
    )
    assert out.get("skipped") is True and "NO CAMPAIGN PACK" in out["error"], (
        "it must get PAST the exclusion gate and fail on the missing pack — "
        "asserting only 'not excluded' would also pass on 'contact not "
        "found': %r" % out
    )

    # A contact whose campaign name came back blank is not "excluded" either —
    # "" must never be a member of the set.
    _stub_engine([OTHER])
    out = campaign.send_first(_settings(""), f"contact-{OTHER}", commit=False)
    assert "excluded" not in (out.get("error") or ""), out
    assert out.get("skipped") is True, out

    print("OK: send_first + _pack_send_preamble honour the full list, exactly")


def test_manifest_carries_the_string_through() -> None:
    """The manifest table accepts several names and `settings_overrides` hands
    the raw string to Settings — the parse happens in ONE place (the property),
    never twice."""
    m = manifest.Manifest.model_validate(
        {"campaigns": {"excluded_campaign": f"{FIRST}, {BATCH2}"}}
    )
    ov = manifest.settings_overrides(m)
    assert ov["excluded_campaign"] == f"{FIRST}, {BATCH2}", ov
    assert _parse(ov["excluded_campaign"]) == {FIRST, BATCH2}

    # And the single-name manifest a clone already has on disk.
    m1 = manifest.Manifest.model_validate(
        {"campaigns": {"excluded_campaign": FIRST}}
    )
    assert _parse(manifest.settings_overrides(m1)["excluded_campaign"]) == {FIRST}
    print("OK: manifest table → settings override → one parse, at the property")


def test_config_report_renders_several_readably() -> None:
    """`cs config` is where an operator checks this. Two names crammed as
    `a,b` is a value the reader has to parse by eye."""
    cell = config_report._cell(
        {"name": "excluded_campaign", "secret": False,
         "value": f"{FIRST},{BATCH2}"}
    )
    assert cell == f"{FIRST}, {BATCH2}", cell
    # One name is printed unchanged; empty still reads as empty, not as "".
    assert config_report._cell(
        {"name": "excluded_campaign", "secret": False, "value": FIRST}
    ) == FIRST
    assert config_report._cell(
        {"name": "excluded_campaign", "secret": False, "value": ""}
    ) == "(empty)"
    # A field that is NOT a list keeps its value byte for byte — the pretty
    # printer must not reformat, say, a comma inside a display name.
    assert config_report._cell(
        {"name": "email_address", "secret": False, "value": "a,b"}
    ) == "a,b"
    print("OK: cs config prints several excluded campaigns readably")


def main() -> int:
    test_parsing()
    test_prefix_is_not_a_match()
    test_pending_skips_every_excluded_name()
    test_contact_level_guards()
    test_manifest_carries_the_string_through()
    test_config_report_renders_several_readably()
    print("test_excluded_campaigns: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
