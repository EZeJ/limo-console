#!/usr/bin/env python3
"""Timestamped image transport. Bounded RAM only; never writes image files."""
from collections import deque
import fcntl
import hashlib
import io
import json
import os
import queue
import struct
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit
from PIL import Image as PILImage
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter,ParameterValue,ParameterType


def resolutions(device='/dev/video0'):
    result=set()
    try:
        fd=os.open(device,os.O_RDONLY|os.O_NONBLOCK)
        try:
            for i in range(16):
                desc=bytearray(64);struct.pack_into('II',desc,0,i,1)
                try:fcntl.ioctl(fd,0xc0405602,desc,True)
                except OSError:break
                pix=struct.unpack_from('I',desc,44)[0]
                for j in range(32):
                    size=bytearray(44);struct.pack_into('II',size,0,j,pix)
                    try:fcntl.ioctl(fd,0xc02c564a,size,True)
                    except OSError:break
                    kind,w,h=struct.unpack_from('III',size,8)
                    if kind==1:result.add((w,h))
        finally:os.close(fd)
    except OSError:pass
    return sorted(result,key=lambda size:size[0]*size[1])


class CameraBridge(Node):
    def __init__(self):
        super().__init__('limo_console_camera_transport')
        self.condition=threading.Condition()
        self.frames=deque(maxlen=120)
        self.frame_bytes=0
        self.ram_limit=32*1024**2
        self.pending=queue.Queue(maxsize=4)
        self.config={'width':640,'height':480,'fps':10,'format':'h264'}
        self.generation=0
        self.sequence=0
        self.boot=uuid.uuid4().hex
        self.drops=0
        self.error=''
        self.source=(0,0)
        self.last_source=0.
        self.next_at=0.
        self.available=resolutions()
        self.set_parameters_client=self.create_client(SetParameters,'/camera/v4l2_camera/set_parameters')
        self.create_subscription(Image,'/camera/image_raw',self.image,qos_profile_sensor_data)
        threading.Thread(target=self.encode,daemon=True,name='camera-encode').start()

    def image(self,msg):
        now=time.monotonic()
        self.last_source=now;self.source=(msg.width,msg.height)
        if now<self.next_at:return
        self.next_at=max(self.next_at+1/self.config['fps'],now)
        if msg.encoding not in ('rgb8','bgr8'):
            self.error='Unsupported camera pixel format';return
        self.sequence+=1
        meta={'sequence':self.sequence,'boot_id':self.boot,'monotonic_ns':time.monotonic_ns(),
              'wall_ns':time.time_ns(),'source_stamp_ns':msg.header.stamp.sec*10**9+msg.header.stamp.nanosec,
              'width':msg.width,'height':msg.height,'frame_id':msg.header.frame_id,'source_encoding':msg.encoding,'generation':self.generation,
              'fps':self.config['fps'],'format':self.config['format']}
        try:self.pending.put_nowait((meta,msg.encoding,msg.step,bytes(msg.data)))
        except queue.Full:self.drops+=1;self.error='Camera encoding queue overflow'

    def encode(self):
        while True:
            meta,encoding,step,data=self.pending.get()
            try:
                frame=PILImage.frombytes('RGB',(meta['width'],meta['height']),data,'raw','RGB' if encoding=='rgb8' else 'BGR',step)
                stream=io.BytesIO()
                if meta['format']=='h264':frame.save(stream,format='JPEG',quality=85);kind='image/jpeg'
                else:
                    meta['rgb_sha256']=hashlib.sha256(frame.tobytes()).hexdigest()
                    frame.save(stream,format='PNG',compress_level=1);kind='image/png'
                with self.condition:
                    if meta['generation']==self.generation:
                        meta['encoded_monotonic_ns']=time.monotonic_ns()
                        encoded=stream.getvalue()
                        while self.frames and (len(self.frames)>=self.frames.maxlen or self.frame_bytes+len(encoded)>self.ram_limit):
                            self.frame_bytes-=len(self.frames.popleft()[1])
                        self.frames.append((meta,encoded,kind));self.frame_bytes+=len(encoded)
                        self.condition.notify_all()
            except Exception as exc:self.error=str(exc)
            finally:self.pending.task_done()

    def status(self):
        return dict(config=dict(self.config),native_resolution=list(self.source),resolutions=[list(v) for v in self.available],
                    formats=['h264','ffv1','png'],boot_id=self.boot,sequence=self.sequence,dropped=self.drops,error=self.error,
                    generation=self.generation,buffer_bytes=self.frame_bytes,buffer_limit_bytes=self.ram_limit,
                    source_age=round(time.monotonic()-self.last_source,3),robot_image_files=False)

    def configure(self,config):
        width,height,fps=config.get('width',640),config.get('height',480),config.get('fps',10)
        fmt=config.get('format','h264')
        if (width,height) not in self.available and (width,height)!=self.source:
            raise ValueError('Camera resolution is not supported')
        if type(fps) is not int or fps not in (5,10,15,30) or fmt not in ('h264','ffv1','png'):
            raise ValueError('Unsupported camera recording profile')
        if (width,height)!=self.source:
            if not self.set_parameters_client.service_is_ready():raise ValueError('Camera configuration service unavailable')
            request=SetParameters.Request()
            request.parameters=[Parameter(name='image_size',value=ParameterValue(type=ParameterType.PARAMETER_INTEGER_ARRAY,integer_array_value=[width,height]))]
            future=self.set_parameters_client.call_async(request);deadline=time.monotonic()+8
            while not future.done() and time.monotonic()<deadline:time.sleep(.02)
            if not future.done():raise ValueError('Camera configuration timed out')
            if not all(result.successful for result in future.result().results):raise ValueError('Camera rejected this resolution')
            while self.source!=(width,height) and time.monotonic()<deadline:time.sleep(.02)
            if self.source!=(width,height):raise ValueError('Camera did not produce the requested native resolution')
        with self.condition:
            self.config=dict(width=width,height=height,fps=fps,format=fmt)
            self.generation+=1;self.frames.clear();self.frame_bytes=0;self.error='';self.drops=0;self.next_at=0
        return self.status()


