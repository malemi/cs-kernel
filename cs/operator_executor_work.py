"""Finite completion accounting from actual canonical command results.

These facts describe retained work and holds, never permission to send. Existing
CLI/engine guards remain authoritative for effects and independent acceptance.
"""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace


def selected_roots(directory, owner, nonce, results, *, send_mode, final=True, target_root=None):
    from .operator_executor_protocol import decode
    from .operator_executor_evidence import read_private
    from .operator_workset import _row_addresses
    from .task_assignment import _validate_projection
    discovery = decode(read_private(Path(directory) / 'discovery.json'))['discovery']
    roots = discovery['triage_workset']['selected']
    outcomes = []
    for selected in roots:
        root = selected['thread_key']
        if target_root is not None and root != target_root:
            continue
        authorities = [r for r in results if r['argv'] == ['assignment','status',root,'--json']]
        if not authorities:
            raise ValueError('selected_root_authority_missing')
        current = authorities[-1]
        value = decode(current['stdout'])
        projection = _validate_projection(SimpleNamespace(engine_owner_uid=owner),root,value)
        if projection['hold_auto_reply']:
            # Named incomplete technical authority is not a legitimate hold.
            from .operator_read_outcomes import assignment_hold
            if projection['complete'] is not True and not assignment_hold(projection,owner,root,__import__('cs.config',fromlist=['load']).load().account_map):
                raise ValueError('selected_root_authority_incomplete')
            outcomes.append(dict(root=root,revision=selected['revision'],outcome='held',
                reason='assignment_hold',tool_ids=[current['tool_id']]))
            continue
        if current['exit_code'] != 0 or projection['complete'] is not True:
            raise ValueError('selected_root_authority_incomplete')
        rows = [r for bucket in ('open','resumed') for r in discovery.get(bucket,[])
                if (r.get('thread_key') or r.get('thread_id')) == root]
        emails = {email for row in rows for email in _row_addresses(row)}
        # _row_addresses returns actual normalized addresses. The selected-root
        # association is resolved from original current discovery, not a model.
        if not emails:
            raise ValueError('selected_root_contact_missing')
        bodies = [r for r in results if r['argv'][:2] == ['rpc','emails.list_by_thread']
            and decode(r['argv'][2]) == {'thread_id':root} and r['exit_code'] == 0]
        if not bodies:
            raise ValueError('selected_root_original_body_missing')
        original=decode(bodies[-1]['stdout'])
        messages=original.get('emails') if isinstance(original,dict) else original
        if (not isinstance(messages,list) or not messages
                or any(not isinstance(m,dict) or not any(isinstance(m.get(k),str) and m[k].strip()
                    for k in ('body','body_text','body_html','text','content')) for m in messages)):
            raise ValueError('selected_root_original_body_missing')
        required = [current,bodies[-1]]
        for family in ('dossier','history','contacted'):
            reads = [r for r in results if len(r['argv']) >= 2 and r['argv'][0] == family
                and r['argv'][1].lower() in emails and r['exit_code'] in (0,1)]
            if not reads:
                raise ValueError('selected_root_' + family + '_missing')
            required.append(reads[-1])
        from .operator_workset import _hash
        if not (Path(directory)/('dossier-root-'+_hash(root)+'.json')).is_file():
            raise ValueError('selected_root_dossier_guard_missing')
        from .operator_dossier import require_effect_allowed
        from .config import load
        require_effect_allowed(load(),root)
        if not final:
            continue
        tasks = [r for r in results if r['argv'][:2] == ['tasks','create'] and '--thread-id' in r['argv']
            and r['argv'][r['argv'].index('--thread-id')+1] == root and '--json' in r['argv'] and r['exit_code'] == 0]
        for result in tasks:
            value = decode(result['stdout'])
            argv = result['argv']
            event = argv[argv.index('--event-id')+1]
            if (isinstance(value,dict) and value.get('ok') is True and isinstance(value.get('task_id'),str)
                    and value['task_id'] and event in projection['current_message_ids']
                    and '--email' in argv and argv[argv.index('--email')+1].lower() in emails):
                outcomes.append(dict(root=root,revision=selected['revision'],outcome='worked',reason='task_recorded',
                    tool_ids=[r['tool_id'] for r in required]+[result['tool_id']]))
                break
        else:
            drafts = [r for r in results if r['argv'][:1] == ['draft-reply'] and '--thread-id' in r['argv']
                and r['argv'][r['argv'].index('--thread-id')+1] == root and r['exit_code'] == 0]
            snapshots = [decode(read_private(p)) for p in Path(directory).glob('workset-draft-*.json')]
            matched = [(r,s) for r in drafts for s in snapshots if s.get('root') == root
                and s.get('nonce') == nonce and s.get('owner_uid') == owner
                and isinstance(s.get('draft_id'),str) and s['draft_id']
                and ('engine draft ready: '+s['draft_id']) in r['stdout'].decode()]
            if len(matched) != 1:
                raise ValueError('selected_root_outcome_missing')
            draft,snapshot = matched[0]
            ids = [r['tool_id'] for r in required]+[draft['tool_id']]
            reason = 'draft_prepared'
            if send_mode == 'send':
                sends = [r for r in results if r['argv'][:2] == ['draft-send',snapshot['draft_id']] and r['exit_code'] == 0]
                if len(sends) != 1:
                    raise ValueError('selected_root_exact_send_missing')
                ids.append(sends[0]['tool_id']);reason='draft_sent'
            outcomes.append(dict(root=root,revision=selected['revision'],outcome='worked',reason=reason,tool_ids=ids))
    return outcomes


