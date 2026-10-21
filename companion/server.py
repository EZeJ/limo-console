#!/usr/bin/env python3
"""Loopback console gateway and computer recording companion."""
import argparse
from http.client import HTTPException
import fcntl
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import mimetypes
import re
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit,parse_qs
from .coordinator import Coordinator
from .datasets import Datasets


class Gateway:
    def __init__(self,robot_url,data_dir):
        self.base=robot_url
        self.browse_only=robot_url is None
        self.data_dir=Path(data_dir).expanduser().resolve()
        self.coordinator=Coordinator(robot_url or 'http://127.0.0.1:1',self.data_dir)
        self.datasets=Datasets(self.data_dir)
        self.restart_lock=threading.Lock()
        self.start_error=''
        self.initializing=False
        self.finishing=False

    def start(self):
        with self.restart_lock:
            if self.coordinator.active or self.finishing:return
            self.initializing=True
            profile=self.coordinator.pending_profile or self.coordinator.profile
            self.coordinator=Coordinator(self.base,self.data_dir)
            try:self.coordinator.start(profile);self.start_error=''
            except Exception as exc:self.start_error=str(exc);self.coordinator.fault(exc)
            finally:self.initializing=False

    def status(self):
        state=self.coordinator.status()
        state.update(initializing=self.initializing,finishing=self.finishing)
        if self.start_error:state['error']=self.start_error
        return state

    def finish(self):
        with self.restart_lock:
            if self.finishing or self.initializing:return
            self.finishing=True
            try:self.coordinator.close(interrupted=False)
            finally:self.finishing=False


