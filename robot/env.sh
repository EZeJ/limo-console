#!/bin/bash
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-42}
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///control/cyclonedds.xml
source /opt/ros/humble/setup.bash
source "${LIMO_ROS_SETUP:-/root/workspace/install/setup.bash}"
export DISPLAY=:1
export LIBGL_ALWAYS_SOFTWARE=1
export QT_X11_NO_MITSHM=1
