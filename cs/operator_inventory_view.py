"""Private readable semantic inventory; omitted case detail remains uninspected."""
import json, hashlib, os, shlex, stat, tempfile
from pathlib import Path
A=['version','actor_uid','space_id','thread_key','authoritative_thread_key','component_thread_keys','component_scope_present','source_owner_uid','complete','authority_complete','state','hold_auto_reply','hold_scope','reason','task','events','current_inbound','covered_inbound','provenance']
I=['email','name','subject','last_inbound_date','days_waiting','thread_key','state','reason','_workset_revision','escalated_at','escalated_owner','escalated_reason','days_escalated']
O=['version','actor_uid','space_id','source_id','thread_key','complete','judgement','reason']
S=['actor_uid','mailbox_id','thread_key','observation_only']
F=['message_id','provider_folder','provider_uid','provider_uidvalidity','owner_uid','body_sha256']
AR=['route_digest','current_message_ids','covered_message_ids','reply_evidence']
SR=['message_id','provider','route_digest','raw_header_digest','content_digest','in_reply_to','recipients']
GROUPS=['open','handled','escalated','operational_fixture_discovery','human_work','assignment_audit','assignment_incomplete','resumed','automatic','courtesy','note','read_incomplete','crm_note','triage_workset']
def allowed(d,keys):
 if not isinstance(d,dict) or set(d)-set(keys):raise ValueError('REFUSE unknown object fields '+repr(d))
def validate_types(value,path=()):
 if type(value)is not dict:raise ValueError('REFUSE object type at '+repr(path))
 for key,item in value.items():
  where=path+(key,)
  if key in ('source','digest') and path[-2:]==('assignment','reply_evidence') and item is None:
   continue
  if key in ['discovery','assignment','provider','triage_workset'] or key=='source' and 'held' not in path:
   if type(item)is not dict:raise ValueError('REFUSE object type at '+repr(where))
   validate_types(item,where)
  elif key in ['ancestry','provenance','reply_evidence','selected','deferred','held'] or path==('discovery',) and key not in ['assignment_incomplete','note','read_incomplete','crm_note']:
   if type(item)is not list:raise ValueError('REFUSE object-list type at '+repr(where))
   for element in item:validate_types(element,where)
  elif key in ['component_thread_keys','current_message_ids','covered_message_ids','sources','recipients']:
   if type(item)is not list or any(type(x)is not str for x in item):raise ValueError('REFUSE string-list type at '+repr(where))
  elif key in ['version','pid','started_ticks','exit_code','days_waiting','days_escalated','limit']:
   if type(item)is not int:raise ValueError('REFUSE integer type at '+repr(where))
  elif key in ['component_scope_present','complete','authority_complete','hold_auto_reply','observation_only','assignment_incomplete']:
   if type(item)is not bool:raise ValueError('REFUSE boolean type at '+repr(where))
  elif key in ['task','events','current_inbound','covered_inbound']:
   if item is not None and not (type(item)is list and not item):raise ValueError('REFUSE nonempty or invalid material type at '+repr(where))
  elif key in ['note','read_incomplete','crm_note','identity'] or key=='thread_key' and 'held' in path:
   if item is not None and type(item)is not str:raise ValueError('REFUSE nullable-string type at '+repr(where))
  elif key in ['uid','uidvalidity']:
   if type(item)not in [str,int]:raise ValueError('REFUSE provider identifier type at '+repr(where))
  elif type(item)is not str:raise ValueError('REFUSE string type at '+repr(where))
def validate_binding_types(binding):
 if type(binding)is not dict:raise ValueError('REFUSE binding object type')
 for key,value in binding.items():
  if key=='raw_bytes':
   if type(value)is not int:raise ValueError('REFUSE raw byte length type')
  elif key=='ancestry':
   if type(value)is not list:raise ValueError('REFUSE binding ancestry type')
   for ancestor in value:validate_types(ancestor,('binding','ancestry'))
  elif key in ['native_invocation','current_native_invocation']:
   if type(value)is not dict:raise ValueError('REFUSE native invocation type')
   for name,item in value.items():
    if name=='child_identity':validate_types(item,('binding','native_invocation','child_identity'))
    elif type(item)is not str:raise ValueError('REFUSE native identity string type')
  elif type(value)is not str:raise ValueError('REFUSE binding string type')