def _reply_disposition(item,results):
    """Account for the existing workflow's reads and explicit disposition.

    Classification remains the operator's judgement. The ledger proves which
    full contact thread was delivered and which canonical mutation followed.
    """
    from .operator_executor_protocol import decode
    from email.utils import getaddresses,parsedate_to_datetime
    from datetime import datetime,timezone
    def moment(value):
        if not isinstance(value,str) or not value:
            return None
        try:
            parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError:
            try:parsed=parsedate_to_datetime(value)
            except (TypeError,ValueError):return None
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    def before(left,right):
        return ('end_sequence' not in left or 'start_sequence' not in right
            or left['end_sequence']<right['start_sequence'])
    email=item['email'].lower()
    observations=[]
    for i,thread in enumerate(results):
        argv=thread['argv']
        if not (len(argv)>=3 and argv[:2]==['thread',item['email']] and '--json' in argv and thread['exit_code']==0):
            continue
        summaries=decode(thread['stdout'])
        if not isinstance(summaries,list):continue
        roots={r.get('thread_id') or r.get('id') for r in summaries if isinstance(r,dict)}
        roots={r for r in roots if isinstance(r,str) and r}
        if item.get('thread_id'):roots.intersection_update({item['thread_id']})
        for body in results[i+1:]:
            if (body['argv'][:2]!=['rpc','emails.list_by_thread'] or body['exit_code']!=0 or not before(thread,body)):
                continue
            args=decode(body['argv'][2]);root=args.get('thread_id')
            if root not in roots:continue
            value=decode(body['stdout']);messages=value.get('emails') if isinstance(value,dict) else None
            if (not isinstance(value,dict) or value.get('complete',True) is not True
                    or any(value.get(k) for k in ('error','errors','truncated','has_more','next_cursor'))
                    or not isinstance(messages,list) or not messages or any(not isinstance(m,dict)
                    or m.get('body_complete',True) is not True or any(m.get(k) for k in ('body_truncated','body_error','incomplete'))
                    or not any(isinstance(m.get(k),str) and m[k].strip() for k in ('body','body_text','body_html','text','content')) for m in messages)):
                continue
            inbound=[]
            for message in messages:
                fields=[message.get(k) for k in ('from_email','sender','from') if isinstance(message.get(k),str)]
                senders={address.lower() for _,address in getaddresses(fields)}
                stamp=next((moment(message.get(k)) for k in ('date','received_at','sent_at','created_at') if moment(message.get(k)) is not None),None)
                if email in senders and stamp is not None:inbound.append(stamp)
            if inbound:observations.append((root,thread,body,inbound))
    if not observations:raise ValueError('campaign_reply_full_body_provenance_missing')
    newest_inbound=max(stamp for _,_,_,stamps in observations for stamp in stamps)
    for root,thread,body,stamps in reversed(observations):
        previews=[r for r in results[:results.index(body)] if r['argv']==['campaign','mark',item['contact_id']]]
        preview=previews[-1] if previews else None
        prior=None
        if preview is not None and preview['exit_code']==0 and before(preview,body):
            value=decode(preview['stdout'])
            planned=value.get('would_set') if isinstance(value,dict) else None
            if (isinstance(value,dict) and value.get('ok') is True and value.get('dry_run') is True
                    and value.get('email')==item['email'] and isinstance(planned,dict)
                    and planned.get('contact_id')==item['contact_id'] and isinstance(planned.get('dossier'),dict)):
                prior=moment(planned['dossier'].get('classified_upto'))
        if prior is not None and newest_inbound<=prior:
            evidence_ids={preview['tool_id']}
            evidence_ids.update(r['tool_id'] for _,read,full,_ in observations for r in (read,full))
            return dict(contact_id=item['contact_id'],outcome='held',reason='already_classified',
                tool_ids=list(dict.fromkeys(r['tool_id'] for r in results if r['tool_id'] in evidence_ids)))
        for mark in results:
            argv=mark['argv']
            if (len(argv)<4 or argv[:3]!=['campaign','mark',item['contact_id']] or '--commit' not in argv
                    or mark['exit_code']!=0 or not before(body,mark) or results.index(mark)<=results.index(body)):
                continue
            value=decode(mark['stdout'])
            if not isinstance(value,dict) or value.get('ok') is not True or value.get('dry_run') or value.get('email')!=item['email']:
                continue
            patch=decode(argv[argv.index('--dossier')+1]) if '--dossier' in argv else {}
            state=argv[argv.index('--state')+1] if '--state' in argv else None
            if not isinstance(patch,dict):continue
            classified=moment(patch.get('classified_upto'))
            if classified is not None and (classified not in stamps or prior is not None and classified<=prior):continue
            ids=[thread['tool_id'],body['tool_id']]
            reason=None
            if state is None and patch.get('autoresponder_seen') is True and classified is not None:reason='autoresponder'
            elif state is None and patch.get('escalated') is True and isinstance(patch.get('escalate_reason'),str) and patch['escalate_reason'].strip() and classified is not None:reason='escalated'
            elif state=='replied' and patch.get('outcome')=='declined':reason='declined'
            elif state=='replied' and patch.get('outcome')=='engaged':
                drafts=[r for r in results if r['argv'][:1]==['draft-reply'] and '--thread-id' in r['argv']
                    and r['argv'][r['argv'].index('--thread-id')+1]==root and r['exit_code']==0
                    and results.index(body)<results.index(r)<results.index(mark) and before(body,r) and before(r,mark)
                    and 'engine draft ready: ' in r['stdout'].decode()]
                if len(drafts)==1:ids.append(drafts[0]['tool_id']);reason='engaged'
            if reason:
                return dict(contact_id=item['contact_id'],outcome='worked',reason=reason,tool_ids=ids+[mark['tool_id']])
    raise ValueError('campaign_reply_disposition_missing')


