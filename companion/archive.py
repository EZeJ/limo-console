"""Download, commit, verify, then acknowledge. Robot deletes only after ACK."""
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.request import Request,urlopen

ID=re.compile(r'^[A-Za-z0-9_-]{1,100}$')

def checked(value):
    if not isinstance(value,str) or not ID.fullmatch(value):raise ValueError('Invalid archive identifier')
    return value


def json_request(base,path,data=None,timeout=5):
    request=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Host':'127.0.0.1:8765','X-Limo-Control':'1','Content-Type':'application/json'})
    try:
        with urlopen(request,timeout=timeout) as response:return json.load(response)
    except Exception as exc:
        if hasattr(exc,'read'):
            try:raise ValueError(json.loads(exc.read()).get('error',str(exc))) from None
            except json.JSONDecodeError:pass
        raise


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    with temporary.open('w') as file:
        json.dump(value,file,ensure_ascii=False,indent=2,allow_nan=False);file.flush();os.fsync(file.fileno())
    os.replace(temporary,path)
    sync_dir(path.parent)


def sync_dir(path):
    fd=os.open(str(path),os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def sha256_file(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def archive_chunk(base,root,chunk):
    session,instance,chunk_id=(checked(chunk[key]) for key in ['session_id','instance_id','chunk_id'])
    folder=Path(root)/session/instance/'sensors';folder.mkdir(parents=True,exist_ok=True)
    target=folder/(chunk_id+'.mcap')
    expected=chunk['sha256'];size=chunk['bytes']
    if not isinstance(size,int) or size<0 or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Invalid chunk manifest')
    if not target.is_file() or target.stat().st_size!=size or sha256_file(target)!=expected:
        partial=target.with_suffix('.partial')
        digest=hashlib.sha256();count=0
        with urlopen(Request(base+'/recording/chunk?id='+chunk_id,headers={'Host':'127.0.0.1:8765'}),timeout=15) as response,partial.open('wb') as file:
            for block in iter(lambda:response.read(256*1024),b''):
                count+=len(block)
                if count>size:raise ValueError('Archive exceeded declared size')
                file.write(block);digest.update(block)
            file.flush();os.fsync(file.fileno())
        if count!=size or digest.hexdigest()!=expected:raise ValueError('Archive checksum mismatch; robot copy retained')
        os.replace(partial,target);sync_dir(folder)
    atomic_json(target.with_suffix('.manifest.json'),dict(chunk,verified_on_computer=True))
    result=json_request(base,'/recording/ack',{'chunk_id':chunk_id,'bytes':size,'sha256':expected})
    if not result.get('deleted'):raise ValueError('Robot did not acknowledge archival')
    return str(target)
