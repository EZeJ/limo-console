"""Computer-only frame storage with source timestamps and lossless verification."""
import csv
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import av
import numpy as np
from PIL import Image


class VideoWriter:
    def __init__(self,folder,profile):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.profile=dict(profile);self.mode=profile['format'];self.count=0
        self.container=None;self.stream=None;self.base_ns=None;self.last_pts=-1
        self.frames=self.folder/'frames'
        if self.mode=='png':self.frames.mkdir(exist_ok=True)
        self.table=(self.folder/'frames.csv.partial').open('w',newline='')
        self.csv=csv.writer(self.table)
        self.csv.writerow(['frame','source_sequence','capture_monotonic_ns','source_ros_stamp_ns','receive_wall_ns','pts_us','width','height','rgb_sha256'])
        self.closed=False
        self.first_ns=self.last_ns=None
        self.pending_path=None

    def write(self,meta,data):
        if self.closed:raise ValueError('Video instance is already closed')
        image=Image.open(io.BytesIO(data)).convert('RGB')
        if image.size!=(self.profile['width'],self.profile['height']):raise ValueError('Camera resolution does not match recording profile')
        rgb=np.asarray(image)
        digest=hashlib.sha256(rgb.tobytes()).hexdigest()
        if self.mode!='h264' and meta.get('rgb_sha256')!=digest:
            raise ValueError('Lossless frame checksum mismatch')
        stamp=meta['monotonic_ns']
        if self.base_ns is None:self.base_ns=stamp;self.first_ns=stamp
        pts=(stamp-self.base_ns)//1000
        if pts<=self.last_pts:raise ValueError('Camera timestamps are not increasing')
        self.last_pts=pts;self.last_ns=stamp
        if self.mode=='png':
            path=self.frames/f'{self.count:08d}.png'
            temporary=path.with_suffix('.partial')
            with temporary.open('wb') as file:
                image.save(file,format='PNG');file.flush();os.fsync(file.fileno())
            os.replace(temporary,path)
        else:
            if self.container is None:
                extension='mp4' if self.mode=='h264' else 'mkv'
                self.pending_path=self.folder/f'camera.{extension}.partial'
                options={'movflags':'frag_keyframe+empty_moov+default_base_moof'} if self.mode=='h264' else {}
                self.container=av.open(str(self.pending_path),mode='w',format='mp4' if self.mode=='h264' else 'matroska',options=options)
                self.stream=self.container.add_stream('libx264' if self.mode=='h264' else 'ffv1',rate=self.profile['fps'])
                self.stream.width,self.stream.height=image.size
                self.stream.pix_fmt='yuv420p' if self.mode=='h264' else 'bgr0'
                self.stream.time_base=Fraction(1,1000000)
                self.stream.codec_context.time_base=Fraction(1,1000000)
                self.stream.codec_context.thread_count=2
                self.stream.options={'preset':'veryfast','tune':'zerolatency','crf':'20','bf':'0','g':str(self.profile['fps'])} if self.mode=='h264' else {'level':'3','slicecrc':'1'}
            frame=av.VideoFrame.from_ndarray(rgb,format='rgb24');frame.pts=pts;frame.time_base=Fraction(1,1000000)
            for packet in self.stream.encode(frame):self.container.mux(packet)
        self.csv.writerow([self.count,meta['sequence'],stamp,meta['source_stamp_ns'],meta['receive_wall_ns'],pts,*image.size,digest])
        self.table.flush()
        self.count+=1
        if self.count % self.profile['fps']==0:
            os.fsync(self.table.fileno())
            if self.pending_path:
                with self.pending_path.open('rb') as file:os.fsync(file.fileno())

    def close(self,interrupted=False):
        if self.closed:return
        if self.container:
            for packet in self.stream.encode():self.container.mux(packet)
            self.container.close()
            with self.pending_path.open('rb') as file:os.fsync(file.fileno())
            os.replace(self.pending_path,self.pending_path.with_suffix(''))
        self.table.flush();os.fsync(self.table.fileno());self.table.close()
        os.replace(self.folder/'frames.csv.partial',self.folder/'frames.csv')
        descriptor=os.open(str(self.folder),os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        self.closed=True
