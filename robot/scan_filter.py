#!/usr/bin/env python3
"""Mapping scan channel; /scan is never modified or suppressed."""
import json
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from scan_quality import mapping_ranges,scan_metrics

class MappingScan(Node):
    def __init__(self):
        super().__init__('limo_mapping_scan')
        self.pub=self.create_publisher(LaserScan,'/scan_mapping',qos_profile_sensor_data)
        self.health=self.create_publisher(String,'/console/scan_quality',10)
        self.create_subscription(LaserScan,'/scan',self.scan,qos_profile_sensor_data)
    def scan(self,msg):
        metrics=scan_metrics(msg,self.get_clock().now().nanoseconds)
        ranges,removed=mapping_ranges(msg.ranges,msg.range_min,msg.range_max)
        msg.ranges=ranges;self.pub.publish(msg)
        event=String();event.data=json.dumps(metrics);self.health.publish(event)

def main():
    rclpy.init();node=MappingScan()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