def make_handler(gateway,port):
    class Handler(BaseHTTPRequestHandler):
        def valid(self):
            return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')
        def answer(self,value,code=200):
            data=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def proxy(self,body=None):
            if gateway.browse_only:return self.answer({'error':'Data browsing only; no robot connection'},503)
            request=Request(gateway.base+self.path,data=body,headers={'Host':'127.0.0.1:8765','X-Limo-Control':'1','Content-Type':'application/json'})
            try:response=urlopen(request,timeout=25)
            except HTTPError as exc:response=exc
            except (URLError,OSError,HTTPException) as exc:return self.answer({'error':'Robot connection unavailable: '+str(exc)},503)
            with response:
                if response.status==200 and response.headers.get_content_type()=='application/json':
                    state=json.load(response)
                    if isinstance(state,dict) and 'mode' in state and 'recording' in state:
                        remote=state['recording'];local=gateway.status()
                        local['ready']=bool(local['healthy'] and remote.get('ready'))
                        if remote.get('error') and not local['error']:local['error']=remote['error']
                        state['recording']=local
                    return self.answer(state)
                self.send_response(response.status)
                for header in ['Content-Type','Content-Length','Content-Disposition','X-Limo-Frame']:
                    if response.headers.get(header):self.send_header(header,response.headers[header])
                self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Options','DENY');self.end_headers()
                try:
                    for block in iter(lambda:response.read(256*1024),b''):self.wfile.write(block)
                except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            if not self.valid():return self.answer({'error':'Host rejected'},403)
            path=urlsplit(self.path).path
            static={'/data':'data.html','/data.html':'data.html','/data.js':'data.js','/data.css':'data.css',
                    '/messages.js':'messages.js','/i18n.js':'i18n.js','/style.css':'style.css'}
            if path=='/' and gateway.browse_only:path='/data'
            if path in static:
                return self.send_file(Path(__file__).resolve().parents[1]/'robot/web'/static[path])
            if path.startswith('/local/data'):
                try:
                    query=parse_qs(urlsplit(self.path).query)
                    if path=='/local/data':return self.answer(gateway.datasets.catalog())
                    session,instance=query['session'][0],query['instance'][0]
                    if path=='/local/data/detail':return self.answer(gateway.datasets.describe(session,instance))
                    if path=='/local/data/file':return self.send_file(gateway.datasets.file(session,instance,query['file'][0]))
                    if path=='/local/data/bundle':return self.send_file(gateway.datasets.bundle_file(session,instance))
                    if path=='/local/data/frame':
                        data,kind=gateway.datasets.frame(session,instance,int(query['index'][0]))
                        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
                    return self.answer({'error':'Unknown data endpoint'},404)
                except (ValueError,KeyError,OSError) as exc:return self.answer({'error':str(exc)},400)
            if path=='/local/recording/status':return self.answer(gateway.status())
            if path=='/local/instances':return self.answer({'instances':gateway.coordinator.instances})
            if path=='/camera.jpg' and gateway.coordinator.active and gateway.coordinator.latest_frame:
                data,kind,meta=gateway.coordinator.latest_frame
                if time.time_ns()-meta['receive_wall_ns']>2*10**9:return self.answer({'error':'Camera frame is stale'},503)
                self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers()
                try:self.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError):pass
                return
            self.proxy()
        def send_file(self,path):
            size=path.stat().st_size;start,end=0,size-1;partial=False
            value=self.headers.get('Range')
            if value:
                match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
                if match and any(match.groups()):
                    if match[1]:start=int(match[1]);end=min(end,int(match[2])) if match[2] else end
                    else:start=max(0,size-int(match[2]))
                    partial=True
                if not partial or start>end or start>=size:
                    self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return
            kind=mimetypes.guess_type(str(path).removesuffix('.partial'))[0] or 'application/octet-stream'
            self.send_response(206 if partial else 200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(max(0,end-start+1)))
            self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','private, no-store');self.send_header('X-Content-Type-Options','nosniff')
            if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            try:
                with path.open('rb') as file:
                    file.seek(start);remaining=end-start+1
                    while remaining>0:
                        block=file.read(min(256*1024,remaining))
                        if not block:break
                        self.wfile.write(block);remaining-=len(block)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_POST(self):
            origin=self.headers.get('Origin')
            if not self.valid() or self.headers.get('X-Limo-Control')!='1' or (origin and origin!='http://'+self.headers.get('Host')):
                return self.answer({'error':'Origin or control header rejected'},403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<=length<=16384:raise ValueError('Request too large')
                body=self.rfile.read(length);data=json.loads(body or b'{}')
                if self.path=='/local/data/export':return self.answer(gateway.datasets.export(data['session'],data['instance']),202)
                if self.path=='/local/data/package':return self.answer(gateway.datasets.bundle(data['session'],data['instance']),202)
                if self.path=='/local/data/open-folder':
                    folder=gateway.datasets.folder(data['session'],data['instance'])
                    subprocess.Popen(['open' if sys.platform=='darwin' else 'xdg-open',str(folder)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    return self.answer({'opened':str(folder)})
                if gateway.browse_only:return self.answer({'error':'Data browsing only; no robot connection'},403)
                if self.path=='/local/recording/start':
                    threading.Thread(target=gateway.start,daemon=True).start()
                    return self.answer({'accepted':True},202)
                if self.path=='/local/recording/next':return self.answer(gateway.coordinator.next(data['request_id'],data.get('name','')))
                if self.path=='/local/recording/profile':return self.answer(gateway.coordinator.stage_profile(data))
                if self.path=='/local/recording/retry':return self.answer(gateway.coordinator.retry())
                if self.path=='/local/recording/open-folder':
                    command=['open',str(gateway.data_dir)] if sys.platform=='darwin' else ['xdg-open',str(gateway.data_dir)]
                    subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    return self.answer({'opened':str(gateway.data_dir)})
                if self.path=='/local/recording/finish':
                    threading.Thread(target=gateway.finish,daemon=True).start()
                    return self.answer({'accepted':True},202)
                if self.path.startswith('/local/'):return self.answer({'error':'Unknown local endpoint'},404)
                self.proxy(body)
            except (ValueError,KeyError,TypeError,OSError,TimeoutError) as exc:self.answer({'error':str(exc)},400)
        def log_message(self,*args):pass
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh',help='SSH account and hostname; credentials are handled by SSH')
    parser.add_argument('--ssh-control-path')
    parser.add_argument('--robot-url',help='Existing local SSH-forward URL, for integration testing')
    parser.add_argument('--browse-only',action='store_true',help='Browse local recordings without connecting to a robot')
    parser.add_argument('--port',type=int,default=18765)
    parser.add_argument('--data-dir',default=str(Path.home()/'Documents'/'Limo Console'/'recordings'))
    args=parser.parse_args()
    if not args.browse_only and bool(args.ssh)==bool(args.robot_url):parser.error('Choose --ssh, --robot-url or --browse-only')
    if args.browse_only and (args.ssh or args.robot_url):parser.error('Browsing mode cannot connect to a robot')
    root=Path(args.data_dir).expanduser().resolve();root.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=(root/'.companion.lock').open('a')
    try:
        if not args.browse_only:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Another recording companion owns this data directory')
    tunnel=None
    if args.ssh:
        if args.ssh.startswith('-') or '@' not in args.ssh:parser.error('Use USER@ROBOT_HOST')
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));tunnel_port=sock.getsockname()[1]
        command=['ssh','-N','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=15']
        if args.ssh_control_path:command+=['-o','ControlPath='+args.ssh_control_path]
        command+=['-L',f'127.0.0.1:{tunnel_port}:127.0.0.1:8765',args.ssh]
        tunnel=subprocess.Popen(command)
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if tunnel.poll() is not None:raise SystemExit('SSH connection failed')
            try:
                with socket.create_connection(('127.0.0.1',tunnel_port),timeout=.2):break
            except OSError:time.sleep(.2)
        else:tunnel.terminate();raise SystemExit('SSH connection timed out')
        args.robot_url=f'http://127.0.0.1:{tunnel_port}'
    gateway=Gateway(args.robot_url,root)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(gateway,args.port))
    print(f'Limo Console: http://127.0.0.1:{args.port}/\nPrivate recordings: {root}',flush=True)
    def terminate(*_):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,terminate)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        gateway.coordinator.close();server.server_close()
        if tunnel:tunnel.terminate();tunnel.wait(timeout=10)

if __name__=='__main__':main()
