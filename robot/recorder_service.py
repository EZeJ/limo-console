#!/usr/bin/env python3
"""Independent ROS recorder; images are explicitly excluded from robot storage."""
import json
import os
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from rosidl_runtime_py.utilities import get_message
from std_msgs.msg import String
from recording_core import Recorder
from ros_schema import message_definition


class RecorderNode(Node):
    def __init__(self):
        super().__init__('limo_console_recorder')
        self.recorder=Recorder(os.environ.get('LIMO_RECORDING_SPOOL','/control/recordings'))
        self.subscriptions_by_topic={}
        self.definitions={}
        self.unavailable={}
        self.skipped={}
        self.health=self.create_publisher(String,'/console/recording_health',10)
        self.create_timer(.1,self.publish_health)
        self.create_timer(2.,self.discover)
        self.create_timer(1.,self.check_capacity)
        self.discover()

    def check_capacity(self):
        try:self.recorder.capacity()
        except Exception as exc:self.recorder.fault('Storage check failed: '+str(exc))

    def discover(self):
        for topic,types in self.get_topic_names_and_types():
            if topic in self.subscriptions_by_topic or topic=='/console/recording_health':continue
            if len(types)!=1:
                self.unavailable[topic]='Multiple message types';continue
            typename=types[0]
            if typename in ('sensor_msgs/msg/Image','sensor_msgs/msg/CompressedImage'):
                self.skipped[topic]='Images stream directly to the computer';continue
            try:
                msgtype=get_message(typename)
                definition=self.definitions.setdefault(typename,message_definition(typename,get_message))
                endpoints=self.get_publishers_info_by_topic(topic)
                reliable=all(p.qos_profile.reliability==ReliabilityPolicy.RELIABLE for p in endpoints)
                latched=topic=='/tf_static' or topic.endswith('/camera_info')
                durability=DurabilityPolicy.TRANSIENT_LOCAL if endpoints and all(p.qos_profile.durability==DurabilityPolicy.TRANSIENT_LOCAL for p in endpoints) else DurabilityPolicy.VOLATILE
                qos=QoSProfile(depth=100,reliability=ReliabilityPolicy.RELIABLE if reliable else ReliabilityPolicy.BEST_EFFORT,durability=durability)
                def callback(data,t=topic,ty=typename,d=definition,l=latched):
                    self.recorder.append(t,ty,d,data,latched=l)
                self.subscriptions_by_topic[topic]=self.create_subscription(msgtype,topic,callback,qos,raw=True)
                self.unavailable.pop(topic,None)
            except Exception as exc:self.unavailable[topic]=str(exc)

    def snapshot(self):
        status=self.recorder.snapshot()
        status.update(topics=list(self.subscriptions_by_topic),unavailable=dict(self.unavailable),skipped=dict(self.skipped))
        if self.unavailable:status['ready']=False;status['error']='Some ROS topics could not be recorded'
        return status

    def publish_health(self):
        message=String();message.data=json.dumps(self.snapshot());self.health.publish(message)


def make_handler(node):
    class Handler(BaseHTTPRequestHandler):
        def reply(self,value,code=200):
            data=json.dumps(value).encode();self.send_response(code)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass

        def do_GET(self):
            parsed=urlsplit(self.path);r=node.recorder
            try:
                if parsed.path=='/status':return self.reply(node.snapshot())
                if parsed.path=='/chunks':return self.reply({'chunks':r.list_chunks()})
                if parsed.path=='/instances':
                    values=[]
                    for p in r.root.glob('*/*/instance.json'):
                        values.append(json.loads(p.read_text()))
                    return self.reply({'instances':values})
                if parsed.path=='/chunk':
                    p=r.chunk_path(parse_qs(parsed.query).get('id',[''])[0])
                    self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(p.stat().st_size));self.end_headers()
                    with p.open('rb') as stream:
                        for data in iter(lambda:stream.read(256*1024),b''):self.wfile.write(data)
                    return
                self.reply({'error':'Unknown recording endpoint'},404)
            except (ValueError,OSError) as exc:self.reply({'error':str(exc)},400)

        def do_POST(self):
            if self.headers.get('X-Limo-Control')!='1':return self.reply({'error':'Control header required'},403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<=length<=16384:raise ValueError('Request too large')
                data=json.loads(self.rfile.read(length) or b'{}');r=node.recorder
                if self.path=='/start':result=r.start(data['request_id'],data['owner'],data.get('metadata'))
                elif self.path=='/next':result=r.split(data['request_id'],data['owner'],data.get('name',''))
                elif self.path=='/finish':result=r.finish(data['owner'],data.get('interrupted',False))
                elif self.path=='/heartbeat':r.heartbeat(data['owner'],data.get('healthy',False));result=node.snapshot()
                elif self.path=='/ack':result=r.acknowledge(data['chunk_id'],data['sha256'],data['bytes'])
                else:return self.reply({'error':'Unknown recording endpoint'},404)
                self.reply(result)
            except (ValueError,KeyError,TypeError,OSError,TimeoutError) as exc:self.reply({'error':str(exc)},400)

        def log_message(self,*args):pass
    return Handler


def main():
    rclpy.init();node=RecorderNode()
    server=ThreadingHTTPServer(('127.0.0.1',8766),make_handler(node))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        if node.recorder.active:
            try:node.recorder.finish(node.recorder.owner,interrupted=True)
            except Exception:pass
        server.shutdown();node.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=='__main__':main()
