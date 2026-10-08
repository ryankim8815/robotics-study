"""속도를 launch 인자로 받아서 실행합니다."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        # launch 인자 선언: ros2 launch ... linear_speed:=3.0 처럼 바꿀 수 있음
        DeclareLaunchArgument('linear_speed', default_value='2.0', description='전진 속도'),
        DeclareLaunchArgument('angular_speed', default_value='0.5', description='회전 속도'),

        Node(
            package='turtlesim',
            executable='turtlesim_node',
            output='screen',
            on_exit=Shutdown(),
        ),
        Node(
            package='turtle_robot',
            executable='lesson_13',
            output='screen',
            parameters=[{
                # value_type=float: linear_speed:=3 처럼 정수로 넣어도 3.0(소수)으로 변환
                'linear_speed': ParameterValue(LaunchConfiguration('linear_speed'), value_type=float),
                'angular_speed': ParameterValue(LaunchConfiguration('angular_speed'), value_type=float),
            }],
        ),
    ])