def check(d):
 validate_types(d)
 allowed(d,['nonce','owner_uid','ancestry','exit_code','output_sha256','discovery'])
 for x in d['ancestry']:allowed(x,['pid','started_ticks'])
 allowed(d['discovery'],GROUPS)
 for g,v in d['discovery'].items():
  if g=='triage_workset':
   allowed(v,['complete','limit','selected','deferred','held'])
   for k,keys in [('selected',['thread_key','revision','sources']),('deferred',['thread_key','reason','sources']),('held',['thread_key','reason','source','identity'])]:
    for r in v[k]:
     allowed(r,keys)
     if 'identity'in r and not isinstance(r['identity'],(str,type(None))):raise ValueError('REFUSE unclassified held identity')
  elif isinstance(v,list):
   for r in v:
    allowed(r,F if g=='operational_fixture_discovery' else I+['assignment'])
    if 'assignment' not in r:continue
    a=r['assignment'];allowed(a,A+AR)
    for k in ['task','events','current_inbound','covered_inbound']:
     if a.get(k) not in (None,[]):raise ValueError('REFUSE material '+k)
    for p in a.get('provenance',[]):allowed(p,['basis','owner','reason'])
    for o in a.get('reply_evidence',[]):
     allowed(o,O+['source','digest'])
     if 'source'not in o:raise ValueError('REFUSE missing observation source')
     if o['source'] is not None:
      allowed(o['source'],S+SR)
      if 'provider'in o['source']:allowed(o['source']['provider'],['folder','uid','uidvalidity'])
  elif g not in ['assignment_incomplete','note','read_incomplete','crm_note']:raise ValueError('REFUSE group type')
def produce(d,binding):
 bounded(d);validate_binding_types(binding);check(d);legend=[];ids={};out=[]
 def enc(v,key=''):
  kind={'thread_key':'root','authoritative_thread_key':'root','component_thread_keys':'root','actor_uid':'actor','source_owner_uid':'actor','owner_uid':'actor','space_id':'space','mailbox_id':'mailbox'}.get(key)
  if kind and isinstance(v,str):
   pair=(kind,v)
   if pair not in ids:
    n=1+sum(x[1]==kind for x in legend);ident=kind[0]+str(n);ids[pair]=ident;legend.append([ident,kind,v])
   return ['id',ids[pair]]
  if isinstance(v,list):
   result=[enc(x,key) for x in v]
   if result==['absent'] or len(result)==2 and type(result[0])is str and result[0] in ['id','literal']:return ['literal',result]
   return result
  if isinstance(v,dict):return {k:enc(x,k) for k,x in v.items()}
  return v
 def cells(r,keys):return [enc(r[k],k) if k in r else ['absent'] for k in keys]
 def table(name,headers,rows):out.append({'table':name,'columns':headers});out.extend(rows)
 table('binding',['schema','raw_sha256','raw_bytes','owner_uid','nonce','ancestry','exit_code','source_identity','native_invocation','current_native_invocation'],[['cs.semantic_inventory.v1',binding['raw_sha256'],binding['raw_bytes'],enc(d['owner_uid'],'owner_uid'),d['nonce'],d['ancestry'],d['exit_code'],binding['source_identity'],binding['native_invocation'],binding['current_native_invocation']]])
 table('groups',['name','type','count','scalar'],[[g,type(v).__name__,len(v) if isinstance(v,(list,dict)) else None,v if not isinstance(v,(list,dict)) else ['absent']] for g,v in d['discovery'].items()])
 assignments=[];observations=[];protected=[];refs=[]
 for g,v in d['discovery'].items():
  if not isinstance(v,list):continue
  if g=='operational_fixture_discovery':
   protected.extend([[g,i]+cells(r,F) for i,r in enumerate(v)]);continue
  cols=[k for k in I if any(k in r for r in v)]
  table('inventory:'+g,['group','index']+cols,[[g,i]+cells(r,cols) for i,r in enumerate(v)])
  for i,r in enumerate(v):
   if 'assignment'not in r:continue
   a=r['assignment'];assignments.append([g,i]+cells(a,A)+[len(a.get('current_message_ids',[])),len(a.get('covered_message_ids',[])),len(a.get('reply_evidence',[]))])
   refs.append([g,i,[[k,len(a[k]) if isinstance(a[k],list) else None] for k in AR if k in a]])
   for j,o in enumerate(a.get('reply_evidence',[])):observations.append([g,i,j]+cells(o,O)+([None]*len(S) if o['source'] is None else cells(o['source'],S)))
 table('assignments',['group','index']+A+['current_message_ids_count','covered_message_ids_count','reply_evidence_count'],assignments)
 table('observations',['group','index','observation_index']+O+['source.'+k for k in S],observations)
 table('protected_originals',['group','index']+F,protected)
 w=d['discovery']['triage_workset'];table('workset',['complete','limit'],[cells(w,['complete','limit'])])
 for name,cols in [('selected',['thread_key','revision','sources']),('deferred',['thread_key','reason','sources']),('held',['thread_key','reason','source','identity'])]:table(name,['index']+cols,[[i]+cells(r,cols) for i,r in enumerate(w[name])])
 table('raw_details',['group','index','present_fields_and_counts'],refs)
 legend_record={'table':'identity_legend','columns':['id','kind','value']}
 notes={'legend':'JSON-lines tables; array rows follow explicit headers. ["absent"] means field absent, null/false/empty retain exact types; four null source.* cells mean source:null, while object sources retain field presence; null observation digest means no verification digest and grants no authority; ["id",ID] resolves typed identities here. All RAW REF detail is UNINSPECTED; selected-root fresh deep reads before effects mandatory. Engine decisions remain authoritative; no MIME authentication claim.','raw_reference_paths':{'root':['output_sha256'],'assignment':['route_digest','current_message_ids','covered_message_ids','reply_evidence'],'observation':['digest'],'source':['message_id','provider.folder','provider.uid','provider.uidvalidity','route_digest','raw_header_digest','content_digest','in_reply_to','recipients']},'lookup':'raw.discovery[group][index].assignment; observation index preserves order; presence of optional RAW REF leaves is inspected from retained raw; reply_evidence count is exact; raw hash binds all details.'}
 return '\n'.join(json.dumps(x,ensure_ascii=False,separators=(',',':')) for x in [notes,legend_record]+legend+out)

