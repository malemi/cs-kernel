"""Private mount initialization requiring CHOWN only; safe on every pod restart."""

INIT_SCRIPT = """import os,pathlib
r=pathlib.Path(os.environ.get('OPERATOR_INIT_STATE','/state'))
s=pathlib.Path(os.environ.get('OPERATOR_INIT_SOURCE','/configuration'))
if r.is_symlink(): raise ValueError('Unsafe state mount')
# Reclaim only the known mount/config directories before traversing them. This
# works with CHOWN alone even when the prior pod left private user-owned modes.
os.chown(r,0,0);r.chmod(0o700)
c=r/'config'
if c.is_symlink(): raise ValueError('Unsafe configuration directory')
c.mkdir(exist_ok=True)
os.chown(c,0,0);c.chmod(0o700)
for n in ('watchdog.json','notify.json'):
 p=c/n;t=c/(n+'.pending')
 if p.is_symlink() or t.exists() or t.is_symlink(): raise ValueError('Unsafe configuration file')
 with t.open('xb') as out: out.write((s/n).read_bytes())
 t.chmod(0o600);os.chown(t,10001,10001);os.replace(t,p)
os.chown(c,10001,10001)
os.chown(r,10001,10001)
"""
