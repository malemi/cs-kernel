"""Project complete private recurring material without granting action authority."""
import hashlib
import json
import re

NAMES = ('workset-tasks.json', 'workset-review.json')
RAW_DEEP = {'task', 'events', 'current_inbound', 'covered_inbound', 'route_digest', 'current_message_ids', 'covered_message_ids'}
NOTE = 'Complete ordered recurring material. RAW REF is UNINSPECTED, grants no body inspection, attention, assignment authority, dossier completeness or send permission; fresh selected-root reads and engine guards remain mandatory. Visible typed_values definitions contain full original JSON values; VALUE indexes them. OBJECT contains an object_columns index and ordered cells. ABSENT:true means field absence. RAW REF:true marks only enumerated uninspected details; source index, pointer pattern and ordered numeric indices reconstruct its exact original JSON pointer. No definition grants authority.'

SCHEMA_ROWS = [
    ('workset-review.json:', 'dict', 'digest,nonce,owner_uid,payload,source'),
    ('workset-review.json:/digest', 'str', ''),
    ('workset-review.json:/nonce', 'str', ''),
    ('workset-review.json:/owner_uid', 'str', ''),
    ('workset-review.json:/payload', 'dict', 'assignment_audit,assignment_coverage,assignments,assignments_error,campaigns,drafts,drafts_inventory,drafts_notes,engine_drafts,escalated,gmail_drafts,gmail_drafts_observation,handled_out_of_band,human_work,last_tick,review_coverage,tasks'),
    ('workset-review.json:/payload/assignment_audit', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage', 'dict', 'requested_order,roots'),
    ('workset-review.json:/payload/assignment_coverage/requested_order', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/requested_order/*', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*', 'dict', 'projection,sources,thread_key'),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection', 'dict', 'actor_uid,authoritative_thread_key,authority_complete,complete,component_scope_present,component_thread_keys,covered_inbound,covered_message_ids,current_inbound,current_message_ids,events,hold_auto_reply,hold_scope,reason,reply_evidence,route_digest,source_owner_uid,space_id,state,task,thread_key,version'),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/actor_uid', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/authoritative_thread_key', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/authority_complete', 'bool', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/complete', 'bool', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/component_scope_present', 'bool', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/component_thread_keys', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/component_thread_keys/*', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/covered_inbound', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/covered_message_ids', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/current_inbound', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/current_message_ids', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/current_message_ids/*', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/events', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/hold_auto_reply', 'bool', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/hold_scope', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reason', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*', 'dict', 'actor_uid,complete,digest,judgement,reason,source,source_id,space_id,thread_key,version'),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/actor_uid', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/complete', 'bool', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/digest', 'NoneType,str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/judgement', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/reason', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source', 'NoneType,dict', 'actor_uid,content_digest,in_reply_to,mailbox_id,message_id,observation_only,provider,raw_header_digest,recipients,route_digest,thread_key'),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/actor_uid', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/content_digest', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/in_reply_to', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/mailbox_id', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/message_id', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/observation_only', 'bool', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/provider', 'dict', 'folder,uid,uidvalidity'),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/provider/folder', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/provider/uid', 'int', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/provider/uidvalidity', 'int', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/raw_header_digest', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/recipients', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/recipients/*', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/route_digest', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source/thread_key', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source_id', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/space_id', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/thread_key', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/version', 'int', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/route_digest', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/source_owner_uid', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/space_id', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/state', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/task', 'NoneType', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/thread_key', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/projection/version', 'int', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/sources', 'list', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/sources/*', 'str', ''),
    ('workset-review.json:/payload/assignment_coverage/roots/*/thread_key', 'str', ''),
    ('workset-review.json:/payload/assignments', 'list', ''),
    ('workset-review.json:/payload/assignments_error', 'str', ''),
    ('workset-review.json:/payload/campaigns', 'list', ''),
    ('workset-review.json:/payload/campaigns/*', 'dict', 'campaign,counts,excluded,flagged,outcomes'),
    ('workset-review.json:/payload/campaigns/*/campaign', 'str', ''),
    ('workset-review.json:/payload/campaigns/*/counts', 'dict', 'replied,sent,skipped'),
    ('workset-review.json:/payload/campaigns/*/counts/replied', 'int', ''),
    ('workset-review.json:/payload/campaigns/*/counts/sent', 'int', ''),
    ('workset-review.json:/payload/campaigns/*/counts/skipped', 'int', ''),
    ('workset-review.json:/payload/campaigns/*/excluded', 'bool', ''),
    ('workset-review.json:/payload/campaigns/*/flagged', 'list', ''),
    ('workset-review.json:/payload/campaigns/*/outcomes', 'dict', 'declined,engaged'),
    ('workset-review.json:/payload/campaigns/*/outcomes/declined', 'int', ''),
    ('workset-review.json:/payload/campaigns/*/outcomes/engaged', 'int', ''),
    ('workset-review.json:/payload/drafts', 'list', ''),
    ('workset-review.json:/payload/drafts/*', 'dict', 'body,body_note,cc_recipients,composed_at,composed_iso,engine_draft_id,engine_id,engine_owner_uid,evidence_incomplete,gmail_body_complete,gmail_body_observed,gmail_fingerprint,gmail_uid,gmail_uidvalidity,identity_conflict,identity_evidence,recipients,signal,signal_at,subject,thread_key,to,to_display,verdict,workset_hold_reasons'),
    ('workset-review.json:/payload/drafts/*/body', 'str', ''),
    ('workset-review.json:/payload/drafts/*/body_note', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/cc_recipients', 'list', ''),
    ('workset-review.json:/payload/drafts/*/cc_recipients/*', 'str', ''),
    ('workset-review.json:/payload/drafts/*/composed_at', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/composed_iso', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/engine_draft_id', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/engine_id', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/engine_owner_uid', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/evidence_incomplete', 'list', ''),
    ('workset-review.json:/payload/drafts/*/gmail_body_complete', 'bool', ''),
    ('workset-review.json:/payload/drafts/*/gmail_body_observed', 'bool', ''),
    ('workset-review.json:/payload/drafts/*/gmail_fingerprint', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/gmail_uid', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/gmail_uidvalidity', 'str', ''),
    ('workset-review.json:/payload/drafts/*/identity_conflict', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/identity_evidence', 'str', ''),
    ('workset-review.json:/payload/drafts/*/recipients', 'list', ''),
    ('workset-review.json:/payload/drafts/*/recipients/*', 'str', ''),
    ('workset-review.json:/payload/drafts/*/signal', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/signal_at', 'NoneType,str', ''),
    ('workset-review.json:/payload/drafts/*/subject', 'str', ''),
    ('workset-review.json:/payload/drafts/*/thread_key', 'str', ''),
    ('workset-review.json:/payload/drafts/*/to', 'str', ''),
    ('workset-review.json:/payload/drafts/*/to_display', 'str', ''),
    ('workset-review.json:/payload/drafts/*/verdict', 'str', ''),
    ('workset-review.json:/payload/drafts/*/workset_hold_reasons', 'list', ''),
    ('workset-review.json:/payload/drafts/*/workset_hold_reasons/*', 'str', ''),
    ('workset-review.json:/payload/drafts_inventory', 'dict', 'complete,engine_count,gmail_count,identity_sha256,row_count,version'),
    ('workset-review.json:/payload/drafts_inventory/complete', 'bool', ''),
    ('workset-review.json:/payload/drafts_inventory/engine_count', 'int', ''),
    ('workset-review.json:/payload/drafts_inventory/gmail_count', 'int', ''),
    ('workset-review.json:/payload/drafts_inventory/identity_sha256', 'str', ''),
    ('workset-review.json:/payload/drafts_inventory/row_count', 'int', ''),
    ('workset-review.json:/payload/drafts_inventory/version', 'int', ''),
    ('workset-review.json:/payload/drafts_notes', 'list', ''),
    ('workset-review.json:/payload/drafts_notes/*', 'str', ''),
    ('workset-review.json:/payload/engine_drafts', 'list', ''),
    ('workset-review.json:/payload/engine_drafts/*', 'dict', 'attachment_paths,bcc_addresses,body,body_format,cc_addresses,created_at,error_message,id,in_reply_to,original_message_id,owner_id,provider,references,sent_at,sent_message_id,status,subject,thread_id,to_addresses,updated_at'),
    ('workset-review.json:/payload/engine_drafts/*/attachment_paths', 'list', ''),
    ('workset-review.json:/payload/engine_drafts/*/bcc_addresses', 'list', ''),
    ('workset-review.json:/payload/engine_drafts/*/body', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/body_format', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/cc_addresses', 'list', ''),
    ('workset-review.json:/payload/engine_drafts/*/cc_addresses/*', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/created_at', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/error_message', 'NoneType,str', ''),
    ('workset-review.json:/payload/engine_drafts/*/id', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/in_reply_to', 'NoneType,str', ''),
    ('workset-review.json:/payload/engine_drafts/*/original_message_id', 'NoneType', ''),
    ('workset-review.json:/payload/engine_drafts/*/owner_id', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/provider', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/references', 'list', ''),
    ('workset-review.json:/payload/engine_drafts/*/references/*', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/sent_at', 'NoneType', ''),
    ('workset-review.json:/payload/engine_drafts/*/sent_message_id', 'NoneType', ''),
    ('workset-review.json:/payload/engine_drafts/*/status', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/subject', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/thread_id', 'NoneType,str', ''),
    ('workset-review.json:/payload/engine_drafts/*/to_addresses', 'list', ''),
    ('workset-review.json:/payload/engine_drafts/*/to_addresses/*', 'str', ''),
    ('workset-review.json:/payload/engine_drafts/*/updated_at', 'str', ''),
    ('workset-review.json:/payload/escalated', 'list', ''),
    ('workset-review.json:/payload/escalated/*', 'dict', 'days,email,escalated_at,escalated_on,owner,reason'),
    ('workset-review.json:/payload/escalated/*/days', 'int', ''),
    ('workset-review.json:/payload/escalated/*/email', 'str', ''),
    ('workset-review.json:/payload/escalated/*/escalated_at', 'str', ''),
    ('workset-review.json:/payload/escalated/*/escalated_on', 'str', ''),
    ('workset-review.json:/payload/escalated/*/owner', 'str', ''),
    ('workset-review.json:/payload/escalated/*/reason', 'str', ''),
    ('workset-review.json:/payload/gmail_drafts', 'list', ''),
    ('workset-review.json:/payload/gmail_drafts/*', 'dict', 'body,body_complete,body_note,cc,date,engine_draft_id,engine_owner_uid,fingerprint,in_reply_to,message_id,references,subject,thread_key,to,uid,uidvalidity'),
    ('workset-review.json:/payload/gmail_drafts/*/body', 'str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/body_complete', 'bool', ''),
    ('workset-review.json:/payload/gmail_drafts/*/body_note', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/cc', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/date', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/engine_draft_id', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/engine_owner_uid', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/fingerprint', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/in_reply_to', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/message_id', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/references', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/subject', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/thread_key', 'str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/to', 'NoneType,str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/uid', 'str', ''),
    ('workset-review.json:/payload/gmail_drafts/*/uidvalidity', 'str', ''),
    ('workset-review.json:/payload/gmail_drafts_observation', 'dict', 'complete,expected_uids,observed_uids,search_complete,uidvalidity,version'),
    ('workset-review.json:/payload/gmail_drafts_observation/complete', 'bool', ''),
    ('workset-review.json:/payload/gmail_drafts_observation/expected_uids', 'list', ''),
    ('workset-review.json:/payload/gmail_drafts_observation/expected_uids/*', 'str', ''),
    ('workset-review.json:/payload/gmail_drafts_observation/observed_uids', 'list', ''),
    ('workset-review.json:/payload/gmail_drafts_observation/observed_uids/*', 'str', ''),
    ('workset-review.json:/payload/gmail_drafts_observation/search_complete', 'bool', ''),
    ('workset-review.json:/payload/gmail_drafts_observation/uidvalidity', 'str', ''),
    ('workset-review.json:/payload/gmail_drafts_observation/version', 'int', ''),
    ('workset-review.json:/payload/handled_out_of_band', 'list', ''),
    ('workset-review.json:/payload/handled_out_of_band/*', 'dict', 'email,handled_at,handled_on,reason'),
    ('workset-review.json:/payload/handled_out_of_band/*/email', 'str', ''),
    ('workset-review.json:/payload/handled_out_of_band/*/handled_at', 'str', ''),
    ('workset-review.json:/payload/handled_out_of_band/*/handled_on', 'str', ''),
    ('workset-review.json:/payload/handled_out_of_band/*/reason', 'str', ''),
    ('workset-review.json:/payload/human_work', 'list', ''),
    ('workset-review.json:/payload/human_work/*', 'dict', 'assignment,days_waiting,email,last_inbound_date,name,state,subject,thread_key'),
    ('workset-review.json:/payload/human_work/*/assignment', 'dict', 'actor_uid,authoritative_thread_key,authority_complete,complete,component_scope_present,component_thread_keys,covered_inbound,covered_message_ids,current_inbound,current_message_ids,events,hold_auto_reply,hold_scope,provenance,reason,reply_evidence,route_digest,source_owner_uid,space_id,state,task,thread_key,version'),
    ('workset-review.json:/payload/human_work/*/assignment/actor_uid', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/authoritative_thread_key', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/authority_complete', 'bool', ''),
    ('workset-review.json:/payload/human_work/*/assignment/complete', 'bool', ''),
    ('workset-review.json:/payload/human_work/*/assignment/component_scope_present', 'bool', ''),
    ('workset-review.json:/payload/human_work/*/assignment/component_thread_keys', 'list', ''),
    ('workset-review.json:/payload/human_work/*/assignment/component_thread_keys/*', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/covered_inbound', 'list', ''),
    ('workset-review.json:/payload/human_work/*/assignment/covered_message_ids', 'list', ''),
    ('workset-review.json:/payload/human_work/*/assignment/current_inbound', 'list', ''),
    ('workset-review.json:/payload/human_work/*/assignment/current_message_ids', 'list', ''),
    ('workset-review.json:/payload/human_work/*/assignment/current_message_ids/*', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/events', 'list', ''),
    ('workset-review.json:/payload/human_work/*/assignment/hold_auto_reply', 'bool', ''),
    ('workset-review.json:/payload/human_work/*/assignment/hold_scope', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/provenance', 'list', ''),
    ('workset-review.json:/payload/human_work/*/assignment/provenance/*', 'dict', 'basis,owner,reason'),
    ('workset-review.json:/payload/human_work/*/assignment/provenance/*/basis', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/provenance/*/owner', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/provenance/*/reason', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reason', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence', 'list', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*', 'dict', 'actor_uid,complete,digest,judgement,reason,source,source_id,space_id,thread_key,version'),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/actor_uid', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/complete', 'bool', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/digest', 'NoneType,str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/judgement', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/reason', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source', 'NoneType,dict', 'actor_uid,content_digest,in_reply_to,mailbox_id,message_id,observation_only,provider,raw_header_digest,recipients,route_digest,thread_key'),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/actor_uid', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/content_digest', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/in_reply_to', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/mailbox_id', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/message_id', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/observation_only', 'bool', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/provider', 'dict', 'folder,uid,uidvalidity'),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/provider/folder', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/provider/uid', 'int', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/provider/uidvalidity', 'int', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/raw_header_digest', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/recipients', 'list', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/recipients/*', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/route_digest', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source/thread_key', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source_id', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/space_id', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/thread_key', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/version', 'int', ''),
    ('workset-review.json:/payload/human_work/*/assignment/route_digest', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/source_owner_uid', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/space_id', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/state', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/task', 'NoneType', ''),
    ('workset-review.json:/payload/human_work/*/assignment/thread_key', 'str', ''),
    ('workset-review.json:/payload/human_work/*/assignment/version', 'int', ''),
    ('workset-review.json:/payload/human_work/*/days_waiting', 'int', ''),
    ('workset-review.json:/payload/human_work/*/email', 'str', ''),
    ('workset-review.json:/payload/human_work/*/last_inbound_date', 'str', ''),
    ('workset-review.json:/payload/human_work/*/name', 'str', ''),
    ('workset-review.json:/payload/human_work/*/state', 'str', ''),
    ('workset-review.json:/payload/human_work/*/subject', 'str', ''),
    ('workset-review.json:/payload/human_work/*/thread_key', 'str', ''),
    ('workset-review.json:/payload/last_tick', 'list', ''),
    ('workset-review.json:/payload/last_tick/*', 'str', ''),
    ('workset-review.json:/payload/review_coverage', 'dict', 'aggregation,assignment_listing,mailbox_discovery'),
    ('workset-review.json:/payload/review_coverage/aggregation', 'str', ''),
    ('workset-review.json:/payload/review_coverage/assignment_listing', 'str', ''),
    ('workset-review.json:/payload/review_coverage/mailbox_discovery', 'str', ''),
    ('workset-review.json:/payload/tasks', 'list', ''),
    ('workset-review.json:/payload/tasks/*', 'dict', 'action_required,analyzed_at,channel,close_actor,close_note,completed_at,contact_email,contact_name,contact_phone,created_at,dedup_skip_until,due_at,email,event_id,event_type,id,last_signal_at,owner_id,pinned,reason,source_root_state,sources,suggested_action,thread_key,title,urgency'),
    ('workset-review.json:/payload/tasks/*/action_required', 'bool', ''),
    ('workset-review.json:/payload/tasks/*/analyzed_at', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/channel', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/close_actor', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/close_note', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/completed_at', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/contact_email', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/contact_name', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/contact_phone', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/created_at', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/dedup_skip_until', 'NoneType,int', ''),
    ('workset-review.json:/payload/tasks/*/due_at', 'NoneType,float', ''),
    ('workset-review.json:/payload/tasks/*/email', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/event_id', 'str', ''),
    ('workset-review.json:/payload/tasks/*/event_type', 'str', ''),
    ('workset-review.json:/payload/tasks/*/id', 'str', ''),
    ('workset-review.json:/payload/tasks/*/last_signal_at', 'str', ''),
    ('workset-review.json:/payload/tasks/*/owner_id', 'str', ''),
    ('workset-review.json:/payload/tasks/*/pinned', 'bool', ''),
    ('workset-review.json:/payload/tasks/*/reason', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/source_root_state', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources', 'dict', 'blobs,business_id,calendar_events,closes,contact_identity,emails,notifier_email,signup_created_at,snoozes,thread_id'),
    ('workset-review.json:/payload/tasks/*/sources/blobs', 'list', ''),
    ('workset-review.json:/payload/tasks/*/sources/blobs/*', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/business_id', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/calendar_events', 'list', ''),
    ('workset-review.json:/payload/tasks/*/sources/closes', 'list', ''),
    ('workset-review.json:/payload/tasks/*/sources/closes/*', 'dict', 'actor,at,display_note,why'),
    ('workset-review.json:/payload/tasks/*/sources/closes/*/actor', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/closes/*/at', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/closes/*/display_note', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/closes/*/why', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/contact_identity', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/emails', 'list', ''),
    ('workset-review.json:/payload/tasks/*/sources/emails/*', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/notifier_email', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/signup_created_at', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/snoozes', 'list', ''),
    ('workset-review.json:/payload/tasks/*/sources/snoozes/*', 'dict', 'actor,at,due_at,previous_due_at,why'),
    ('workset-review.json:/payload/tasks/*/sources/snoozes/*/actor', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/snoozes/*/at', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/snoozes/*/due_at', 'float', ''),
    ('workset-review.json:/payload/tasks/*/sources/snoozes/*/previous_due_at', 'NoneType,float', ''),
    ('workset-review.json:/payload/tasks/*/sources/snoozes/*/why', 'str', ''),
    ('workset-review.json:/payload/tasks/*/sources/thread_id', 'str', ''),
    ('workset-review.json:/payload/tasks/*/suggested_action', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/thread_key', 'str', ''),
    ('workset-review.json:/payload/tasks/*/title', 'NoneType,str', ''),
    ('workset-review.json:/payload/tasks/*/urgency', 'NoneType,str', ''),
    ('workset-review.json:/source', 'str', ''),
    ('workset-tasks.json:', 'dict', 'digest,nonce,owner_uid,payload,source'),
    ('workset-tasks.json:/digest', 'str', ''),
    ('workset-tasks.json:/nonce', 'str', ''),
    ('workset-tasks.json:/owner_uid', 'str', ''),
    ('workset-tasks.json:/payload', 'dict,list', 'tasks,complete,error,errors,total,truncated,has_more,next_cursor,next_page,next_page_token'),
    ('workset-tasks.json:/payload/*', 'dict', 'action_required,analyzed_at,channel,close_actor,close_note,completed_at,contact_email,contact_name,contact_phone,created_at,dedup_skip_until,due_at,event_id,event_type,id,last_signal_at,owner_id,pinned,reason,source_root_state,sources,suggested_action,thread_key,title,urgency'),
    ('workset-tasks.json:/payload/*/action_required', 'bool', ''),
    ('workset-tasks.json:/payload/*/analyzed_at', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/channel', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/close_actor', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/close_note', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/completed_at', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/contact_email', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/contact_name', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/contact_phone', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/created_at', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/dedup_skip_until', 'NoneType,int', ''),
    ('workset-tasks.json:/payload/*/due_at', 'NoneType,float', ''),
    ('workset-tasks.json:/payload/*/event_id', 'str', ''),
    ('workset-tasks.json:/payload/*/event_type', 'str', ''),
    ('workset-tasks.json:/payload/*/id', 'str', ''),
    ('workset-tasks.json:/payload/*/last_signal_at', 'str', ''),
    ('workset-tasks.json:/payload/*/owner_id', 'str', ''),
    ('workset-tasks.json:/payload/*/pinned', 'bool', ''),
    ('workset-tasks.json:/payload/*/reason', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/source_root_state', 'str', ''),
    ('workset-tasks.json:/payload/*/sources', 'dict', 'blobs,business_id,calendar_events,closes,contact_identity,emails,notifier_email,signup_created_at,snoozes,thread_id'),
    ('workset-tasks.json:/payload/*/sources/blobs', 'list', ''),
    ('workset-tasks.json:/payload/*/sources/blobs/*', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/business_id', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/calendar_events', 'list', ''),
    ('workset-tasks.json:/payload/*/sources/closes', 'list', ''),
    ('workset-tasks.json:/payload/*/sources/closes/*', 'dict', 'actor,at,display_note,why'),
    ('workset-tasks.json:/payload/*/sources/closes/*/actor', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/closes/*/at', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/closes/*/display_note', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/closes/*/why', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/contact_identity', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/emails', 'list', ''),
    ('workset-tasks.json:/payload/*/sources/emails/*', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/notifier_email', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/signup_created_at', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/snoozes', 'list', ''),
    ('workset-tasks.json:/payload/*/sources/snoozes/*', 'dict', 'actor,at,due_at,previous_due_at,why'),
    ('workset-tasks.json:/payload/*/sources/snoozes/*/actor', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/snoozes/*/at', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/snoozes/*/due_at', 'float', ''),
    ('workset-tasks.json:/payload/*/sources/snoozes/*/previous_due_at', 'NoneType,float', ''),
    ('workset-tasks.json:/payload/*/sources/snoozes/*/why', 'str', ''),
    ('workset-tasks.json:/payload/*/sources/thread_id', 'str', ''),
    ('workset-tasks.json:/payload/*/suggested_action', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/thread_key', 'str', ''),
    ('workset-tasks.json:/payload/*/title', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/*/urgency', 'NoneType,str', ''),
    ('workset-tasks.json:/source', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*', 'dict', 'action_required,analyzed_at,channel,close_actor,close_note,completed_at,contact_email,contact_name,contact_phone,created_at,dedup_skip_until,due_at,event_id,event_type,id,last_signal_at,owner_id,pinned,reason,source_root_state,sources,suggested_action,thread_key,title,urgency'),
    ('workset-tasks.json:/payload/tasks/*/action_required', 'bool', ''),
    ('workset-tasks.json:/payload/tasks/*/analyzed_at', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/channel', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/close_actor', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/close_note', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/completed_at', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/contact_email', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/contact_name', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/contact_phone', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/created_at', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/dedup_skip_until', 'NoneType,int', ''),
    ('workset-tasks.json:/payload/tasks/*/due_at', 'NoneType,float', ''),
    ('workset-tasks.json:/payload/tasks/*/event_id', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/event_type', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/id', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/last_signal_at', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/owner_id', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/pinned', 'bool', ''),
    ('workset-tasks.json:/payload/tasks/*/reason', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/source_root_state', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources', 'dict', 'blobs,business_id,calendar_events,closes,contact_identity,emails,notifier_email,signup_created_at,snoozes,thread_id'),
    ('workset-tasks.json:/payload/tasks/*/sources/blobs', 'list', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/blobs/*', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/business_id', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/calendar_events', 'list', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/closes', 'list', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/closes/*', 'dict', 'actor,at,display_note,why'),
    ('workset-tasks.json:/payload/tasks/*/sources/closes/*/actor', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/closes/*/at', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/closes/*/display_note', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/closes/*/why', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/contact_identity', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/emails', 'list', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/emails/*', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/notifier_email', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/signup_created_at', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/snoozes', 'list', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/snoozes/*', 'dict', 'actor,at,due_at,previous_due_at,why'),
    ('workset-tasks.json:/payload/tasks/*/sources/snoozes/*/actor', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/snoozes/*/at', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/snoozes/*/due_at', 'float', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/snoozes/*/previous_due_at', 'NoneType,float', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/snoozes/*/why', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/sources/thread_id', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/suggested_action', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/thread_key', 'str', ''),
    ('workset-tasks.json:/payload/tasks/*/title', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks/*/urgency', 'NoneType,str', ''),
    ('workset-tasks.json:/payload/tasks', 'list', ''),
    ('workset-tasks.json:/payload/complete', 'bool', ''),
    ('workset-tasks.json:/payload/error', 'str,NoneType', ''),
    ('workset-tasks.json:/payload/errors', 'list', ''),
    ('workset-tasks.json:/payload/total', 'int', ''),
    ('workset-tasks.json:/payload/truncated', 'bool', ''),
    ('workset-tasks.json:/payload/has_more', 'bool', ''),
    ('workset-tasks.json:/payload/next_cursor', 'str,NoneType', ''),
    ('workset-tasks.json:/payload/next_page', 'str,int,NoneType', ''),
    ('workset-tasks.json:/payload/next_page_token', 'str,NoneType', ''),
    ('workset-tasks.json:/payload/errors/*', 'str', ''),
]

SCHEMA = {path: (types.split(','), set(keys.split(',')) if keys else set()) for path, types, keys in SCHEMA_ROWS}

def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate material JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite material JSON')))

def commitment(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def validate(value, path, depth=0, counter=None):
    counter = [0] if counter is None else counter
    counter[0] += 1
    if depth > 64 or counter[0] > 250000:
        raise ValueError('material complexity')
    shape = SCHEMA.get(path)
    if shape is None or type(value).__name__ not in shape[0]:
        raise ValueError('unclassified material type at '+path)
    if type(value) is dict:
        if set(value)-shape[1]:
            raise ValueError('unknown material field at '+path)
        for key, item in value.items():
            validate(item, path+'/'+key, depth+1, counter)
    elif type(value) is list:
        for item in value:
            validate(item, path+'/*', depth+1, counter)

def raw_detail(path):
    pieces = path.split('/')
    if len(pieces)==4 and pieces[0]=='payload' and pieces[1] in ('drafts','engine_drafts','gmail_drafts') and pieces[3]=='body':
        return True
    if any(name in pieces for name in ('assignment','projection')):
        if pieces[-1] in RAW_DEEP:
            return True
        if 'reply_evidence' in pieces and pieces[-1]=='digest':
            return True
        if 'reply_evidence' in pieces and 'source' in pieces and pieces[-1] in ('message_id','route_digest','raw_header_digest','content_digest'):
            return True
    return False

def project(records):
    refs = []
    def visit(value, name, path):
        if raw_detail(path):
            refs.append([name, '/'+path, type(value).__name__, len(value) if type(value) in (str,list,dict) else None])
            return {'RAW REF': True}
        if type(value) is dict:
            return {key:visit(item,name,path+'/'+key) for key,item in value.items()}
        if type(value) is list:
            return [visit(item,name,path+'/'+str(i)) for i,item in enumerate(value)]
        return value
    output=[]
    for name in NAMES:
        data=records[name]['payload']
        if type(data) is list:
            columns=list(dict.fromkeys(key for row in data for key in row))
            output.append({'table':name+':tasks','columns':columns})
            output.extend([[visit(row[key],name,'payload/'+str(i)+'/'+key) if key in row else {'ABSENT':True} for key in columns] for i,row in enumerate(data)])
        else:
            for key,value in data.items():
                base=records[NAMES[0]]['payload']
                if key=='tasks' and type(base)is list and type(value)is list:
                    index={row.get('id'):i for i,row in enumerate(base)}
                    if len(index)==len(base) and None not in index and len({row.get('id')for row in value})==len(value) and all(row.get('id')in index for row in value):
                        output.append({'table':name+':tasks_delta','columns':['source_task_index','ordered_fields','changed_values']})
                        for i,row in enumerate(value):
                            previous=base[index[row['id']]]
                            changes={field:visit(item,name,'payload/tasks/'+str(i)+'/'+field)for field,item in row.items()if field not in previous or json.dumps(item,ensure_ascii=False,separators=(',',':'))!=json.dumps(previous[field],ensure_ascii=False,separators=(',',':'))}
                            output.append([index[row['id']],list(row),changes])
                        continue
                if type(value) is list and value and all(type(row)is dict for row in value):
                    columns=list(dict.fromkeys(field for row in value for field in row))
                    output.append({'table':name+':'+key,'columns':columns})
                    output.extend([[visit(row[field],name,'payload/'+key+'/'+str(i)+'/'+field) if field in row else {'ABSENT':True} for field in columns] for i,row in enumerate(value)])
                else:
                    output.append({'table':name+':'+key,'columns':['value']})
                    output.append([visit(value,name,'payload/'+key)])
    patterns=[];compact=[]
    for source,pointer,kind,count in refs:
        indices=[int(piece) for piece in pointer.split('/') if piece.isdecimal()]
        pattern='/'.join('*' if piece.isdecimal() else piece for piece in pointer.split('/'))
        if pattern not in patterns:patterns.append(pattern)
        compact.append([NAMES.index(source),patterns.index(pattern),indices,kind,count])
    output.append({'table':'recurring_raw_patterns','columns':['source_order','pointer_patterns']})
    output.append([list(NAMES),patterns])
    output.append({'table':'recurring_raw_details','columns':['source_index','pattern_index','ordered_indices','present_type','count_or_length']})
    output.extend(compact)
    return output

def load_sources(directory, context, discovery, read):
    records, sources = {}, []
    for name in NAMES:
        raw=read(directory/name);record=parse(raw)
        validate(record,name+':')
        if set(record)!={'digest','nonce','owner_uid','payload','source'} or record['source']!=name[8:-5] or record['nonce']!=context['nonce'] or record['owner_uid']!=context['owner_uid'] or record['digest']!=commitment(record['payload']):
            raise ValueError('material source binding')
        records[name]=record
        sources.append({'basename':name,'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),'payload_digest':record['digest'],'source':record['source'],'nonce':record['nonce'],'owner_uid':record['owner_uid']})
    from .operator_workset import _rows, WorksetError
    try:
        _rows('tasks', records[NAMES[0]]['payload'])
    except WorksetError as exc:
        raise ValueError('incomplete task inventory') from exc
    from .draft_state import inventory_proof
    review=records[NAMES[1]]['payload']
    proof=inventory_proof(review.get('gmail_drafts'),review.get('engine_drafts'),review.get('drafts'),review.get('gmail_drafts_observation'))
    if proof.get('complete') is not True or proof!=review.get('drafts_inventory'):
        raise ValueError('material draft identity proof')
    reserved=parse(read(directory/'workset-reserved.json'))
    original=dict(discovery);original.pop('triage_workset')
    expected=commitment([original,{'tasks':records[NAMES[0]]['payload'],'review':review}])
    if set(reserved)!={'nonce','owner_uid','digest','selected','contacts'} or reserved['nonce']!=context['nonce'] or reserved['owner_uid']!=context['owner_uid'] or reserved['digest']!=expected:
        raise ValueError('material reservation binding')
    return records,sources

def append(view, records):
    rows=[{'recurring_material_schema':'cs.semantic_inventory.material.v2','legend':NOTE}]+pack(project(records))
    return view+'\n'+'\n'.join(json.dumps(row,ensure_ascii=False,separators=(',',':')) for row in rows)


def pack(rows):
    counts={};original={}
    def key(item):return json.dumps(item,ensure_ascii=False,separators=(',',':'))
    def count(item):
        if type(item)in (str,list,dict):
            token=key(item);counts[token]=counts.get(token,0)+1;original[token]=item
        if type(item)is dict:
            for value in item.values():count(value)
        elif type(item)is list:
            for value in item:count(value)
    for row in rows:
        if type(row)is list:count(row)
    chosen={token for token,n in counts.items()if n>1 and (len(token)-8)*(n-1)>len(token)+32}
    used=set();shapes=[]
    def encode(item,indices):
        token=key(item)if type(item)in (str,list,dict)else None
        if token in indices:used.add(token);return {'VALUE':indices[token]}
        if type(item)is dict:
            fields=list(item)
            if fields not in shapes:shapes.append(fields)
            return {'OBJECT':[shapes.index(fields),[encode(value,indices)for value in item.values()]]}
        if type(item)is list:return [encode(value,indices)for value in item]
        return item
    candidates={token:index for index,token in enumerate(sorted(chosen))}
    for row in rows:
        if type(row)is list:encode(row,candidates)
    active=sorted(used);used.clear();shapes.clear()
    indices={token:index for index,token in enumerate(active)}
    encoded=[encode(row,indices)if type(row)is list else row for row in rows]
    definitions=[[type(original[token]).__name__,original[token]]for token in active]
    return [{'table':'recurring_visible_definitions','columns':['typed_values','object_columns']},[definitions,shapes]]+encoded