MAX_BYTES = 4 * 1024 * 1024

def bounded(value):
    cells = 0
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        cells += 1
        if depth > 64 or cells > 250000:
            raise ValueError('REFUSE inventory complexity')
        if isinstance(item, dict):
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in item)

def source_identity():
    root = Path(__file__).parent
    files = [[str(p.relative_to(root)), hashlib.sha256(p.read_bytes()).hexdigest()]
             for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def read_private(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600
                or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES):
            raise ValueError('unsafe inventory artifact')
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('oversized inventory artifact')
    return raw

def directory(context):
    path = Path(context['directory'])
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError('unsafe inventory directory')
    meta = path.lstat()
    if meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o700 or not stat.S_ISDIR(meta.st_mode):
        raise ValueError('unsafe inventory directory')
    return path

def binding_for(raw, record, context):
    if (record['nonce'] != context['nonce'] or record['owner_uid'] != context['owner_uid']
            or record['ancestry'][-1] != context['supervisor']):
        raise ValueError('inventory context differs')
    native = {'child_identity': record['ancestry'][-2]}
    return {'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
            'owner_uid': record['owner_uid'], 'nonce': record['nonce'], 'ancestry': record['ancestry'],
            'source_identity': source_identity(), 'native_invocation': native,
            'current_native_invocation': native}

def exclusive(path, raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('oversized inventory view')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())

def _page(raw, requested):
    """Choose bytes that native whitespace trimming cannot change."""
    size = len(raw)
    if not 0 <= requested < size:
        raise ValueError('invalid inventory page start')

    def previous(position):
        position -= 1
        while position > 0 and raw[position] & 0xc0 == 0x80:
            position -= 1
        return position

    def character(position):
        end = position + 1
        while end < size and raw[end] & 0xc0 == 0x80:
            end += 1
        return raw[position:end].decode('utf-8')

    start = requested
    while start > 0 and raw[start] & 0xc0 == 0x80:
        start -= 1
    while character(start).isspace():
        if start == 0:
            raise ValueError('undeliverable inventory prefix')
        start = previous(start)
    end = min(size, start + 8192)
    while end < size and raw[end] & 0xc0 == 0x80:
        end -= 1
    while end > start:
        last = previous(end)
        if not raw[last:end].decode('utf-8').isspace():
            break
        end = last
    if end <= start:
        raise ValueError('undeliverable inventory page')
    return start, end


def _pages(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('invalid inventory page source')
    raw.decode('utf-8')
    pages = []
    start = 0
    covered = 0
    while covered < len(raw):
        begin, end = _page(raw, start)
        if begin > covered or end <= covered:
            raise ValueError('nonadvancing inventory page plan')
        pages.append((begin, end))
        covered = end
        start = max(0, end - 128)
    return pages


def _page_text(path, begin, end):
    return ('dd if=' + shlex.quote(str(path)) + ' bs=1 skip=' + str(begin)
            + ' count=' + str(end - begin) + ' status=none')


def page_command(path, start, raw=None):
    raw = read_private(path) if raw is None else raw
    return _page_text(path, *_page(raw, start))


def progress_value(envelope, path, covered, raw=None):
    raw = read_private(path) if raw is None else raw
    size = envelope['view_bytes']
    if size != len(raw) or not 0 <= covered <= size:
        raise ValueError('invalid inventory progress bounds')
    pages = _pages(raw)
    return {'schema': 'cs.semantic_inventory.progress.v1', 'view_sha256': envelope['view_sha256'],
            'view_bytes': size, 'raw_sha256': envelope['raw_sha256'], 'nonce': envelope['nonce'],
            'owner_uid': envelope['owner_uid'], 'supervisor': envelope['supervisor'],
            'source_identity': envelope['source_identity'], 'covered': [[0, covered]] if covered else [],
            'uncovered': [[covered, size]] if covered < size else [],
            'next_command': next((_page_text(path, begin, end) for begin, end in pages if end > covered), None),
            'page_plan': [_page_text(path, begin, end) for begin, end in pages]}

def envelope_bytes(value):
    """Standard JSON values, ASCII transport without trim-sensitive bytes."""
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).replace(' ', '\\u0020').encode('ascii')


def capture(context):
    path = directory(context)
    raw = read_private(path / 'discovery.json')
    record = json.loads(raw)
    binding = binding_for(raw, record, context)
    text = produce(record, binding)
    sources = None
    if context.get('workset_enabled') is True:
        from . import operator_inventory_material as material
        record = material.parse(raw)
        records, sources = material.load_sources(path, context, record['discovery'], read_private)
        text = material.append(text, records)
    view = text.encode()
    if len(view) > MAX_BYTES:
        raise ValueError('oversized inventory view')
    envelope = {'schema': 'cs.semantic_inventory.envelope.v1', **binding,
                'supervisor': context['supervisor'], 'view_sha256': hashlib.sha256(view).hexdigest(),
                'view_bytes': len(view),
                'page_plan': [_page_text(path / 'inventory-view.jsonl', begin, end)
                              for begin, end in _pages(view)]}
    if sources is not None:
        envelope['schema'] = 'cs.semantic_inventory.envelope.v2'
        envelope['workset_sources'] = sources
    progress = progress_value(envelope, path / 'inventory-view.jsonl', 0, view)
    exclusive(path / 'inventory-view.jsonl', view)
    exclusive(path / 'inventory-view-envelope.json', envelope_bytes(envelope))
    exclusive(path / 'inventory-view-progress.json', json.dumps(progress).encode())

def load(context):
    path = directory(context)
    raw = read_private(path / 'discovery.json')
    record = json.loads(raw)
    envelope = json.loads(read_private(path / 'inventory-view-envelope.json'))
    view = read_private(path / 'inventory-view.jsonl')
    binding = binding_for(raw, record, context)
    expected = {'schema': 'cs.semantic_inventory.envelope.v1', **binding,
                'supervisor': context['supervisor'], 'view_sha256': hashlib.sha256(view).hexdigest(), 'view_bytes': len(view),
                'page_plan': [_page_text(path / 'inventory-view.jsonl', begin, end)
                              for begin, end in _pages(view)]}
    text = produce(record, binding)
    if context.get('workset_enabled') is True:
        from . import operator_inventory_material as material
        record = material.parse(raw)
        records, sources = material.load_sources(path, context, record['discovery'], read_private)
        expected['schema'] = 'cs.semantic_inventory.envelope.v2'
        expected['workset_sources'] = sources
        text = material.append(text, records)
    if envelope != expected or view != text.encode():
        raise ValueError('inventory binding or projection differs')
    return path, view, envelope

def effect_words(words):
    """Recognize all canonical CLI prefixes and argparse account spellings."""
    canonical = words
    if words[:3] in (['.venv/bin/python', '-m', 'cs'], ['.venv/bin/python3', '-m', 'cs'], ['python', '-m', 'cs'], ['python3', '-m', 'cs']):
        canonical = words[3:]
    elif words[:1] in (['cs'], ['.venv/bin/cs']):
        canonical = words[1:]
    else:
        return False
    while canonical:
        option = canonical[0].split('=', 1)[0]
        if not (option.startswith('--') and len(option) >= 3 and '--account'.startswith(option)):
            break
        canonical = canonical[1:] if '=' in canonical[0] else canonical[2:]
    return canonical[:1] in (['draft-reply'], ['reply-send'], ['draft-send'], ['chat']) or canonical[:2] == ['campaign', 'queue-draft']


def coverage(events, path, view):
    uses = {}
    seen = set()
    completed = set()
    covered = 0
    early = False
    for event in events:
        message = event.get('message')
        blocks = message.get('content', []) if isinstance(message, dict) else []
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                args = block.get('input') or {}
                try:
                    words = shlex.split(args.get('command', ''))
                except ValueError:
                    continue
                if effect_words(words):
                    early = early or covered != len(view)
                if (len(words) != 6 or words[:3] != ['dd', 'if=' + str(path), 'bs=1']
                        or words[5] != 'status=none' or args.get('run_in_background', False) is not False):
                    continue
                if not words[3].startswith('skip=') or not words[4].startswith('count='):
                    continue
                try:
                    start, count = int(words[3][5:]), int(words[4][6:])
                except ValueError:
                    continue
                tool = block.get('id')
                if not isinstance(tool, str) or not tool or tool in seen:
                    raise ValueError('ambiguous inventory tool')
                seen.add(tool)
                if start >= 0 and 0 < count <= 8192:
                    uses[tool] = (start, count, event.get('session_id'))
            elif block.get('type') == 'tool_result' and block.get('tool_use_id') in seen:
                if block.get('tool_use_id') in completed:
                    raise ValueError('duplicate inventory result')
                completed.add(block.get('tool_use_id'))
                if block.get('tool_use_id') not in uses:
                    continue
                start, count, session = uses.pop(block['tool_use_id'])
                output = block.get('content')
                if isinstance(output, list):
                    output = '\n'.join(x.get('text', '') for x in output if isinstance(x, dict) and x.get('type') == 'text')
                expected = view[start:start + count].decode('utf-8', 'replace')
                if (block.get('is_error', False) is False and event.get('session_id') == session
                        and expected and output == expected and start <= covered):
                    covered = max(covered, min(len(view), start + count))
    return covered, early

def audit(events, context):
    path, view, envelope = load(context)
    covered, early = coverage(events, path / 'inventory-view.jsonl', view)
    envelope_raw = read_private(path / 'inventory-view-envelope.json')
    envelope_covered, envelope_early = coverage(events, path / 'inventory-view-envelope.json', envelope_raw)
    from .operator_context_delivery import delivered
    automatic = delivered(events, view, envelope_raw, envelope)
    return automatic or (covered == len(view) and envelope_covered == len(envelope_raw) and not early and not envelope_early)

def update_progress(events, context):
    path, view, envelope = load(context)
    covered, _ = coverage(events, path / 'inventory-view.jsonl', view)
    target = path / 'inventory-view-progress.json'
    prior = json.loads(read_private(target))
    value = progress_value(envelope, path / 'inventory-view.jsonl', covered, view)
    if prior == value:
        return
    fd, name = tempfile.mkstemp(prefix='.inventory-progress-', dir=path)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(json.dumps(value).encode())
            stream.flush()
            os.fsync(stream.fileno())
        read_private(target)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)
