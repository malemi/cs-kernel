"""Bounded maintenance of fixed legacy producers; active writers keep their evidence."""
from __future__ import annotations

import fcntl
import json
import os
import stat
import re
import time
from pathlib import Path
from types import SimpleNamespace

from .observability_producers import emit

AGE_SECONDS = 7*86400
LOG_BYTES = 32*1024**2
NATIVE_BYTES = 96*1024**2


def _capture_files(directory):
    """Inventory only the fixed, shallow capture layout used by the supervisor."""
    fixed={'native-stream.jsonl','native-stream.json','discovery.json','inventory-view.jsonl','inventory-view-envelope.json','inventory-view-progress.json','inventory-context-settings.json','.observability-active','dossier-context-failure.json'}
    contents=list(directory.iterdir())
    if len(contents)>4096:
        raise ValueError('capture file inventory exceeds bound')
    files=[]
    complete=True
    for path in contents:
        if path.is_dir() and not path.is_symlink():
            _safe(path,True)
            business=path.name=='business-reads'
            dossier=re.fullmatch(r'dossier-attempt-[A-Za-z0-9_-]+',path.name) is not None
            if not (business or dossier):
                complete=False
                continue
            children=list(path.iterdir())
            if len(children)>4096:
                raise ValueError('nested capture inventory exceeds bound')
            for child in children:
                meta=_safe(child)
                known=(re.fullmatch(r'\d+-\d+\.json',child.name) is not None if business else child.name in {'request.json','phase.json','result.json','worker-result.json'})
                files.append((child,meta,known))
        else:
            meta=_safe(path)
            known=path.name in fixed or re.fullmatch(r'workset-[a-z0-9-]+\.json|context-delivered-[a-f0-9]+|dossier-root-[a-f0-9]+\.json',path.name) is not None
            files.append((path,meta,known))
    return files,complete


def _safe(path, directory=False):
    info = path.lstat()
    if info.st_uid != os.getuid() or path.is_symlink() or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) or not directory and info.st_nlink != 1:
        raise PermissionError('unsafe retained log')
    return info


def _trim_log(base, log, now, budget):
    dropped=0
    guard=os.open(base/'cs_operator.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        _safe(base/'cs_operator.lock')
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if log.exists():
            meta=_safe(log)
            if meta.st_size > budget//2 or now-meta.st_mtime > AGE_SECONDS:
                fd=os.open(log,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK)
                try:
                    current=os.fstat(fd)
                    if current.st_ino!=meta.st_ino or current.st_nlink!=1:
                        raise PermissionError('log changed during maintenance')
                    data=b'' if now-meta.st_mtime > AGE_SECONDS else os.pread(fd,budget//2,max(0,meta.st_size-budget//2))
                    archive=base/'cs_operator.log.1'
                    archive_fd=os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
                    try:
                        _safe(archive)
                        os.ftruncate(archive_fd,0)
                        if os.write(archive_fd,data)!=len(data):
                            raise OSError("incomplete retained log write")
                    finally:
                        os.close(archive_fd)
                    os.ftruncate(fd,0)
                    dropped+=1
                finally:
                    os.close(fd)
        archive=base/'cs_operator.log.1'
        if archive.exists():
            meta=_safe(archive)
            if now-meta.st_mtime>AGE_SECONDS:
                archive.unlink();dropped+=1
            elif meta.st_size>budget//2:
                fd=os.open(archive,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK)
                try:
                    current=os.fstat(fd)
                    if current.st_ino!=meta.st_ino or current.st_nlink!=1:
                        raise PermissionError('archive changed during maintenance')
                    data=os.pread(fd,budget//2,max(0,meta.st_size-budget//2))
                    os.ftruncate(fd,0)
                    if os.write(fd,data)!=len(data):
                        raise OSError('incomplete retained archive write')
                    dropped+=1
                finally:
                    os.close(fd)
        return dropped
    finally:
        os.close(guard)


def _live(directory):
    marker=directory/'.observability-active'
    if not marker.exists():
        return False
    if _safe(marker).st_size>1024:
        raise ValueError('oversized capture identity')
    pid,start=json.loads(marker.read_text())
    if type(pid) is not int or not isinstance(start,str) or not start.isdigit():
        raise ValueError('invalid capture identity')
    try:
        actual=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
        return actual==start
    except (OSError,IndexError):
        return False


def maintain(settings, *, active_directory=None, now=None, log_bytes=LOG_BYTES, native_bytes=NATIVE_BYTES):
    """Prune only known inactive producers; report inability to meet a cap honestly."""
    now=time.time() if now is None else now
    dropped=0
    complete=True
    try:
        base=settings.state_dir
        if not base.exists():
            return {'complete':True,'removed':0}
        _safe(base,True)
        lock=os.open(base/'observability-retention.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
        try:
            _safe(base/'observability-retention.lock')
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            try:
                dropped+=_trim_log(base,settings.log_path,now,log_bytes)
            except BlockingIOError:
                pass
            managed=[path for path in (settings.log_path,base/'cs_operator.log.1') if path.exists()]
            managed_metadata=[_safe(path) for path in managed]
            if sum(meta.st_size for meta in managed_metadata)>log_bytes or any(now-meta.st_mtime>AGE_SECONDS for meta in managed_metadata):
                complete=False
            native=[]
            root=base/'operator-runs'
            if root.exists():
                _safe(root,True)
                runs=list(root.glob('run-*'))
                if len(runs)>4096:
                    raise ValueError('native inventory exceeds bound')
                for directory in runs:
                    _safe(directory,True)
                    protected=(active_directory is not None and directory==Path(active_directory)) or _live(directory)
                    files,known_layout=_capture_files(directory)
                    complete=complete and known_layout
                    for path,meta,known in files:
                        native.append((path,meta,protected or not known))
                        if not known and now-meta.st_mtime>AGE_SECONDS:
                            complete=False
                total=sum(meta.st_size for _,meta,_ in native)
                for path,meta,protected in sorted(native,key=lambda item:item[1].st_mtime):
                    if not protected and (total>native_bytes or now-meta.st_mtime>AGE_SECONDS):
                        path.unlink();total-=meta.st_size;dropped+=1
                complete=complete and total<=native_bytes
            if complete:
                emit(settings,'cleanup','result',reason='none',count=dropped)
            if not complete:
                emit(settings,'cleanup','failed',reason='logging')
            return {'complete':complete,'removed':dropped}
        finally:
            os.close(lock)
    except Exception:
        emit(settings,'cleanup','failed',reason='logging')
        return {'complete':False,'removed':dropped}


def prune_for_state(state_dir, *, owner_uid='', active_directory=None):
    """Service-only maintenance adapter for an explicitly configured state root."""
    base=Path(state_dir)
    return maintain(SimpleNamespace(state_dir=base,log_path=base/'cs_operator.log',engine_owner_uid=owner_uid),active_directory=active_directory)


def active(directory):
    """Bind a capture to its live supervisor's PID and OS start identity."""
    try:
        start=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
        fd=os.open(Path(directory)/'.observability-active',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump([os.getpid(),start],stream)
    except Exception:
        pass
