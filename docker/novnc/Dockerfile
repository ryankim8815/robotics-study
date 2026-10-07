# 브라우저 기반 GUI 서버 (multi-arch → M1 에서 arm64 네이티브로 동작)
#   Xvnc (TigerVNC)  : X 서버(TCP 6000) + VNC 서버(localhost:5900)
#   websockify/noVNC : VNC → 브라우저 (8080)
#   fluxbox          : 창 이동/크기 조절용 경량 윈도우 매니저
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      tigervnc-standalone-server \
      novnc \
      websockify \
      fluxbox \
      xterm \
    && rm -rf /var/lib/apt/lists/* \
    && echo '<meta http-equiv="refresh" content="0; url=vnc.html?autoconnect=1&resize=remote">' \
       > /usr/share/novnc/index.html

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080
CMD ["/entrypoint.sh"]
