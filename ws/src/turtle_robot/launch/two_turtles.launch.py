"""거북이 2마리를 서로 다른 속도로 한 번에 움직입니다."""

from launch import LaunchDescription
from launch.actions import ExecuteProcess, Shutdown
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params = PathJoinSubstitution(
        [FindPackageShare('turtle_robot'), 'config', 'two_turtles.yaml'])

    return LaunchDescription([
        Node(
            package='turtlesim',
            executable='turtlesim_node',
            output='screen',
            on_exit=Shutdown(),
        ),
        # turtle2 만들기 (서비스가 준비될 때까지 기다렸다가 호출됨)
        ExecuteProcess(
            cmd=['ros2', 'service', 'call', '/spawn', 'turtlesim/srv/Spawn',
                 "{x: 2.0, y: 2.0, theta: 0.0, name: 'turtle2'}"],
            output='screen',
        ),
        # 느린 노드 → turtle1
        Node(
            package='turtle_robot',
            executable='lesson_13',
            name='slow_turtle',
            output='screen',
            parameters=[params],
        ),
        # 빠른 노드 → 토픽 이름을 바꿔서 turtle2
        Node(
            package='turtle_robot',
            executable='lesson_13',
            name='fast_turtle',
            output='screen',
            parameters=[params],
            remappings=[('/turtle1/cmd_vel', '/turtle2/cmd_vel')],
        ),
    ])
