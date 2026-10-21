"""Read-only private dataset catalog, local playback and explicit CSV export."""
from collections import Counter
import csv
import io
import json
import math
from pathlib import Path
import threading
import os
import uuid
import zipfile
from .archive import checked,sha256_file,sync_dir

class Datasets:
    def __init__(self,root):
        self.root=Path(root).resolve();self.jobs={};self.bundles={};self.lock=threading.Lock();self.export_slot=threading.Semaphore(1)
    def folder(self,session,instance):
        path=self.root/checked(session)/checked(instance)
        if path.is_symlink() or path.parent.is_symlink() or not path.is_dir() or not path.resolve().is_relative_to(self.root):raise ValueError('Recording not found')
        return path
    def file(self,session,instance,name):
        root=self.folder(session,instance)
        if not isinstance(name,str) or '\\' in name or not name or name.startswith('/') or '..' in Path(name).parts:raise ValueError('Invalid recording file')
        path=root/name
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p!=self.root) or not path.resolve().is_relative_to(root) or not path.is_file():raise ValueError('Recording file not found')
        return path
    def manifest(self,session,instance):
        path=self.file(session,instance,'manifest.json')
        return json.loads(path.read_text())
    def catalog(self):
        sessions={}
        for path in self.root.glob('*/*/manifest.json'):
            session,instance=path.parent.parent.name,path.parent.name
            try:
                value=self.manifest(session,instance)
                item={key:value.get(key) for key in ('name','status','started_at','video_frames','camera_profile','incidents','video_closed')}
                item.update(session_id=session,instance_id=instance)
                start,end=value.get('first_frame_monotonic_ns'),value.get('last_frame_monotonic_ns')
                item['duration_s']=(end-start)/1e9 if start is not None and end is not None else 0
                sessions.setdefault(session,[]).append(item)
            except (OSError,ValueError,KeyError):continue
        return {'sessions':[{'session_id':key,'instances':sorted(value,key=lambda x:x['instance_id'])} for key,value in sorted(sessions.items(),reverse=True)]}
    def describe(self,session,instance):
        root=self.folder(session,instance);manifest=self.manifest(session,instance);files=[];counts=Counter()
        for path in sorted(root.rglob('*')):
            if not path.is_file():continue
            name=str(path.relative_to(root))
            try:self.file(session,instance,name)
            except ValueError:continue
            if path.suffix in ('.csv','.json','.mp4','.mkv','.mcap') or name.endswith(('.mp4.partial','.mkv.partial','.csv.partial')):
                files.append({'name':name,'bytes':path.stat().st_size})
            if path.name.endswith('.manifest.json') and path.parent.name=='sensors':
                counts.update(json.loads(path.read_text()).get('counts',{}))
        trajectory=[];events=[]
        odometry=root/'odometry.csv'
        if odometry.exists():
            with self.file(session,instance,'odometry.csv').open() as file:
                rows=list(csv.DictReader(file))
            if rows:
                t0=int(rows[0]['source_ros_stamp_ns'])
                stride=max(1,math.ceil(len(rows)/3000))
                for row in rows[::stride]:
                    trajectory.append([(int(row['source_ros_stamp_ns'])-t0)/1e9,*[float(row[key]) if row[key] else None for key in ('x_m','y_m','linear_m_s','angular_rad_s','derived_acceleration_m_s2')]])
        if (root/'events.csv').exists():
            with self.file(session,instance,'events.csv').open() as file:events=list(csv.DictReader(file))[-100:]
        frames=self.frame_table(session,instance)
        return {'manifest':manifest,'files':files,'topics':dict(counts),'trajectory':trajectory,'events':events,
                'source_directory':str(root),'bundle':self.bundles.get((session,instance),{'state':'not_bundled'}),
                'frame_count':len(frames),'duration_s':float(frames[-1]['pts_us'])/1e6 if frames else 0,
                'export':self.jobs.get((session,instance),{'state':'done' if odometry.exists() else 'not_exported'})}
    def frame_table(self,session,instance):
        for name in ('frames.csv','frames.csv.partial'):
            try:path=self.file(session,instance,name)
            except ValueError:continue
            with path.open() as file:return [r for r in csv.DictReader(file) if r.get('pts_us') and r.get('frame') is not None]
        return []
    def frame(self,session,instance,index):
        rows=self.frame_table(session,instance)
        if not 0<=index<len(rows):raise ValueError('Frame index is out of range')
        root=self.folder(session,instance)
        if (root/'frames').is_dir():
            return self.file(session,instance,'frames/'+f'{index:08d}.png').read_bytes(),'image/png'
        import av
        candidates=[name for name in ('camera.mkv','camera.mp4','camera.mkv.partial','camera.mp4.partial') if (root/name).is_file()]
        if not candidates:raise ValueError('Video is not available yet')
        target=int(rows[index]['pts_us'])/1e6
        with av.open(str(self.file(session,instance,candidates[0]))) as container:
            stream=container.streams.video[0]
            container.seek(max(0,int(target/float(stream.time_base))),stream=stream,backward=True)
            for frame in container.decode(stream):
                if frame.time is not None and frame.time+1e-5>=target:
                    out=io.BytesIO();frame.to_image().save(out,format='JPEG',quality=88)
                    return out.getvalue(),'image/jpeg'
        raise ValueError('Frame is not available yet')
    def export(self,session,instance):
        root=self.folder(session,instance);manifest=self.manifest(session,instance)
        if not manifest.get('video_closed'):raise ValueError('Finish this instance before exporting CSV')
        key=(session,instance)
        with self.lock:
            if self.jobs.get(key,{}).get('state') in ('queued','running'):return self.jobs[key]
            self.jobs[key]={'state':'queued'}
        def work():
            with self.export_slot:
                self.jobs[key]={'state':'running'}
                try:
                    from harness.replay import inspect
                    report=inspect(root,export=True)
                    self.jobs[key]={'state':'done','report':report}
                except Exception as exc:self.jobs[key]={'state':'error','error':str(exc)}
        threading.Thread(target=work,daemon=True).start()
        return self.jobs[key]

    def bundle(self,session,instance):
        root=self.folder(session,instance);manifest=self.manifest(session,instance)
        if not manifest.get('video_closed'):raise ValueError('Finish this instance before packaging')
        key=(session,instance)
        with self.lock:
            if self.bundles.get(key,{}).get('state') in ('queued','running'):return self.bundles[key]
            self.bundles[key]={'state':'queued'}
        def work():
            with self.export_slot:
                try:
                    folder=self.root/'.downloads';folder.mkdir(exist_ok=True,mode=0o700)
                    files=[(self.file(session,instance,str(p.relative_to(root))),str(p.relative_to(root))) for p in root.rglob('*') if p.is_file()]
                    configuration=root.parent/'configuration.json'
                    if configuration.is_file() and not configuration.is_symlink():files.append((configuration,'_session/configuration.json'))
                    target=folder/(session+'_'+instance+'.zip');temporary=folder/(uuid.uuid4().hex+'.partial')
                    job={'state':'running','files_done':0,'files_total':len(files)};self.bundles[key]=job
                    with zipfile.ZipFile(temporary,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
                        for path,name in files:archive.write(path,name);job['files_done']+=1
                    with temporary.open('rb') as file:os.fsync(file.fileno())
                    os.replace(temporary,target);sync_dir(folder)
                    self.bundles[key]={'state':'done','filename':target.name,'bytes':target.stat().st_size,'sha256':sha256_file(target)}
                except Exception as exc:self.bundles[key]={'state':'error','error':str(exc)}
        threading.Thread(target=work,daemon=True).start()
        return self.bundles[key]

    def bundle_file(self,session,instance):
        self.folder(session,instance)
        info=self.bundles.get((session,instance),{})
        if info.get('state')!='done':raise ValueError('Package is not ready')
        path=self.root/'.downloads'/info['filename']
        if path.is_symlink() or not path.is_file():raise ValueError('Package is not available')
        return path