def handler_for(node):
    class Handler(BaseHTTPRequestHandler):
        def answer(self,payload,code=200):
            data=json.dumps(payload).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass

        def do_GET(self):
            parsed=urlsplit(self.path)
            if parsed.path=='/status':return self.answer(node.status())
            if parsed.path!='/frame':return self.answer({'error':'Unknown camera endpoint'},404)
            try:after=int(parse_qs(parsed.query).get('after',['-1'])[0])
            except ValueError:return self.answer({'error':'Invalid frame sequence'},400)
            deadline=time.monotonic()+2
            with node.condition:
                selected=None
                while time.monotonic()<deadline:
                    if after<0 and node.frames:selected=node.frames[-1]
                    else:selected=next((frame for frame in node.frames if frame[0]['sequence']>after),None)
                    if selected:break
                    node.condition.wait(max(0,deadline-time.monotonic()))
            if not selected:return self.answer({'error':node.error or 'Camera frame unavailable'},503)
            source_meta,data,kind=selected
            meta=dict(source_meta,transport_age_s=(time.monotonic_ns()-source_meta['monotonic_ns'])/1e9)
            if after<0 and meta['transport_age_s']>2:return self.answer({'error':'Camera frame is stale'},503)
            self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
            self.send_header('X-Limo-Frame',json.dumps(meta,separators=(',',':')));self.send_header('Cache-Control','no-store');self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass

        def do_POST(self):
            if self.path!='/configure' or self.headers.get('X-Limo-Control')!='1':return self.answer({'error':'Not allowed'},403)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<2048:raise ValueError('Request too large')
                self.answer(node.configure(json.loads(self.rfile.read(size))))
            except (ValueError,TypeError,KeyError) as exc:self.answer({'error':str(exc)},400)

        def log_message(self,*args):pass
    return Handler


def main():
    rclpy.init();node=CameraBridge();server=ThreadingHTTPServer(('127.0.0.1',8767),handler_for(node))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        server.shutdown();node.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=='__main__':main()
