# osrf/ros:jazzy-<variant> 와 동일한 레시피 (osrf/docker_images 의 Dockerfile 참고)
# 베이스 ros:jazzy-ros-base-noble 은 공식 multi-arch 이미지이고,
# packages.ros.org 에 arm64 바이너리가 있으므로 M1 에서 네이티브로 빌드된다.
FROM ros:jazzy-ros-base-noble

ARG ROS_VARIANT=desktop-full

RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-${ROS_DISTRO}-${ROS_VARIANT} \
    && rm -rf /var/lib/apt/lists/*

# Gazebo·SLAM 실습용 (notes/ 의 Gazebo·SLAM 노트 참고)
#   turtlebot3-gazebo/teleop : TurtleBot3 시뮬레이션과 키보드 조종
#   slam-toolbox             : 라이다로 지도를 만드는 SLAM
#   nav2-map-server          : 만든 지도를 파일로 저장 (map_saver_cli)
#   nav2-bringup             : 지도·라이다·로봇을 보여 주는 RViz 설정
# 위 단계와 나눠 두어서, 패키지를 추가해도 desktop-full 설치 단계는 캐시를 재사용한다.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-${ROS_DISTRO}-turtlebot3-gazebo \
      ros-${ROS_DISTRO}-turtlebot3-teleop \
      ros-${ROS_DISTRO}-slam-toolbox \
      ros-${ROS_DISTRO}-nav2-map-server \
      ros-${ROS_DISTRO}-nav2-bringup \
    && rm -rf /var/lib/apt/lists/*

# TurtleBot3 launch·teleop 이 요구하는 로봇 모델 (burger | waffle | waffle_pi)
ENV TURTLEBOT3_MODEL=burger
