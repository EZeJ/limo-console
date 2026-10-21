#!/usr/bin/env python3
"""Save resumable SLAM state, or seed AMCL with an operator-provided pose."""
import argparse
import math
from pathlib import Path
import time
import rclpy
from rclpy.node import Node
from rosidl_runtime_py.utilities import get_service
from geometry_msgs.msg import PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState


def call(node,type_name,endpoint,fields,timeout=25):
    service=get_service(type_name);client=node.create_client(service,endpoint)
    if not client.wait_for_service(timeout_sec=timeout):raise RuntimeError('Service unavailable: '+endpoint)
    request=service.Request()
    for key,value in fields.items():setattr(request,key,value)
    future=client.call_async(request);rclpy.spin_until_future_complete(node,future,timeout_sec=timeout)
    if not future.done():raise RuntimeError('Service timed out: '+endpoint)
    return future.result()


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    save=sub.add_parser('save');save.add_argument('engine',choices=['cartographer','slam_toolbox']);save.add_argument('path',type=Path)
    locate=sub.add_parser('localize');locate.add_argument('pose',nargs=3,type=float)
    args=parser.parse_args();rclpy.init();node=Node('limo_map_checkpoint')
    try:
        if args.command=='save':
            base=str(args.path.resolve())
            if args.engine=='cartographer':
                path=Path(base+'.pbstream')
                result=call(node,'cartographer_ros_msgs/srv/WriteState','/write_state',{'filename':str(path),'include_unfinished_submaps':True})
                if result.status.code:raise RuntimeError(result.status.message)
                paths=[path]
            else:
                result=call(node,'slam_toolbox/srv/SerializePoseGraph','/slam_toolbox/serialize_map',{'filename':base})
                if result.result:raise RuntimeError('SLAM graph serialization failed')
                paths=[Path(base+'.posegraph'),Path(base+'.data')]
            if not all(p.is_file() and p.stat().st_size for p in paths):raise RuntimeError('SLAM checkpoint files are missing')
        else:
            x,y,heading=args.pose
            if not all(math.isfinite(v) for v in args.pose):raise ValueError('Pose must be finite')
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                result=call(node,'lifecycle_msgs/srv/GetState','/amcl/get_state',{},timeout=5)
                if result.current_state.id==3:break
                time.sleep(.1)
            else:raise RuntimeError('AMCL is not active')
            pub=node.create_publisher(PoseWithCovarianceStamped,'/initialpose',10)
            while pub.get_subscription_count()==0 and time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.1)
            message=PoseWithCovarianceStamped();message.header.frame_id='map'
            message.pose.pose.position.x=x;message.pose.pose.position.y=y
            message.pose.pose.orientation.z=math.sin(heading/2);message.pose.pose.orientation.w=math.cos(heading/2)
            message.pose.covariance[0]=message.pose.covariance[7]=.25;message.pose.covariance[35]=math.radians(15)**2
            for _ in range(3):message.header.stamp=node.get_clock().now().to_msg();pub.publish(message);rclpy.spin_once(node,timeout_sec=.1)
    finally:
        node.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
