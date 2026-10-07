#!/bin/sh
set -e

# -listen tcp -ac : 같은 compose 네트워크의 ROS 컨테이너가 DISPLAY=novnc:0 으로 접속 (포트 6000은 외부 미공개)
# -localhost      : VNC(5900)는 컨테이너 내부 websockify 만 접속 가능
Xvnc :0 \
  -listen tcp -ac \
  -localhost -SecurityTypes None \
  -geometry "${DISPLAY_WIDTH:-1600}x${DISPLAY_HEIGHT:-900}" -depth 24 \
  -AlwaysShared &

until [ -S /tmp/.X11-unix/X0 ]; do sleep 0.2; done

DISPLAY=:0 fluxbox >/dev/null 2>&1 &

exec websockify --web /usr/share/novnc 8080 localhost:5900
