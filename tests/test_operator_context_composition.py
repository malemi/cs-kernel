"""Constructed Bash carrier plus exact retained hook shapes; no native launch."""
import copy
import json
from pathlib import Path
import runpy
import sys
from cs.operator_native_composition import composition
from cs.operator_native_hooks import hook_indices

fixture=runpy.run_path(str(Path(__file__).with_name('test_operator_native_composition.py')))
if len(sys.argv)>1:
    actual=[json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()]
    indices=hook_indices(actual)
    hooks=[copy.deepcopy(e) for i,e in enumerate(actual) if i in indices]
    assert len(hooks)==18
    label='retained actual M0 hook fields/payloads, constructed Bash carrier and rebound session/UUID'
else:
    hooks=[]
    for index,kind in enumerate(('UserPromptSubmit','MessageDisplay','PreToolUse','PostToolUse')):
        common={'type':'system','hook_id':str(index),'hook_name':kind if kind in ('UserPromptSubmit','MessageDisplay') else kind+':Read','hook_event':kind}
        hooks.extend([{**common,'subtype':'hook_started'}, {**common,'subtype':'hook_response','output':'','stdout':'','stderr':'','exit_code':0,'outcome':'success'}])
    label='constructed observed hook schemas'
carrier=fixture['constructed']('automatic')
events=fixture['seal'](hooks[:2]+carrier[:-1]+hooks[2:]+carrier[-1:])
before=copy.deepcopy(events)
result=composition(events,fixture['producer']())
assert result is not None and events==before
assert sum(row['kind'].startswith('hook_') for row in result['proof']['removed'])==len(hooks)
for index in range(len(events)):
    if events[index].get('subtype')!='hook_response':continue
    for key,value in [('session_id','foreign'),('exit_code',2),('subtype','hook_progress')]:
        bad=copy.deepcopy(events);bad[index][key]=value
        assert composition(bad,fixture['producer']()) is None
bad=copy.deepcopy(events);bad.pop(0)
assert composition(bad,fixture['producer']()) is None
print(label+': pre-init/full composition, original order, foreign/failure/unknown/unpaired controls PASS')