def campaign_work(pending, results):
    from .operator_executor_protocol import decode
    outcomes=[]
    for item in pending:
        if not isinstance(item,dict) or not isinstance(item.get('contact_id'),str) or not item['contact_id']:
            raise ValueError('campaign_item_identity_missing')
        action,contact = item.get('action'),item['contact_id']
        if action == 'evidence_incomplete':
            # Technical missing mailbox evidence remains a failure, never an
            # accepted human hold or silent disappearance from the worklist.
            raise ValueError('campaign_evidence_incomplete')
        if item.get('escalated_to') and action == 'handle_reply':
            outcomes.append(dict(contact_id=contact,outcome='held',reason='human_takeover',tool_ids=[]))
            continue
        if action=='handle_reply':
            outcomes.append(_reply_disposition(item,results))
            continue
        commands={'reconcile':('reconcile',),'send_draft':('queue-draft',)}.get(action)
        if commands is None:
            raise ValueError('campaign_action_unsupported')
        def committed(result,verbs,ok=True):
            argv=result['argv']
            if (len(argv)<4 or argv[:1]!=['campaign'] or argv[1] not in verbs or argv[2]!=contact
                    or '--commit' not in argv or result['exit_code']!=0):
                return None
            value=decode(result['stdout'])
            if (not isinstance(value,dict) or value.get('email')!=item.get('email')
                    or value.get('dry_run') or (ok and value.get('ok') is not True)):
                return None
            return value
        matches=[]
        for index,result in enumerate(results):
            if committed(result,commands) is not None:
                matches.append([result['tool_id']])
            elif action=='send_draft':
                refused=committed(result,('queue-draft',),ok=False)
                if refused is not None and refused.get('ok') is False and refused.get('next')=='reconcile':
                    reconciles=[later for later in results[index+1:] if committed(later,('reconcile',)) is not None
                        and ('end_sequence' not in result or 'start_sequence' not in later or result['end_sequence']<later['start_sequence'])]
                    if len(reconciles)==1:
                        matches.append([result['tool_id'],reconciles[0]['tool_id']])
        if len(matches)!=1:
            raise ValueError('campaign_action_outcome_missing')
        outcomes.append(dict(contact_id=contact,outcome='worked',reason=action,tool_ids=matches[0]))
    return outcomes
