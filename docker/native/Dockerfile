# osrf/ros:jazzy-<variant> 와 동일한 레시피 (osrf/docker_images 의 Dockerfile 참고)
# 베이스 ros:jazzy-ros-base-noble 은 공식 multi-arch 이미지이고,
# packages.ros.org 에 arm64 바이너리가 있으므로 M1 에서 네이티브로 빌드된다.
FROM ros:jazzy-ros-base-noble

ARG ROS_VARIANT=desktop-full

RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-${ROS_DISTRO}-${ROS_VARIANT} \
    && rm -rf /var/lib/apt/lists/*
