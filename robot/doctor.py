#!/usr/bin/env python3
"""Read-only ROS integration checks. Never publishes velocity or changes devices."""
import argparse
import json
from pathlib import Path
import time
from urllib.request import urlopen
import rclpy
from rclpy.node import Node
from integration.verify_driver import check

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',default='/root/workspace/src/limo_ros2');args=parser.parse_args()
    rclpy.init();node=Node('limo_console_doctor');deadline=time.monotonic()+2
    while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.1)
    try:
        topics=dict(node.get_topic_names_and_types())
        required=['/scan','/odom','/imu','/limo_status','/camera/image_raw','/console/recording_health','/scan_mapping']
        publishers=[p.node_name for p in node.get_publishers_info_by_topic('/limo/cmd_vel')]
        guarded=[p.node_name for p in node.get_subscriptions_info_by_topic('/limo/cmd_vel')]
        raw=[p.node_name for p in node.get_subscriptions_info_by_topic('/cmd_vel')]
        result={'required_topics':{t:bool(node.get_publishers_info_by_topic(t)) for t in required},
                'guard_is_only_chassis_publisher':publishers==['limo_console_guard'],
                'base_subscribes_guarded_topic':'limo_base' in guarded,
                'base_cannot_bypass_guard':'limo_base' not in raw,
                'stationary_mode':Path('/control/stationary-mode').exists()}
        try:result['driver_source']=check(args.source)
        except OSError as exc:result['driver_source']={'error':str(exc)}
        with urlopen('http://127.0.0.1:8765/status',timeout=3) as response:
            state=json.load(response)
        result['state']={k:state.get(k) for k in ('mode','output','chassis','scan_quality','mapping')}
        result['ready_for_stationary_checks']=all(result['required_topics'].values()) and result['guard_is_only_chassis_publisher'] and result['base_subscribes_guarded_topic'] and result['base_cannot_bypass_guard']
        print(json.dumps(result,indent=2))
        raise SystemExit(0 if result['ready_for_stationary_checks'] else 1)
    finally:node.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
