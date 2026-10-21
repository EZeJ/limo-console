from launch import LaunchDescription
from launch_ros.actions import Node
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lidar_control import LidarControl


def generate_launch_description():
    return LaunchDescription([
        Node(package='limo_base', executable='limo_base', name='limo_base',
             parameters=[dict(port_name='ttyTHS1', odom_frame='odom', base_frame='base_link',
                              pub_odom_tf=True, use_mcnamu=False, control_rate=50)],
             remappings=[('cmd_vel', '/limo/cmd_vel')], output='screen'),
        Node(package='ydlidar_ros2_driver', executable='ydlidar_ros2_driver_node',
             name='ydlidar_ros2_driver_node', parameters=['/control/lidar.yaml',
                 {'start_paused': LidarControl.read_paused('/control/lidar-state.json')}], output='screen'),
        Node(package='tf2_ros', executable='static_transform_publisher', name='laser_tf',
             arguments=['--x', '0.103', '--z', '-0.034', '--frame-id', 'base_link', '--child-frame-id', 'laser_frame']),
        Node(package='tf2_ros', executable='static_transform_publisher', name='imu_tf',
             arguments=['--z', '-0.1', '--frame-id', 'base_link', '--child-frame-id', 'imu_link']),
        Node(package='tf2_ros', executable='static_transform_publisher', name='camera_tf',
             arguments=['--x', '0.084', '--z', '0.3', '--roll', '-1.570796', '--yaw', '-1.570796',
                        '--frame-id', 'base_link', '--child-frame-id', 'camera_optical_frame']),
        Node(package='v4l2_camera', executable='v4l2_camera_node', namespace='camera',
             parameters=[dict(video_device='/dev/video0', image_size=[640, 480],
                              camera_frame_id='camera_optical_frame',
                              exposure_auto=3, exposure_auto_priority=True,
                              gain=20, gamma=125, brightness=4,
                              power_line_frequency=2)], output='screen'),
    ])
