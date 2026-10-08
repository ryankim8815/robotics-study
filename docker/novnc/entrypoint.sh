#!/bin/sh
set -e

# 컨테이너 재시작(restart/stop→start) 시 /tmp 가 유지되므로, 이전 실행이 남긴
# 잠금 파일/소켓을 지운다. 남아 있으면 Xvnc 가 "Server is already active" 로 종료된다.
rm -f /tmp/.X0-lock /tmp/.X11-unix/X0

# -listen tcp -ac : 같은 compose 네트워크의 ROS 컨테이너가 DISPLAY=novnc:0 으로 접속 (포트 6000은 외부 미공개)
# -localhost      : VNC(5900)는 컨테이너 내부 websockify 만 접속 가능
Xvnc :0 \
  -listen tcp -ac \
  -localhost -SecurityTypes None \
  -geometry "${DISPLAY_WIDTH:-1600}x${DISPLAY_HEIGHT:-900}" -depth 24 \
  -AlwaysShared &
XVNC_PID=$!

# X 소켓이 생길 때까지 대기. Xvnc 가 그 전에 죽으면 컨테이너도 실패로 종료해서 문제를 바로 드러낸다.
until [ -S /tmp/.X11-unix/X0 ]; do
  if ! kill -0 "$XVNC_PID" 2>/dev/null; then
    echo "Xvnc 시작 실패 (위 로그 참고)" >&2
    exit 1
  fi
  sleep 0.2
done

DISPLAY=:0 fluxbox >/dev/null 2>&1 &

exec websockify --web /usr/share/novnc 8080 localhost:5900
