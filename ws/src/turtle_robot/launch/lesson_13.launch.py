"""turtlesim과 lesson_13 노드를 한 번에 실행합니다."""

from launch import LaunchDescription
from launch.actions import Shutdown
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        # 터미널 1에서 하던 일: ros2 run turtlesim turtlesim_node
        Node(
            package='turtlesim',
            executable='turtlesim_node',
            output='screen',
            on_exit=Shutdown(),  # 거북이 창을 닫으면 launch 전체를 종료
        ),
        # 터미널 2에서 하던 일: ros2 run turtle_robot lesson_13 --ros-args -p ...
        Node(
            package='turtle_robot',
            executable='lesson_13',
            output='screen',
            parameters=[{'linear_speed': 2.0, 'angular_speed': 0.5}],
        ),
    ])
