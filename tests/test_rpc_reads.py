"""Real multiplexed transport and conservative projection comparisons."""
from __future__ import annotations

import asyncio
import base64
import copy
import contextlib
import subprocess
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import websockets
from cs import config, engine_view, rpc, rpc_reads, task_assignment
from test_task_assignment import projection, settings, task, KEY

TOKEN = "fixture." + base64.urlsafe_b64encode(json.dumps({"exp": int(time.time()) + 3600}).encode()).decode().rstrip("=") + ".fixture"


class Transport(unittest.IsolatedAsyncioTestCase):
    @contextlib.contextmanager
    def completion_measurements(self, label):
        from cs import observability_producers
        values = {'case': label, 'reads': [], 'projections': [], 'diagnostics': []}
        original_read, original_projection, original_emit = rpc_reads.read_many, task_assignment.projections, observability_producers.emit
        def read(*args, **kwargs):
            result = original_read(*args, **kwargs)
            values['reads'].extend(row.completion for row in result.values() if row.completion is not None)
            return result
        def projection_call(*args, **kwargs):
            entered = time.monotonic()
            try:
                return original_projection(*args, **kwargs)
            finally:
                values['projections'].append({'entry_monotonic': entered, 'elapsed_us': rpc_reads._elapsed_us(entered)})
        def emit(*args, **kwargs):
            entered = time.monotonic()
            try:
                return original_emit(*args, **kwargs)
            finally:
                values['diagnostics'].append({'elapsed_us': rpc_reads._elapsed_us(entered), 'timing': (kwargs.get('causal') or {}).get('timing')})
        with patch.object(rpc_reads, 'read_many', side_effect=read), patch.object(task_assignment, 'projections', side_effect=projection_call), patch.object(observability_producers, 'emit', side_effect=emit):
            try:
                yield values
            finally:
                print('RPC_COMPLETION ' + json.dumps(values, sort_keys=True), file=sys.stderr)
    async def run_batch(self, keys, delays, *, request_timeout=1, batch_timeout=2, disconnected=False, stall_close=False):
        clients, ids = [], []
        stats = {"connections": 0, "active": 0, "maximum": 0, "replies": []}
        original = rpc.EngineClient

        class Client(original):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                clients.append(self)

            async def __aexit__(self, *args):
                if stall_close:
                    await asyncio.sleep(99)
                await super().__aexit__(*args)

        async def handler(ws):
            stats["connections"] += 1
            replies = []

            async def respond(frame):
                stats["active"] += 1
                stats["maximum"] = max(stats["maximum"], stats["active"])
                try:
                    await asyncio.sleep(delays[frame["params"]["thread_id"]])
                    if disconnected:
                        await ws.close()
                    else:
                        await ws.send(json.dumps({"jsonrpc": "2.0", "id": frame["id"], "result": {"key": frame["params"]["thread_id"]}}))
                        stats["replies"].append(frame["params"]["thread_id"])
                finally:
                    stats["active"] -= 1

            try:
                async for raw in ws:
                    frame = json.loads(raw)
                    if frame["method"] == "system.capabilities":
                        await ws.send(json.dumps({"jsonrpc": "2.0", "id": frame["id"], "result": {"observability": 1}}))
                        continue
                    ids.append(frame["id"])
                    replies.append(asyncio.create_task(respond(frame)))
            except websockets.ConnectionClosed:
                pass
            finally:
                for reply in replies:
                    reply.cancel()
                await asyncio.gather(*replies, return_exceptions=True)

        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            selected = SimpleNamespace(engine_ws_url=f"ws://127.0.0.1:{port}", engine_owner_uid="operator")
            with patch.object(rpc.auth, "get_id_token", return_value=TOKEN), patch.object(rpc, "EngineClient", Client):
                started = time.monotonic()
                result = await rpc_reads._read(selected, "emails.list_by_thread",
                    {key: {"thread_id": key} for key in keys}, request_timeout, batch_timeout, None)
                elapsed = time.monotonic() - started
        self.assertEqual(stats["connections"], 1)
        self.assertLessEqual(stats["maximum"], 4)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(client._recv_task.done() for client in clients))
        self.assertTrue(all(not client._pending for client in clients))
        self.assertEqual(list(result), keys)
        return result, stats, elapsed, ids

    async def test_one_connection_out_of_order_unique_correlation_four_active(self):
        keys = [str(i) for i in range(11)]
        results, stats, _, ids = await self.run_batch(keys, {key: 0.01 * (4 - int(key) % 4) for key in keys})
        self.assertEqual(stats["maximum"], 4)
        self.assertEqual(len(ids), 11)
        self.assertNotEqual(stats["replies"], keys)
        self.assertEqual([results[key].value["key"] for key in keys], keys)
        self.assertTrue(all(row.error is None for row in results.values()))

    async def test_shared_timeout_retains_completed_and_all_missing_unstarted(self):
        keys = [str(i) for i in range(12)]
        results, _, elapsed, ids = await self.run_batch(keys, {key: 0.001 if key == "0" else 5 for key in keys}, request_timeout=0.04)
        self.assertEqual(results["0"].value, {"key": "0"})
        self.assertTrue(all(results[key].error is not None for key in keys[1:]))
        self.assertLess(len(ids), len(keys))
        self.assertLess(elapsed, 1)

    async def test_batch_deadline_closes_stalled_socket_and_marks_every_key(self):
        keys = [str(i) for i in range(8)]
        results, _, elapsed, _ = await self.run_batch(keys, {key: 5 for key in keys}, request_timeout=3, batch_timeout=0.04)
        self.assertTrue(all(row.error is not None for row in results.values()))
        self.assertLess(elapsed, 1)

    async def test_disconnect_keeps_all_unanswered_explicit(self):
        results, _, elapsed, _ = await self.run_batch(["a", "b"], {"a": 0.001, "b": 2}, disconnected=True)
        self.assertTrue(all(row.error is not None for row in results.values()))
        self.assertLess(elapsed, 1)

    async def test_stalled_close_is_bounded_and_reader_is_awaited(self):
        with patch.object(rpc_reads, "CLOSE_SECONDS", 0.02):
            results, _, elapsed, _ = await self.run_batch(["a"], {"a": 0.001}, stall_close=True)
        self.assertEqual(results["a"].value, {"key": "a"})
        self.assertLess(elapsed, 1)

    async def test_external_cancellation_awaits_client_reader(self):
        clients = []
        original = rpc.EngineClient
        class Client(original):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                clients.append(self)
        async def handler(ws):
            async for _ in ws:
                pass
        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            selected = SimpleNamespace(engine_ws_url=f"ws://127.0.0.1:{port}", engine_owner_uid="operator")
            with patch.object(rpc.auth, "get_id_token", return_value=TOKEN), patch.object(rpc, "EngineClient", Client):
                active = asyncio.create_task(rpc_reads._read(selected, "emails.list_by_thread", {"a": {"thread_id": "a"}}, 1, 2, None))
                while not clients or not clients[0]._pending:
                    await asyncio.sleep(0.001)
                active.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await active
        self.assertTrue(clients[0]._recv_task.done())
        self.assertFalse(clients[0]._pending)

    async def test_isolated_auth_and_dns_are_killed_within_projection_bound(self):
        import os
        import tempfile
        dispatch = []
        async def handler(ws):
            async for frame in ws:
                dispatch.append(frame)
        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            for phase in ("auth", "dns"):
                with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                    marker = Path(directory) / "phase-started"
                    blocked = "lambda *a,**kw:(Path(" + repr(str(marker)) + ").write_text(str(os.getpid())),time.sleep(2)," + (repr(TOKEN) if phase == "auth" else "original(*a,**kw)") + ")[2]"
                    command = (sys.executable, "-c", "import os,socket,time; from pathlib import Path; "
                        "from cs import auth,rpc_reads; original=socket.getaddrinfo; " +
                        ("auth.get_id_token=" + blocked if phase == "auth" else
                         "auth.get_id_token=lambda selected:" + repr(TOKEN) + "; socket.getaddrinfo=" + blocked) +
                        "; rpc_reads._isolated_main()")
                    selected = settings().model_copy(update={"engine_ws_url": f"ws://localhost:{port}"})
                    with patch.object(rpc_reads, "READ_COMMAND", command), patch.object(rpc_reads, "CLOSE_SECONDS", 0.01), patch.object(task_assignment, "PROJECTION_SECONDS", 0.5), self.completion_measurements("auth_dns_" + phase):
                        started = time.monotonic()
                        result = await asyncio.to_thread(task_assignment.projections, selected, [KEY])
                        elapsed = time.monotonic() - started
                    self.assertTrue(marker.exists(), "actual blocking phase must begin")
                    self.assertLess(elapsed, 0.5)
                    self.assertEqual(result[KEY]["state"], "unknown")
                    self.assertTrue(result[KEY]["hold_auto_reply"])
                    with self.assertRaises(ProcessLookupError):
                        os.kill(int(marker.read_text()), 0)
                    self.assertEqual(dispatch, [])

    async def test_isolated_assignment_opt_in_exceeds_former_cap_and_cleanup_stays_finite(self):
        import os
        import tempfile
        async def handler(ws):
            async for raw in ws:
                frame = json.loads(raw)
                await asyncio.sleep(0.65)
                try:
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": frame["id"], "result": {"verified": True}}))
                except websockets.ConnectionClosed:
                    pass
        self.assertEqual(rpc_reads.read_many.__kwdefaults__["request_timeout"], 60)
        self.assertEqual(rpc_reads.read_many.__kwdefaults__["batch_timeout"], 90)
        async with websockets.serve(handler, "127.0.0.1", 0) as server, self.fixture_directory() as directory:
            marker = Path(directory) / "child"
            command = (sys.executable, "-c", "import os; from pathlib import Path; "
                "Path(" + repr(str(marker)) + ").write_text(str(os.getpid())); "
                "from cs.rpc_reads import _isolated_main; _isolated_main()")
            selected = settings().model_copy(update={"engine_ws_url": f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"})
            cases = [("tasks.assignment.project", 1.5, 1.8, True),
                     ("tasks.assignment.project", 0.6, 0.9, False),
                     ("emails.list_by_thread", 1.5, 1.8, False)]
            for method, request, batch, success in cases:
                with self.subTest(method=method, request=request), patch.object(rpc_reads, "READ_COMMAND", command), patch.object(rpc_reads, "REQUEST_SECONDS", 0.6), patch.object(rpc_reads, "BATCH_SECONDS", 0.9), patch.object(rpc_reads, "ASSIGNMENT_REQUEST_SECONDS", 1.5), patch.object(rpc_reads, "ASSIGNMENT_BATCH_SECONDS", 1.8), patch.object(rpc_reads, "CLOSE_SECONDS", 0.01):
                    started = time.monotonic()
                    outcome = (await asyncio.to_thread(rpc_reads.read_many, selected, method, {KEY: {}},
                        request_timeout=request, batch_timeout=batch, token_cache={"operator": TOKEN}))[KEY]
                    self.assertEqual(outcome.error is None, success)
                    self.assertLess(time.monotonic() - started, 1.85)
                    with self.assertRaises(ProcessLookupError):
                        os.kill(int(marker.read_text()), 0)
                    if success:
                        self.assertEqual(outcome.value, {"verified": True})

    async def test_partial_or_malformed_worker_output_holds_every_key(self):
        for output in ("{", '{"outcomes":{},"token":null}', '{"outcomes":{"a":{"value":{},"error":null}},"token":null}'):
            command = (sys.executable, "-c", "import sys; sys.stdin.read(); print(" + repr(output) + ")")
            with self.subTest(output=output), patch.object(rpc_reads, "READ_COMMAND", command):
                outcomes = await asyncio.to_thread(rpc_reads.read_many, settings(), "tasks.assignment.project", {"a": {}, "b": {}})
            self.assertEqual(list(outcomes), ["a", "b"])
            self.assertTrue(all(row.error is not None for row in outcomes.values()))

    async def projection_fixture(self, *, slow_account=None, alias=False):
        from cs import cli, gmail_archive
        from datetime import timedelta
        from test_task_assignment import NOW, OTHER, inbound
        import contextlib
        import io
        fresh = "<PROVA-001@example.test>"
        old = "<000-history@example.test>"
        older = "<001-history@example.test>"
        noise = "<zzz-newsletter@example.test>"
        rows = [inbound(old, date=NOW - timedelta(days=2)), inbound(fresh, date=NOW - timedelta(days=1)),
                inbound(older, date=NOW - timedelta(days=3)), inbound(noise, date=NOW)]
        stats = {"active": 0, "maximum": 0, "dispatch": [], "complete": []}
        tasks = set()
        fresh_ready = asyncio.Event()

        async def handler(ws):
            uid = ws.request.path.rsplit("/", 1)[-1]
            async def respond(frame):
                key = frame["params"]["thread_key"]
                stats["dispatch"].append((uid, key))
                stats["active"] += 1
                stats["maximum"] = max(stats["maximum"], stats["active"])
                try:
                    if key == fresh:
                        if sum(candidate == fresh for _, candidate in stats["dispatch"]) == 4:
                            fresh_ready.set()
                        await fresh_ready.wait()
                    await asyncio.sleep(1.2 if key == old and (slow_account is None or uid == slow_account) else 0.002)
                    shared = task() | {"thread_key": OTHER}
                    state = "assigned" if alias and (uid == "operator" or key == OTHER) else "normal"
                    value = projection(state, task=shared if state == "assigned" else None) | {
                        "actor_uid": uid, "thread_key": key, "authoritative_thread_key": OTHER if alias and uid == "operator" else key,
                        "component_thread_keys": sorted([key, OTHER]) if alias and uid == "operator" and key != OTHER else [key],
                        "component_scope_present": uid == "operator"}
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": frame["id"], "result": value}))
                    stats["complete"].append((uid, key))
                except websockets.ConnectionClosed:
                    pass
                finally:
                    stats["active"] -= 1
            async for raw in ws:
                frame = json.loads(raw)
                if frame["method"] == "system.capabilities":
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": frame["id"], "result": {"observability": 1}}))
                    continue
                pending = asyncio.create_task(respond(frame))
                tasks.add(pending)
                pending.add_done_callback(tasks.discard)

        async with websockets.serve(handler, "127.0.0.1", 0) as server, self.fixture_directory() as directory:
            port = server.sockets[0].getsockname()[1]
            selected = settings().model_copy(update={"engine_ws_url": f"ws://127.0.0.1:{port}",
                "accounts": "p1:p1,p2:p2,p3:p3,duplicate:p1", "db_path": str(Path(directory) / "state.db")})
            output = io.StringIO()
            authentication = Path(directory) / "authentication"
            command = (sys.executable, "-c", "from pathlib import Path; from cs import auth,rpc_reads; "
                "original=auth.get_id_token; "
                "auth.get_id_token=lambda selected:(Path(" + repr(str(authentication)) + ").open('a').write(selected.engine_owner_uid+'\\n'),original(selected))[1]; "
                "rpc_reads._isolated_main()")
            for uid in ("operator", "p1", "p2", "p3"):
                (Path(directory) / (uid + ".json")).write_text(json.dumps({"uid": uid, "id_token": TOKEN}))
            def load(**kwargs):
                uid = kwargs.get("engine_owner_uid", "operator")
                return selected.model_copy(update={**kwargs, "firebase_web_api_key": "fixture-public-key",
                    "token_cache_path": str(Path(directory) / (uid + ".json"))})
            views = {noise: engine_view.ThreadView(noise, {int(NOW.timestamp())}, 1)}
            started = time.monotonic()
            with patch.object(config, "load", side_effect=load), patch.object(rpc_reads, "READ_COMMAND", command), patch.object(gmail_archive, "inbound_recent", return_value=rows[:1] if alias else rows), patch.object(gmail_archive, "sent_recent", return_value=[]), patch.object(engine_view, "classify", return_value=(views, None)), patch.object(engine_view, "settled", return_value=({}, None)), patch.object(rpc_reads, "REQUEST_SECONDS", 0.7), patch.object(rpc_reads, "ASSIGNMENT_REQUEST_SECONDS", 0.7), patch.object(rpc_reads, "CLOSE_SECONDS", 0.01), patch.object(task_assignment, "PROJECTION_SECONDS", 3), contextlib.redirect_stdout(output), self.completion_measurements("projection_" + str(slow_account)):
                code = await asyncio.to_thread(cli.main, ["unanswered", "--json", "--all-buckets"])
            elapsed = time.monotonic() - started
            self.assertEqual(sorted(authentication.read_text().splitlines()), ["operator", "p1", "p2", "p3"])
            stats["elapsed_seconds"] = elapsed
            result = json.loads(output.getvalue())
            for pending in list(tasks):
                pending.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self.assertLessEqual(stats["maximum"], 4)
        self.assertLess(elapsed, 3)
        return result, stats, code, fresh, old, older, noise

    async def scheduled_fixture(self, *, count=26, alias=False, stalled=False, asymmetric=False, budget=4, alias_after_first=False, admission=None, contended=False, actors=2, response=None, read_batch=None):
        from test_task_assignment import OTHER
        keys = [f"<batch-{index:02}@example.test>" for index in range(count)]
        stats = {"active": 0, "maximum": 0, "per_actor": {}, "actor_maximum": {}, "dispatch": [], "complete": [], "events": []}
        responders = set()
        backend_locks = {}
        stats["backend_deadline_failures"] = []
        actor_uids = ["operator", "peer", "p2", "p3"][:actors]
        allowed = task_assignment.PER_ACCOUNT_CONCURRENCY if admission is None else admission
        loop = asyncio.get_running_loop()
        async def handler(ws):
            uid = ws.request.path.rsplit("/", 1)[-1]
            async def respond(frame):
                key = frame["params"]["thread_key"]
                stats["dispatch"].append((uid, key))
                stats["events"].append(("start", uid, key, time.monotonic()))
                stats["active"] += 1
                stats["per_actor"][uid] = stats["per_actor"].get(uid, 0) + 1
                stats["maximum"] = max(stats["maximum"], stats["active"])
                stats["actor_maximum"][uid] = max(stats["actor_maximum"].get(uid, 0), stats["per_actor"][uid])
                try:
                    unavailable = False
                    if contended:
                        try:
                            async with asyncio.timeout(0.18):
                                async with backend_locks.setdefault(uid, asyncio.Lock()):
                                    await asyncio.sleep(0.12)
                        except TimeoutError:
                            unavailable = True
                            stats["backend_deadline_failures"].append((uid, key))
                    else:
                        await asyncio.sleep((0.01 if uid == "operator" else 0.25) if asymmetric else 0.7 if stalled and uid == "peer" and key != keys[0] else 0.02 if stalled else 0.2)
                    uses_alias = alias and (not alias_after_first or key != keys[0])
                    value = projection("assigned" if uses_alias and (uid == "operator" or key == OTHER) else "normal",
                                       task=task() | {"thread_key": OTHER} if uses_alias and (uid == "operator" or key == OTHER) else None)
                    value.update(actor_uid=uid, thread_key=key, authoritative_thread_key=OTHER if uses_alias and uid == "operator" else key,
                                 component_thread_keys=sorted({key, OTHER}) if uses_alias and uid == "operator" else [key],
                                 component_scope_present=uid == "operator")
                    if unavailable:
                        value.update(state="unknown", complete=False, hold_auto_reply=True, reason="SOURCE_UNAVAILABLE")
                    if response is not None:
                        value = response(uid, key, sum(pair == (uid, key) for pair in stats["dispatch"]), value)
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": frame["id"], "result": value}))
                    stats["complete"].append((uid, key))
                    stats["events"].append(("complete", uid, key, time.monotonic()))
                except websockets.ConnectionClosed:
                    pass
                finally:
                    stats["active"] -= 1
                    stats["per_actor"][uid] -= 1
            async for raw in ws:
                frame = json.loads(raw)
                if frame["method"] == "system.capabilities":
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": frame["id"], "result": {"observability": 1}}))
                    continue
                pending = asyncio.create_task(respond(frame))
                responders.add(pending)
                pending.add_done_callback(responders.discard)
        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            selected = settings().model_copy(update={"engine_ws_url": f"ws://127.0.0.1:{port}", "accounts": ",".join(uid + ":" + uid for uid in actor_uids[1:])})
            def many(account, method, requests, **kwargs):
                return asyncio.run_coroutine_threadsafe(rpc_reads._read(account, method, requests, 0.12 if stalled else 0.5,
                    budget if read_batch is None else read_batch, kwargs["deadline"], kwargs.get("token_cache")), loop).result()
            started = time.monotonic()
            with patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc.auth, "get_id_token", return_value=TOKEN), patch.object(rpc_reads, "read_many", side_effect=many), patch.object(rpc_reads, "CLOSE_SECONDS", 0.001), patch.object(task_assignment, "PROJECTION_SECONDS", budget), patch.object(task_assignment, "PER_ACCOUNT_CONCURRENCY", allowed):
                result = await asyncio.to_thread(task_assignment.projections, selected, keys)
            stats["elapsed"] = time.monotonic() - started
            for pending in list(responders):
                pending.cancel()
            await asyncio.gather(*responders, return_exceptions=True)
        self.assertLessEqual(stats["maximum"], 4)
        self.assertTrue(all(value <= allowed for value in stats["actor_maximum"].values()))
        self.assertEqual(set(stats["dispatch"][:actors]), {(uid, keys[0]) for uid in actor_uids})
        return result, stats, keys

    async def test_transient_source_failure_recovers_once_with_fresh_real_response(self):
        def response(uid, key, attempt, value):
            if uid == "peer" and attempt == 1:
                value.update(state="unknown", complete=False, hold_auto_reply=True, reason="SOURCE_UNAVAILABLE")
            return value
        result, stats, keys = await self.scheduled_fixture(count=3, actors=4, response=response)
        self.assertTrue(all(row["state"] == "normal" and row["complete"] for row in result.values()))
        for key in keys:
            self.assertEqual(stats["dispatch"].count(("peer", key)), 2)
        self.assertTrue(all(value == 1 for value in stats["actor_maximum"].values()))
        self.assertEqual(stats["maximum"], 4)

    async def test_repeated_source_failure_stays_held_after_exactly_two_attempts(self):
        def response(uid, key, attempt, value):
            return value | {"state": "unknown", "complete": False, "hold_auto_reply": True, "reason": "SOURCE_UNAVAILABLE"}
        result, stats, keys = await self.scheduled_fixture(count=2, response=response)
        self.assertTrue(all(row["state"] == "unknown" and row["hold_auto_reply"] for row in result.values()))
        self.assertEqual(len(stats["dispatch"]), 8)
        self.assertTrue(all(stats["dispatch"].count((uid, key)) == 2 for uid in ("operator", "peer") for key in keys))

    async def test_canonical_recovery_budget_is_shared_across_alias_roots(self):
        from test_task_assignment import OTHER
        def response(uid, key, attempt, value):
            if uid == "peer" and key == OTHER:
                value.update(state="unknown", complete=False, hold_auto_reply=True, reason="SOURCE_UNAVAILABLE")
            return value
        result, stats, keys = await self.scheduled_fixture(count=3, alias=True, response=response)
        self.assertEqual(stats["dispatch"].count(("peer", OTHER)), 2)
        self.assertTrue(all(row["state"] == "unknown" and row["hold_auto_reply"] for row in result.values()))

    async def test_noneligible_typed_and_invalid_responses_never_retry(self):
        changes = [
            {"actor_uid": "spoof", "state": "unknown", "complete": False, "hold_auto_reply": True, "reason": "SOURCE_UNAVAILABLE"},
            {"current_message_ids": None, "state": "unknown", "complete": False, "hold_auto_reply": True, "reason": "SOURCE_UNAVAILABLE"},
            {"state": "needs-assignment", "complete": False, "hold_auto_reply": True, "reason": "NEEDS_HUMAN_VERIFICATION"},
            {"state": "conflict", "complete": False, "hold_auto_reply": True, "reason": "SOURCE_UNAVAILABLE"},
            {"state": "unknown", "complete": False, "hold_auto_reply": True, "reason": "REPLY_SOURCE_UNAVAILABLE"},
        ]
        for change in changes:
            with self.subTest(change=change):
                result, stats, keys = await self.scheduled_fixture(count=1, response=lambda uid, key, attempt, value: value | change)
                self.assertEqual(len(stats["dispatch"]), 2)
                self.assertTrue(result[keys[0]]["hold_auto_reply"])

    async def test_recovery_exhaustion_shares_original_scaled_deadline(self):
        def response(uid, key, attempt, value):
            return value | {"state": "unknown", "complete": False, "hold_auto_reply": True, "reason": "SOURCE_UNAVAILABLE"}
        result, stats, keys = await self.scheduled_fixture(count=4, budget=0.65, response=response)
        self.assertLess(stats["elapsed"], 0.85)
        self.assertTrue(all(row["state"] == "unknown" and row["hold_auto_reply"] for row in result.values()))
        self.assertTrue(all(stats["dispatch"].count((uid, key)) <= 2 for uid in ("operator", "peer") for key in keys))

    async def test_four_distinct_actors_use_global_capacity_and_complete_fifo_work(self):
        result, stats, keys = await self.scheduled_fixture(count=7, actors=4)
        self.assertEqual(list(result), keys)
        self.assertTrue(all(row["state"] == "normal" and row["complete"] for row in result.values()))
        self.assertEqual(len(stats["complete"]), len(keys) * 4)
        self.assertEqual(stats["maximum"], 4)
        self.assertTrue(all(value == 1 for value in stats["actor_maximum"].values()))

    async def test_single_actor_admission_avoids_backend_deadline_including_lock_wait(self):
        overlapping, old_stats, keys = await self.scheduled_fixture(count=6, admission=2, contended=True, budget=3.6)
        self.assertTrue(old_stats["backend_deadline_failures"])
        self.assertTrue(any(row["state"] == "unknown" and row["hold_auto_reply"] for row in overlapping.values()))
        complete, stats, keys = await self.scheduled_fixture(count=6, contended=True, budget=3.6)
        self.assertEqual(stats["backend_deadline_failures"], [])
        self.assertTrue(all(row["state"] == "normal" and row["complete"] for row in complete.values()))
        self.assertEqual(len(stats["complete"]), len(keys) * 2)
        self.assertTrue(all(value == 1 for value in stats["actor_maximum"].values()))
        self.assertLess(stats["elapsed"], 3.6)

    async def test_measured_global_capacity_doubles_without_changing_read_limits(self):
        self.assertEqual(task_assignment.PROJECTION_SECONDS, 3600)
        self.assertEqual((rpc_reads.REQUEST_SECONDS, rpc_reads.BATCH_SECONDS, rpc_reads.CONCURRENCY,
                          task_assignment.PER_ACCOUNT_CONCURRENCY), (60, 90, 4, 1))
        short, _, keys = await self.scheduled_fixture(count=8, budget=1.3)
        self.assertTrue(any(row["state"] == "unknown" and row["hold_auto_reply"] for row in short.values()))
        complete, stats, keys = await self.scheduled_fixture(count=8, budget=2.6)
        self.assertTrue(all(row["state"] == "normal" and row["complete"] for row in complete.values()))
        self.assertEqual(len(stats["complete"]), len(keys) * 2)
        self.assertLess(stats["elapsed"], 2.6)

    async def test_canonical_keeps_origin_priority_before_queued_historical_roots(self):
        result, stats, keys = await self.scheduled_fixture(count=7, alias=True, alias_after_first=True)
        from test_task_assignment import OTHER
        peer_dispatch = [key for uid, key in stats["dispatch"] if uid == "peer"]
        self.assertLess(peer_dispatch.index(OTHER), peer_dispatch.index(keys[4]))
        self.assertEqual(result[keys[0]]["state"], "normal")
        self.assertTrue(all(result[key]["state"] == "assigned" and result[key]["hold_auto_reply"] for key in keys[1:]))
        self.assertEqual(sum(uid == "peer" and key == OTHER for uid, key in stats["complete"]), 1)

    async def test_asymmetric_actor_uses_free_positions_before_slow_roots_finish(self):
        result, stats, keys = await self.scheduled_fixture(count=7, asymmetric=True)
        self.assertTrue(all(row["state"] == "normal" for row in result.values()))
        events = {(kind, uid, key): at for kind, uid, key, at in stats["events"]}
        self.assertLess(events[("complete", "operator", keys[4])], events[("complete", "peer", keys[1])])
        self.assertEqual(stats["actor_maximum"]["peer"], 1)
        self.assertEqual(stats["maximum"], 2)

    async def test_canonical_scopes_share_pipeline_capacity_and_keep_assignment(self):
        result, stats, keys = await self.scheduled_fixture(count=7, alias=True)
        from test_task_assignment import OTHER
        self.assertTrue(all(row["state"] == "assigned" and row["hold_auto_reply"] for row in result.values()))
        self.assertEqual(sum(uid == "peer" and key == OTHER for uid, key in stats["complete"]), 1)
        self.assertEqual(stats["maximum"], 2)

    async def test_timeout_reserves_surviving_remote_work_and_stops_actor_replacement(self):
        result, stats, keys = await self.scheduled_fixture(count=9, stalled=True)
        self.assertEqual(result[keys[0]]["state"], "normal")
        self.assertTrue(all(result[key]["state"] == "unknown" and result[key]["hold_auto_reply"] for key in keys[1:]))
        self.assertTrue(all(("operator", key) in stats["complete"] for key in keys))
        self.assertEqual({key for uid, key in stats["dispatch"] if uid == "peer"}, set(keys[:2]))
        self.assertEqual(stats["maximum"], 2)

    def fixture_directory(self):
        import contextlib
        import tempfile
        @contextlib.asynccontextmanager
        async def directory():
            with tempfile.TemporaryDirectory() as value:
                yield value
        return directory()

    async def test_actual_cli_recent_useful_work_completes_four_sparse_peers_before_history(self):
        result, stats, code, fresh, old, older, noise = await self.projection_fixture()
        self.assertEqual([key for _, key in stats["dispatch"][:4]], [fresh] * 4)
        self.assertEqual({uid for uid, key in stats["complete"] if key == fresh}, {"operator", "p1", "p2", "p3"})
        self.assertIn(fresh, [row["thread_key"] for row in result["open"]])
        held = {row["thread_key"]: row for row in result["human_work"]}
        self.assertTrue({old, older, noise}.issubset(held))
        self.assertIn("capacity deferred", held[older]["assignment"]["reason"])
        self.assertNotEqual(code, 0)
        self.assertTrue(result["assignment_incomplete"])

    async def test_timed_out_scope_keeps_other_healthy_queued_scopes(self):
        result, stats, _, fresh, old, older, noise = await self.projection_fixture(slow_account="p3")
        self.assertTrue({("operator", older), ("p1", older), ("p2", older)}.issubset(stats["complete"]))
        self.assertNotIn(("p3", noise), stats["dispatch"])
        self.assertLessEqual(sum(uid == "p3" and key != fresh for uid, key in stats["dispatch"]), 2)
        self.assertEqual(stats["maximum"], 4)
        self.assertNotIn(fresh, [row["thread_key"] for row in result["human_work"]])
        self.assertEqual({uid for uid, key in stats["complete"] if key == fresh}, {"operator", "p1", "p2", "p3"})

    async def test_actual_sparse_peer_alias_reads_shared_task_without_unholding(self):
        result, stats, _, _, old, _, _ = await self.projection_fixture(slow_account="absent", alias=True)
        from test_task_assignment import OTHER
        self.assertEqual(result["open"], [])
        self.assertEqual(result["human_work"][0]["assignment"]["state"], "assigned")
        self.assertEqual(result["human_work"][0]["assignment"]["thread_key"], old)
        self.assertEqual(result["human_work"][0]["assignment"]["task"]["thread_key"], OTHER)
        self.assertTrue({("p1", OTHER), ("p2", OTHER), ("p3", OTHER)}.issubset(stats["complete"]))


class Semantics(unittest.TestCase):
    def test_projection_finalization_reserve_preserves_outer_deadline_and_admission(self):
        from cs import observability_producers
        from cs.observability_causal import validate
        cases = [(None, .5, True), (10.25, .25, True), (10.05, .05, True),
                 (10.04, .04, False), (10.03, .03, False), (10.015, .015, False)]
        for inherited, allowance, admitted in cases:
            with self.subTest(inherited=inherited):
                clock = [10.0]
                reads, summaries = [], []
                outer = 10 + allowance
                reserve = min(allowance, .02)
                cutoff = outer - reserve
                def read(account, method, requests, **kwargs):
                    reads.append(kwargs['deadline'])
                    clock[0] = cutoff - .02
                    return {key: rpc_reads.ReadOutcome(value=projection() | {'thread_key':key}) for key in requests}
                def emit(*args, **kwargs):
                    if kwargs.get('method') == 'tasks.assignment.budget':
                        summaries.append(kwargs['causal'])
                with patch.object(task_assignment.time, 'monotonic', side_effect=lambda:clock[0]), patch.object(task_assignment, 'PROJECTION_SECONDS', .5), patch.object(rpc_reads, 'CLOSE_SECONDS', .01), patch.object(rpc_reads, 'read_many', side_effect=read), patch.object(observability_producers, 'emit', side_effect=emit):
                    result = task_assignment.projections(settings(), [KEY, '<later@example.test>'], deadline=inherited)
                self.assertEqual(len(reads), int(admitted))
                if admitted:
                    self.assertAlmostEqual(reads[0], cutoff)
                    self.assertEqual(result[KEY]['state'], 'normal')
                self.assertEqual(result['<later@example.test>']['state'], 'unknown')
                self.assertTrue(result['<later@example.test>']['hold_auto_reply'])
                self.assertEqual(len(summaries), 1)
                summary = summaries[0]
                self.assertEqual(summary['facts']['effective_entry_ms'], round(allowance * 1000))
                self.assertEqual(summary['timing']['finalization_reserve_us'], round(reserve * 1000000))
                self.assertEqual(summary['timing']['work_allowance_us'], round((allowance-reserve) * 1000000))
                validate(summary)
                for field in ('finalization_reserve_us', 'work_allowance_us'):
                    with self.assertRaises(ValueError):
                        validate({**summary, 'timing':{**summary['timing'], field:True}})
                    with self.assertRaises(ValueError):
                        validate({**summary, 'timing':{**summary['timing'], field:-1}})
        print('ALLOCATION: unchanged outer/inherited deadlines, earlier read/admission cutoff and combined insufficient capacity checked', file=sys.stderr)
    def test_cleanup_pipe_timeout_confirms_reap_and_keeps_one_allowance(self):
        import os
        process = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True)
        identity = rpc_reads._process_start(process)
        self.assertIsInstance(identity, int)
        with patch.object(process, 'communicate', side_effect=subprocess.TimeoutExpired('controlled', .01)) as communication, patch.object(rpc_reads, 'CLOSE_SECONDS', .2):
            value = rpc_reads._cleanup_process(process, time.monotonic() + .2, None, identity)
        self.assertEqual(value['worker_pid'], process.pid)
        self.assertEqual(value['worker_start_ticks'], identity)
        self.assertTrue(value['signal_attempted'])
        self.assertTrue(value['signal_sent'])
        self.assertTrue(value['reap_confirmed'])
        self.assertTrue(value['exit_status_available'])
        self.assertEqual(value['worker_exit'], -9)
        self.assertEqual(communication.call_count, 1)
        with self.assertRaises(ProcessLookupError):
            os.kill(process.pid, 0)
        clock = [10.0]
        class Unconfirmed:
            pid = 123
            returncode = None
            stdin = None
            stdout = None
            def poll(self): return None
            def kill(self): pass
            def communicate(self, *, timeout):
                self.communicate_timeout = timeout
                clock[0] += .018
                raise subprocess.TimeoutExpired('controlled', timeout)
            def wait(self, *, timeout):
                self.wait_timeout = timeout
                clock[0] += timeout
                raise subprocess.TimeoutExpired('controlled', timeout)
        unconfirmed = Unconfirmed()
        with patch.object(rpc_reads.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(rpc_reads, 'CLOSE_SECONDS', .03):
            missing = rpc_reads._cleanup_process(unconfirmed, 10.03, os.getpid())
        self.assertFalse(missing['reap_confirmed'])
        self.assertFalse(missing['exit_status_available'])
        self.assertFalse(missing['worker_start_available'])
        self.assertNotIn('worker_start_ticks', missing)
        self.assertLessEqual(unconfirmed.communicate_timeout, .03)
        self.assertLessEqual(unconfirmed.wait_timeout, .012000001)
        self.assertEqual(missing['cleanup_elapsed_us'], 30000)
        from cs.observability_causal import decision, validate
        observation = decision('assignment_time_budget', 'complete', timing=value)
        self.assertIsNotNone(observation)
        validate(observation)
        for invalid in ({'worker_pid': 'private'}, {'worker_pid': -1}, {'worker_pid': True}, {'reap_confirmed': 1}, {'arbitrary': 1}, {'cleanup_elapsed_us': float('nan')}):
            with self.assertRaises(ValueError):
                validate({**observation, 'timing': invalid})
        print('CLEANUP_MEASUREMENTS ' + json.dumps({'confirmed': value, 'unconfirmed': missing}, sort_keys=True), file=sys.stderr)
    def test_mutations_rejected_before_client_or_authentication(self):
        with patch.object(rpc, "EngineClient") as client:
            for method in ("chat.send", "tasks.assignment.commit", "drafts.send", "emails.needs_reply"):
                with self.assertRaises(ValueError):
                    rpc_reads.read_many(settings(), method, {KEY: {}})
            client.assert_not_called()

    def test_supervised_caps_are_finite_and_method_specific(self):
        command = (sys.executable, "-c", "import json,sys; p=json.load(sys.stdin); "
            "print(json.dumps({'outcomes':{'a':{'value':[p['request_timeout'],p['batch_timeout'],p['request_seconds']], 'error':None}},'token':None}))")
        with patch.object(rpc_reads, "READ_COMMAND", command):
            for method, kwargs, expected in (
                ("tasks.assignment.project", {}, [60, 90, 60]),
                ("tasks.assignment.project", {"request_timeout": 999, "batch_timeout": 999}, [150, 180, 150]),
                ("emails.list_by_thread", {"request_timeout": 999, "batch_timeout": 999}, [60, 90, 60]),
            ):
                with self.subTest(method=method, kwargs=kwargs):
                    outcome = rpc_reads.read_many(settings(), method, {"a": {}}, **kwargs)["a"]
                    self.assertIsNone(outcome.error)
                    self.assertEqual(outcome.value, expected)
        for field in ("request_timeout", "batch_timeout", "deadline"):
            for value in (float("inf"), float("nan")):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    rpc_reads.read_many(settings(), "tasks.assignment.project", {"a": {}}, **{field: value})

    def test_expired_batch_has_every_key_without_connection(self):
        with patch.object(rpc, "EngineClient") as client:
            result = rpc_reads.read_many(settings(), "tasks.assignment.project", {"a": {}, "b": {}}, deadline=time.monotonic() - 1)
            self.assertEqual(list(result), ["a", "b"])
            self.assertTrue(all(row.error is not None for row in result.values()))
            client.assert_not_called()

    def compare(self, selected, raw):
        def one(s, method, params, timeout):
            value = raw[s.engine_owner_uid][params["thread_key"]]
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)
        def many(s, method, requests, **kwargs):
            return {key: rpc_reads.ReadOutcome(error=value) if isinstance(value := raw[s.engine_owner_uid][key], Exception)
                    else rpc_reads.ReadOutcome(value=copy.deepcopy(value)) for key in requests}
        with patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=one), patch.object(rpc_reads, "read_many", side_effect=many):
            expected = {key: task_assignment.project(selected, key) for key in sorted(raw["operator"])}
            actual = task_assignment.projections(selected, reversed(list(raw["operator"])))
        self.assertEqual(actual, expected)
        self.assertEqual(list(actual), list(reversed(raw["operator"])))

    def test_single_and_bulk_preserve_states_conflicts_owner_exception_and_errors(self):
        selected = settings().model_copy(update={"accounts": "peer:peer,duplicate:peer"})
        for state in ("normal", "needs-assignment", "assigned", "closed", "later-inbound", "unknown", "conflict"):
            current_task = task("closed" if state in {"closed", "later-inbound"} else "assigned") if state in {"assigned", "closed", "later-inbound"} else None
            base = projection(state, complete=state != "needs-assignment", task=current_task)
            for peer in (base | {"actor_uid": "peer"}, ConnectionError("offline"), base | {"actor_uid": "peer", "space_id": "foreign"}, base | {"actor_uid": "forged"}, base | {"actor_uid": "peer", "task": task() | {"revision": 2}}, base | {"actor_uid": "peer", "covered_message_ids": None}):
                with self.subTest(state=state, peer=peer):
                    self.compare(selected, {"operator": {KEY: base}, "peer": {KEY: peer}})
        for invalid in (None, {}, projection() | {"actor_uid": "forged"}, projection("assigned", task=task() | {"revision": 0}), projection() | {"hold_auto_reply": True, "current_message_ids": None}):
            self.compare(selected, {"operator": {KEY: invalid}, "peer": {KEY: projection() | {"actor_uid": "peer"}}})
        creator = task("closed") | {"creator_uid": "peer"}
        self.compare(selected, {"operator": {KEY: projection("unknown", complete=False, task=creator) | {"reason": "SOURCE_OWNER_REQUIRED", "source_owner_uid": "peer"}}, "peer": {KEY: projection("later-inbound", task=creator) | {"actor_uid": "peer"}}})

    def test_multiple_roots_order_dedup_and_primary_failure(self):
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        roots = ["<z@example.test>", "<a@example.test>", KEY]
        raw = {uid: {key: projection() | {"thread_key": key, "actor_uid": uid} for key in roots} for uid in ("operator", "peer")}
        raw["operator"][roots[0]] = ConnectionError("offline")
        self.compare(selected, raw)

    def test_all_reserved_slots_defer_additional_actor_without_replacement(self):
        selected = settings().model_copy(update={"accounts": "p1:p1,p2:p2,p3:p3,p4:p4"})
        dispatched = []
        def many(account, method, requests, **kwargs):
            dispatched.append(account.engine_owner_uid)
            return {key: rpc_reads.ReadOutcome(error=TimeoutError("stalled")) for key in requests}
        with patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc_reads, "read_many", side_effect=many):
            result = task_assignment.projections(selected, [KEY, "<later@example.test>"])
        self.assertEqual(len(dispatched), 4)
        self.assertNotIn("p4", dispatched)
        self.assertTrue(all(row["state"] == "unknown" and row["hold_auto_reply"] for row in result.values()))
        self.assertIn("unresolved transport timeout", result["<later@example.test>"]["reason"])

    def test_expired_capacity_is_explicit_without_dispatch(self):
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        with patch.object(task_assignment, "PROJECTION_SECONDS", 0), patch.object(rpc_reads, "read_many") as read, patch.object(config, "load", return_value=selected.model_copy(update={"engine_owner_uid": "peer"})):
            result = task_assignment.projections(selected, [KEY])[KEY]
        read.assert_not_called()
        self.assertEqual(result["state"], "unknown")
        self.assertIn("capacity deferred", result["reason"])
        self.assertTrue(result["hold_auto_reply"])

    def test_review_bulk_keeps_list_order_and_runs_full_sweep(self):
        from cs import review, unanswered
        import tempfile
        import contextlib
        import io
        keys = ["z", "a", "z"]
        rows = [{"thread_key": key} for key in keys]
        projected = {key: projection() | {"thread_key": key} for key in keys}
        with tempfile.TemporaryDirectory() as directory:
            selected = settings().model_copy(update={"db_path": str(Path(directory) / "state.db"), "log_path": Path(directory) / "operator.log"})
            with patch.object(review.rpc, "call_sync", return_value=[]), patch.object(review.draft_state, "reconcile", return_value=([], [])), patch.object(review.campaign, "list_campaigns", return_value=[]), patch.object(task_assignment, "listing", return_value={"items": rows}), patch.object(task_assignment, "projections", return_value=projected) as bulk, patch.object(unanswered, "sweep", side_effect=lambda s, **kw: (kw["projection_observer"](projected), {"human_work": [], "assignment_audit": []})[1]) as sweep, contextlib.redirect_stderr(io.StringIO()):
                result = review._aggregate(selected)
        self.assertEqual([row["thread_key"] for row in result["assignments"]], keys)
        bulk.assert_not_called()
        self.assertEqual(sweep.call_args.kwargs["listed_roots"], keys)
        self.assertEqual(sweep.call_args.kwargs["days"], 14)

    def test_batch_setup_failure_is_conservative_for_every_requested_root(self):
        with patch.object(rpc_reads, "read_many", side_effect=ValueError("invalid setup")):
            views, note = engine_view.classify(settings(), ["a", "b"])
            projected = task_assignment.projections(settings(), ["a", "b"])
        self.assertEqual(views, {})
        self.assertEqual(note, "ValueError: invalid setup (2 thread(s) unclassified)")
        self.assertEqual(list(projected), ["a", "b"])
        self.assertTrue(all(row["state"] == "unknown" and row["hold_auto_reply"] for row in projected.values()))

    def test_classification_preserves_data_and_conservative_failures(self):
        raw = {"a": rpc_reads.ReadOutcome(value={"emails": [{"is_auto_reply": True, "date": "2026-10-13T10:00:00"}, {"date": "2026-10-13T11:00:00"}]}),
               "b": rpc_reads.ReadOutcome(error=ConnectionError("offline")),
               "c": rpc_reads.ReadOutcome(value={"emails": ["malformed"]})}
        with patch.object(rpc_reads, "read_many", return_value=raw):
            views, note = engine_view.classify(settings(), ["a", "a", "b", "c", ""])
        self.assertEqual(list(views), ["a"])
        self.assertEqual(views["a"].count, 2)
        self.assertEqual(views["a"].auto_at, {1791885600})
        self.assertEqual(note, "ConnectionError: offline (2 thread(s) unclassified)")


if __name__ == "__main__":
    unittest.main()
