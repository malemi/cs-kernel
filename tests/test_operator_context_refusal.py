"""Constructed zero-work refusal compatibility; no native/model/provider calls."""
import copy
import json
from cs.operator_recovery import Attempt, _prework_refusal


def refusal(status, output=''):
    events=[{'type':'system','subtype':'init'},
            {'type':'assistant','error':'billing_error' if status==402 else 'rate_limit','is_api_error_message':True,
             'message':{'content':[{'type':'text','text':'constructed refusal'}]}},
            {'type':'result','terminal_reason':'api_error','api_error_status':status,'is_error':True,
             'total_cost_usd':0,'modelUsage':{},'usage':{'input_tokens':0,'output_tokens':0},'subagent_stats':{'spawned':0}}]
    if status==429:events.insert(1,{'type':'rate_limit_event','rate_limit_info':{'status':'rejected','rateLimitType':'seven_day'}})
    base={'type':'system','hook_id':'prework','hook_name':'UserPromptSubmit','hook_event':'UserPromptSubmit'}
    hooks=[{**base,'subtype':'hook_started'},{**base,'subtype':'hook_response','output':output,'stdout':output,'stderr':'','exit_code':0,'outcome':'success'}]
    events=hooks+events
    for index,event in enumerate(events):event.update(uuid=str(index),session_id='constructed-session')
    return events

positives=negatives=0
for status in (402,429):
    for output in ('','Now: 2026-10-19 10:19:29 UTC  |  06:19 EDT New York  |  12:19 CEST Roma\n'):
        events=refusal(status,output)
        assert _prework_refusal(Attempt(1,events));positives+=1
        assert _prework_refusal(Attempt(1,events[2:]));positives+=1
    for mutation in ('foreign','unpaired','failed','unknown','tool-boundary','tool-work','usage','cost','inventory','arbitrary','stderr'):
        events=refusal(status)
        if mutation=='foreign':events[1]['session_id']='foreign'
        elif mutation=='unpaired':events.pop(0)
        elif mutation=='failed':events[1]['exit_code']=2
        elif mutation=='unknown':events[1]['subtype']='hook_progress'
        elif mutation=='tool-boundary':
            for event in events[:2]:event.update(hook_event='PostToolUse',hook_name='PostToolUse:Read')
        elif mutation=='tool-work':events.insert(-1,{'type':'assistant','session_id':'constructed-session','message':{'content':[{'type':'tool_use','name':'Bash'}]}})
        elif mutation=='usage':events[-1]['usage']['input_tokens']=1
        elif mutation=='cost':events[-1]['total_cost_usd']=0.01
        elif mutation=='inventory':events[1]['output']=events[1]['stdout']=json.dumps({'hookSpecificOutput':{'hookEventName':'UserPromptSubmit','additionalContext':'cs.inventory.context.v1'}})
        elif mutation=='arbitrary':events[1]['output']=events[1]['stdout']='arbitrary prework context'
        elif mutation=='stderr':events[1]['stderr']='failure'
        assert not _prework_refusal(Attempt(1,events)),(status,mutation)
        negatives+=1
print(f'Constructed refusal controls: {positives} positive and {negatives} negative PASS (402/429; empty/retained datetime; no work/usage/context replay).')
