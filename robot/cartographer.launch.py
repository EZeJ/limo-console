from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='cartographer_ros', executable='cartographer_node',
             arguments=['-configuration_directory', '/control',
                        '-configuration_basename', 'cartographer.lua'],
             remappings=[('scan', '/scan_mapping'), ('odom', '/odom')], output='screen'),
        Node(package='cartographer_ros', executable='cartographer_occupancy_grid_node',
             arguments=['-resolution', '0.05', '-publish_period_sec', '1.0'], output='screen'),
    ])
