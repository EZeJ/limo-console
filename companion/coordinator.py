"""Own one recording connection; stream video locally and drain robot MCAP chunks."""
import io
import json
from pathlib import Path
import shutil
import threading
import time
from urllib.request import Request,urlopen
import uuid
from PIL import Image
from .video import VideoWriter
from .archive import json_request,atomic_json,archive_chunk,checked

DEFAULT_PROFILE={'width':640,'height':480,'fps':10,'format':'h264'}


class Coordinator:
    def __init__(self,robot_url,data_dir,*,reserve_bytes=5*1024**3):
        self.base=robot_url.rstrip('/')
        self.root=Path(data_dir).expanduser().resolve();self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.reserve=reserve_bytes
        self.lock=threading.RLock()
        self.owner=uuid.uuid4().hex
        self.session=None;self.instances=[];self.writers={};self.profile=dict(DEFAULT_PROFILE)
        self.pending_profile=None
        self.error='';self.last_frame=0.;self.frame_count=0;self.gaps=0
        self.last_seq=-1;self.boot=None;self.latest_frame=None
        self.archived_chunks=0;self.archived_bytes=0;self.last_archived=''
        self.free_bytes=shutil.disk_usage(self.root).free
        self.halt=threading.Event();self.threads=[];self.active=False;self.switching=False
        self.last_archive_poll=0.;self.sensor_status={};self.operation={}
        self.warmup_started=time.monotonic();self.warmup_count=0

    def request(self,path,data=None,timeout=8):return json_request(self.base,path,data,timeout)

    def start(self,profile=None):
        self.request('/stop',{})
        self.profile=dict(profile or DEFAULT_PROFILE)
        self.request('/capture/configure',self.profile,timeout=15)
        if shutil.disk_usage(self.root).free<self.reserve:raise ValueError('Computer recording storage is full')
        boundary=self.request('/recording/start',{'request_id':uuid.uuid4().hex,'owner':self.owner,
                              'metadata':{'camera_profile':self.profile,'clock':'robot_monotonic_ns','version':1}},timeout=25)
        self.session=boundary['session_id'];self.active=True
        self._add_instance(boundary)
        self.warmup_started=time.monotonic()
        for name,fn in [('video-receiver',self.frame_loop),('recording-heartbeat',self.heartbeat_loop),('sensor-archive',self.archive_loop)]:
            thread=threading.Thread(target=fn,name=name,daemon=True);thread.start();self.threads.append(thread)
        return self.status()

    def _add_instance(self,boundary):
        folder=self.root/checked(boundary['session_id'])/checked(boundary['instance_id'])
        folder.mkdir(parents=True,exist_ok=True)
        item=dict(boundary,camera_profile=dict(self.profile),status='recording',path=str(folder))
        self.instances.append(item)
        self.writers[item['instance_id']]=VideoWriter(folder,self.profile)
        self._persist(item)

    def _persist(self,item):
        writer=self.writers.get(item['instance_id'])
        value=dict(item)
        if writer:value.update(video_frames=writer.count,first_frame_monotonic_ns=writer.first_ns,last_frame_monotonic_ns=writer.last_ns,video_closed=writer.closed)
        atomic_json(Path(item['path'])/'manifest.json',value)

    def status(self):
        with self.lock:
            current=self.instances[-1] if self.instances else {}
            healthy=self.active and not self.error and not self.switching and time.monotonic()-self.warmup_started>=5 and time.monotonic()-self.last_frame<.6 and self.free_bytes>=self.reserve
            return dict(active=self.active,ready=bool(healthy and self.sensor_status.get('ready')),healthy=bool(healthy),
                        error=self.error or self.sensor_status.get('error',''),session_id=self.session,
                        instance_id=current.get('instance_id'),started_at=current.get('started_at'),
                        instance_count=len(self.instances),frames=self.frame_count,frame_gaps=self.gaps,
                        saved_directory=str(self.root),instance_directory=current.get('path'),
                        profile=dict(self.profile),pending_profile=self.pending_profile,
                        free_bytes=self.free_bytes,archived_chunks=self.archived_chunks,archived_bytes=self.archived_bytes,
                        last_archived=self.last_archived,robot=self.sensor_status,switching=self.switching)

    def fault(self,reason):
        with self.lock:
            if self.error:return
            self.error=str(reason)
        try:self.request('/stop',{},timeout=2)
        except Exception:pass

    def next(self,request_id,name=''):
        with self.lock:
            if not self.active or self.error:raise ValueError('Recording is not ready')
            if self.operation.get('request_id')==request_id:return self.operation['result']
            if self.pending_profile:
                robot=self.request('/status')
                if robot['mode']!='stopped':raise ValueError('Stop driving before applying a camera profile')
                self.switching=True
            boundary=self.request('/recording/next',{'request_id':request_id,'owner':self.owner,'name':name},timeout=25)
            old=self.instances[-1];old['end_monotonic_ns']=boundary['monotonic_ns'];old['status']='closing';self._persist(old)
            if self.pending_profile:
                self.request('/capture/configure',self.pending_profile,timeout=15)
                self.profile=self.pending_profile;self.pending_profile=None;self.last_seq=-1
            self._add_instance(boundary)
            if self.switching:self.warmup_started=time.monotonic();self.warmup_count=self.frame_count
            self.switching=False
            result=dict(boundary,recording=self.status())
            self.operation={'request_id':request_id,'result':result}
            return result

    def stage_profile(self,profile):
        capabilities=self.request('/capture/status')
        candidate={key:profile[key] for key in DEFAULT_PROFILE}
        if candidate['format'] not in capabilities['formats'] or candidate['fps'] not in (5,10,15,30):raise ValueError('Unsupported camera recording profile')
        if [candidate['width'],candidate['height']] not in capabilities['resolutions']:raise ValueError('Camera resolution is not supported')
        with self.lock:self.pending_profile=candidate
        return self.status()

    def frame_loop(self):
        startup=time.monotonic()+10
        while not self.halt.is_set():
            try:
                with urlopen(Request(self.base+'/capture/frame?after='+str(self.last_seq),headers={'Host':'127.0.0.1:8765'}),timeout=4) as response:
                    meta=json.loads(response.headers['X-Limo-Frame']);data=response.read()
                    kind=response.headers['Content-Type']
                meta['receive_wall_ns']=time.time_ns()
                with self.lock:
                    if self.boot and meta['boot_id']!=self.boot:raise ValueError('Camera transport restarted; start a new recording session')
                    self.boot=meta['boot_id']
                    if self.last_seq>=0 and meta['sequence']!=self.last_seq+1:
                        self.gaps+=max(0,meta['sequence']-self.last_seq-1)
                        raise ValueError('Camera frames were lost; driving is locked')
                    self.last_seq=meta['sequence']
                    self.latest_frame=(data,kind,meta)
                    if self.error:continue
                    target=next((item for item in reversed(self.instances) if item['monotonic_ns']<=meta['monotonic_ns']),None)
                    if not target:continue
                    writer=self.writers[target['instance_id']]
                    writer.write(meta,data)
                    self.frame_count+=1;self.last_frame=time.monotonic()
                    for item in self.instances:
                        if item.get('end_monotonic_ns',10**30)<=meta['monotonic_ns']:
                            previous=self.writers[item['instance_id']]
                            if not previous.closed:previous.close();item['status']='video_saved';self._persist(item)
                    if writer.count % self.profile['fps']==0:self._persist(target)
            except Exception as exc:
                if self.halt.is_set():break
                if time.monotonic()>startup and not self.switching:self.fault('Video recording failed: '+str(exc))
                self.halt.wait(.2)

    def heartbeat_loop(self):
        while not self.halt.is_set():
            try:
                self.free_bytes=shutil.disk_usage(self.root).free
                if self.free_bytes<self.reserve:self.fault('Computer recording storage is full')
                if 5 < time.monotonic()-self.warmup_started < 6 and self.frame_count-self.warmup_count < self.profile['fps']*4.5:
                    self.fault('Selected camera frame rate cannot be sustained')
                local=self.status()
                self.sensor_status=self.request('/recording/heartbeat',{'owner':self.owner,'healthy':local['healthy']},timeout=2)
                if self.sensor_status.get('error'):self.fault(self.sensor_status['error'])
            except Exception as exc:
                if self.active:self.fault('Recording connection lost: '+str(exc))
            self.halt.wait(.2)

    def archive_loop(self):
        while not self.halt.is_set():
            try:
                chunks=self.request('/recording/chunks')['chunks']
                for chunk in chunks:
                    path=archive_chunk(self.base,self.root,chunk)
                    self.archived_chunks+=1;self.archived_bytes+=chunk['bytes'];self.last_archived=path
                self.last_archive_poll=time.monotonic()
                remote=self.request('/recording/instances')['instances']
                with self.lock:
                    by_id={item['instance_id']:item for item in remote}
                    for item in self.instances:
                        remote_item=by_id.get(item['instance_id'])
                        if remote_item:
                            item['sensor_status']=remote_item['status']
                            if remote_item['status']!='recording' and self.writers[item['instance_id']].closed:
                                item['status']='complete' if remote_item['status']=='complete' and not self.error else 'interrupted'
                            self._persist(item)
            except Exception as exc:
                if not self.halt.is_set():self.fault('Data archival failed: '+str(exc))
            self.halt.wait(1.)

    def close(self):
        self.active=False
        try:self.request('/stop',{})
        except Exception:pass
        try:self.request('/recording/finish',{'owner':self.owner},timeout=25)
        except Exception:pass
        self.halt.set()
        for thread in self.threads:
            if thread is not threading.current_thread():thread.join(timeout=5)
        with self.lock:
            for item in self.instances:
                writer=self.writers[item['instance_id']]
                try:writer.close(interrupted=bool(self.error))
                except Exception as exc:self.error=str(exc)
                item['status']='interrupted' if self.error else 'video_saved';self._persist(item)
        # The final closed chunks are also verified before deletion.
        try:
            for chunk in self.request('/recording/chunks')['chunks']:archive_chunk(self.base,self.root,chunk)
            with self.lock:
                for item in self.instances:
                    item['status']='interrupted' if self.error else 'complete';self._persist(item)
        except Exception as exc:
            self.error='Final data remains on the robot: '+str(exc)
            with self.lock:
                for item in self.instances:
                    item['status']='pending_transfer';self._persist(item)
