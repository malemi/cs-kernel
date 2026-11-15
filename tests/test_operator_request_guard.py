"""Exercise the installed alias-aware projection through the explicit operator caller."""
import copy
import unittest
from unittest.mock import patch

from cs import config, rpc, task_assignment as assignment
from test_task_assignment import KEY, OTHER, malformed_observation, projection, settings


def manual():
    return projection("needs-assignment", complete=False) | {
        "source_owner_uid": "operator", "reason": "NEEDS_HUMAN_VERIFICATION",
        "current_message_ids": [KEY], "reply_evidence": [{"complete": True,
        "judgement": "MEMBER_ACTIVITY_REQUIRES_HUMAN_VERIFICATION"}]}


class OperatorRequestGuard(unittest.TestCase):
    def test_real_project_operator_flag_preserves_manual_and_independent_holds(self):
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        for mode in ("normal", "conflict", "unknown", "independent-hold", "incomplete-authority", "offline"):
            primary = manual()
            peer = projection() | {"actor_uid": "peer"}
            if mode == "conflict":
                peer.update(state="conflict", hold_auto_reply=True)
            elif mode == "unknown":
                peer.update(state="unknown", complete=False, hold_auto_reply=True)
            elif mode == "independent-hold":
                peer.update(state="needs-assignment", complete=False, hold_auto_reply=True, reason="OTHER_HOLD")
            elif mode == "incomplete-authority":
                primary = malformed_observation()
            def call(account, method, params, **kwargs):
                self.assertEqual(method, "tasks.assignment.project")
                if mode == "offline" and account.engine_owner_uid == "peer":
                    raise ConnectionError("offline fixture")
                return copy.deepcopy(primary if account.engine_owner_uid == "operator" else peer)
            with self.subTest(mode=mode), patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call):
                result = assignment.project(selected, KEY, operator=True)
                self.assertTrue(result["hold_auto_reply"])
                if mode == "normal":
                    self.assertEqual(assignment.operator_guard(selected, KEY, KEY)["state"], "needs-assignment")
                    with self.assertRaises(assignment.AssignmentUnavailable):
                        assignment.guard(selected, KEY)
                else:
                    with self.assertRaises(assignment.AssignmentUnavailable):
                        assignment.operator_guard(selected, KEY, KEY)

    def test_real_alias_fallback_cannot_clear_an_independent_canonical_hold(self):
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        primary = manual() | {"authoritative_thread_key": OTHER,
            "component_thread_keys": sorted([KEY, OTHER]), "component_scope_present": True}
        for held in (False, True):
            calls = []
            def call(account, method, params, **kwargs):
                key = params["thread_key"]
                calls.append((account.engine_owner_uid, key))
                if account.engine_owner_uid == "operator":
                    return copy.deepcopy(primary)
                response = projection() | {"actor_uid": "peer", "thread_key": key,
                    "authoritative_thread_key": key, "component_thread_keys": [key], "component_scope_present": False}
                if held and key == OTHER:
                    response.update(state="needs-assignment", complete=False, hold_auto_reply=True, reason="OTHER_HOLD")
                return response
            with self.subTest(held=held), patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call):
                if held:
                    with self.assertRaises(assignment.AssignmentUnavailable):
                        assignment.operator_guard(selected, KEY, KEY)
                else:
                    self.assertTrue(assignment.operator_guard(selected, KEY, KEY)["hold_auto_reply"])
                self.assertIn(("peer", OTHER), calls)


if __name__ == "__main__":
    unittest.main()
