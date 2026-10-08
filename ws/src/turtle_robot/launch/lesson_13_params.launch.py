"""파라미터 파일(YAML)을 지정해서 실행합니다."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, Shutdown
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # 기본값: 설치된 패키지의 config/lesson_13_fast.yaml
    default_params = PathJoinSubstitution(
        [FindPackageShare('turtle_robot'), 'config', 'lesson_13_fast.yaml'])

    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=default_params,
                              description='lesson_13 파라미터 파일 경로'),

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
            parameters=[LaunchConfiguration('params_file')],
        ),
    ])
