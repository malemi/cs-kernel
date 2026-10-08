def normal_projection(settings, params):
    return {"version": 1, "complete": True, "actor_uid": settings.engine_owner_uid,
            "space_id": "fixture-space", "thread_key": params["thread_key"],
            "state": "normal", "hold_auto_reply": False, "task": None,
            "events": [], "covered_inbound": [], "current_inbound": [],
            "current_message_ids": [], "covered_message_ids": [], "reply_evidence": [], "reason": "no assignment or reply candidate"}
