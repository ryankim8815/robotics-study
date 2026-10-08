# 01. turtlesim으로 배우는 ROS 2 기본 개념

turtlesim은 ROS 2 공식 입문 튜토리얼에서 노드, 토픽, 서비스, 파라미터, 액션을 차례로 배울 때 쓰는 예제입니다.

- 환경: `osrf/ros:jazzy-desktop-full` (이 레포의 `desktop-full` 서비스)
- 검증: 2026-10-08, 이 환경에서 아래 명령을 모두 실행해 확인했습니다.
- 참고: [ROS 2 Jazzy 공식 튜토리얼 – Beginner: CLI tools](https://docs.ros.org/en/jazzy/Tutorials/Beginner-CLI-Tools.html)

## 0. 준비 (Mac 터미널)

환경을 띄웁니다.

```bash
cd ~/robotics/robotics-study && docker compose up -d
```

브라우저에서 GUI 화면을 엽니다.

```bash
open http://localhost:8080
```

컨테이너 셸에 들어갑니다. 실습하다 보면 터미널이 3~4개 필요하니, Mac 터미널 탭을 여러 개 열고 탭마다 이 명령을 실행하세요.

```bash
cd ~/robotics/robotics-study && docker compose exec desktop-full bash
```

아래부터는 모두 **컨테이너 안**에서 입력하는 명령입니다.

> 💡 M1에서는 Rosetta 에뮬레이션 때문에 `ros2` 명령이 시작되고 다른 노드를 찾기까지 2~3초 걸립니다. 출력이 바로 안 나와도 잠시 기다리세요.

## 1. 실행하고 조종하기

```
# 터미널 1: 거북이 창 띄우기 (브라우저에 나타남)
ros2 run turtlesim turtlesim_node

# 터미널 2: 키보드로 조종
ros2 run turtlesim turtle_teleop_key
```

- **방향키:** 이동합니다. ↑/↓는 앞뒤로, ←/→는 제자리 회전입니다.
- **g b v c d e r t:** 지정한 절대 각도로 회전합니다(예: `r`은 위쪽 90도, `d`는 왼쪽 180도). 6장의 액션을 쓰는 기능입니다.
- **f:** 회전을 취소합니다.
- **q:** 조종을 끝냅니다.
- 키는 모두 **소문자**로 누르세요. Shift를 누른 대문자는 인식하지 않습니다.
- 키 입력은 브라우저가 아니라 **터미널 2 창**을 클릭해 둔 상태에서 해야 합니다.

turtlesim 패키지에 들어 있는 실행 파일 목록도 볼 수 있습니다(`draw_square`, `mimic`, `turtle_teleop_key`, `turtlesim_node`).

```
ros2 pkg executables turtlesim
```

## 2. 노드 (Node): 실행 중인 프로그램 단위

```
ros2 node list
ros2 node info /turtlesim
```

`ros2 node info`는 이 노드가 주고받는 토픽, 서비스, 액션을 모두 보여줍니다.

## 3. 토픽 (Topic): 계속 흘러가는 데이터

```
# 토픽 목록과 메시지 타입
ros2 topic list -t

# 거북이 위치를 실시간으로 보기 (Ctrl+C로 중지)
ros2 topic echo /turtle1/pose

# 한 번만 보기
ros2 topic echo /turtle1/pose --once

# 초당 발행 횟수 (확인 결과 약 62Hz)
ros2 topic hz /turtle1/pose

# 이 토픽에 연결된 발행자/구독자 수
ros2 topic info /turtle1/cmd_vel

# 메시지 구조 보기
ros2 interface show geometry_msgs/msg/Twist

# 속도 명령을 한 번 보내기
ros2 topic pub --once /turtle1/cmd_vel geometry_msgs/msg/Twist "{linear: {x: 2.0}, angular: {z: 1.8}}"

# 1초마다 계속 보내서 원 그리기 (Ctrl+C로 중지)
ros2 topic pub --rate 1 /turtle1/cmd_vel geometry_msgs/msg/Twist "{linear: {x: 2.0}, angular: {z: 1.8}}"
```

`topic echo` 출력에 `A message was lost!!!` 경고가 가끔 섞여 나옵니다. 1초에 62번 오는 메시지를 출력이 다 따라가지 못해서 생기는 경고라 무시해도 됩니다. 보기 싫다면 `--no-lost-messages` 옵션을 붙이세요.

```
ros2 topic echo /turtle1/pose --no-lost-messages
```

## 4. 서비스 (Service): 요청하면 한 번 응답받기

```
# 서비스 목록과 타입
ros2 service list -t

# 요청/응답 구조 보기
ros2 interface show turtlesim/srv/Spawn

# 그린 선 지우기
ros2 service call /clear std_srvs/srv/Empty

# 거북이 하나 더 만들기
ros2 service call /spawn turtlesim/srv/Spawn "{x: 2.0, y: 2.0, theta: 0.2, name: 'turtle2'}"

# 펜을 빨간색, 굵기 5로 바꾸기
ros2 service call /turtle1/set_pen turtlesim/srv/SetPen "{r: 255, g: 0, b: 0, width: 5, 'off': 0}"

# 순간이동
ros2 service call /turtle1/teleport_absolute turtlesim/srv/TeleportAbsolute "{x: 5.5, y: 5.5, theta: 0.0}"

# turtle2 없애기
ros2 service call /kill turtlesim/srv/Kill "{name: 'turtle2'}"

# 처음 상태로 되돌리기
ros2 service call /reset std_srvs/srv/Empty
```

⚠️ `set_pen`의 `off` 항목은 반드시 `'off'`처럼 따옴표로 감싸야 합니다. 따옴표 없이 쓰면 YAML이 `off`를 거짓(false) 값으로 읽어서 `attribute name must be string, not 'bool'` 오류가 납니다.

## 5. 파라미터 (Parameter): 노드의 설정값

```
# 설정값 목록 (background_r/g/b, holonomic 등)
ros2 param list

# 값 읽기
ros2 param get /turtlesim background_g

# 값 바꾸기 (배경색이 바뀜)
ros2 param set /turtlesim background_r 150

# 현재 설정을 파일로 저장 (Mac의 data/ 폴더에 저장됨)
ros2 param dump /turtlesim > ~/data/turtlesim.yaml

# 저장한 설정으로 노드 시작 (먼저 터미널 1의 turtlesim을 Ctrl+C로 끄고, 터미널 1에서 실행)
ros2 run turtlesim turtlesim_node --ros-args --params-file ~/data/turtlesim.yaml
```

기존 turtlesim을 끄지 않고 실행하면 `/turtlesim`이라는 같은 이름의 노드가 두 개 생깁니다. 이때 `ros2 node list`에 `nodes in the graph that share an exact name` 경고가 나옵니다.

## 6. 액션 (Action): 오래 걸리는 작업 + 중간 진행 상황 + 취소

```
ros2 action list -t
ros2 action info /turtle1/rotate_absolute
ros2 interface show turtlesim/action/RotateAbsolute

# 90도(1.57 라디안)로 회전, 남은 각도를 중간중간 출력
ros2 action send_goal /turtle1/rotate_absolute turtlesim/action/RotateAbsolute "{theta: 1.57}" --feedback
```

`--feedback`을 붙이면 `remaining: 1.57 → … → 0`처럼 남은 각도가 출력되고, 마지막에 `Goal finished with status: SUCCEEDED`가 나옵니다.

**취소해 보기:** 회전하는 도중에 `send_goal` 터미널에서 Ctrl+C를 누르면 `Canceling goal...`이 출력되고 거북이가 그 자리에서 멈춥니다. 이때 `Executor is already spinning` 문구가 함께 나올 수 있지만 무시해도 됩니다. 1장의 조종기에서 `f`를 누르는 것도 같은 취소 기능입니다.

## 7. rqt: GUI 도구

```
# 노드와 토픽 연결 관계를 그림으로 보기
ros2 run rqt_graph rqt_graph

# 로그 메시지 모아 보기
ros2 run rqt_console rqt_console

# 값 그래프 (예: /turtle1/pose/x 를 추가)
ros2 run rqt_plot rqt_plot

# 통합 창 (Plugins → Services → Service Caller 에서 서비스를 클릭으로 호출)
rqt
```

사용 팁:

- **창 크기:** rqt 창은 작게 열립니다. 창 오른쪽 아래 모서리를 끌어서 크게 만든 뒤 사용하세요.
- **끄기:** 창을 닫거나, 실행한 터미널에서 Ctrl+C를 누르면 됩니다.
- **rqt_graph:** 1장의 조종기(`turtle_teleop_key`)를 함께 띄워 두고 왼쪽 위 새로고침(↻) 버튼을 누르세요. `/teleop_turtle → /turtle1/cmd_vel → /turtlesim` 연결이 그려집니다. turtlesim 하나만 떠 있으면 그릴 연결이 없어 빈 화면이 나옵니다.
- **rqt_console:** 거북이를 벽까지 몰고 가면 `Oh no! I hit the wall!` 경고(Warn)가 찍히는 것을 볼 수 있습니다.
- **rqt_plot:** 위쪽 Topic 칸에 `/turtle1/pose/x`를 입력하고 `+` 버튼을 누르면 그래프가 그려집니다. `rqt_plot /turtle1/pose/x`처럼 실행할 때 토픽을 넘기는 방법은 이 환경에서 반영되지 않았으니 Topic 칸을 쓰세요.
- **Service Caller:** Service 목록에 `/spawn` 같은 turtlesim 서비스가 안 보이면 왼쪽 새로고침(↻) 버튼을 누르세요. `/spawn`을 고르고 **Call**을 누르면 왼쪽 아래(0, 0)에 거북이가 생깁니다.

## 8. 실행 옵션: 이름 바꾸기(remap)와 로그 레벨

```
# 노드 이름을 바꿔서 실행 (거북이 창이 하나 더 뜨고, ros2 node list에 /my_turtle로 보임)
ros2 run turtlesim turtlesim_node --ros-args --remap __node:=my_turtle

# 조종기가 turtle2를 움직이도록 토픽 이름 바꾸기 (먼저 4장의 spawn으로 turtle2를 만들어 두세요)
ros2 run turtlesim turtle_teleop_key --ros-args --remap turtle1/cmd_vel:=turtle2/cmd_vel

# 경고(WARN) 이상의 로그만 출력
ros2 run turtlesim turtlesim_node --ros-args --log-level WARN
```

## 9. Launch와 mimic: 여러 노드를 한 번에 실행하고 연결하기

```
# 터미널 1: 거북이 창 2개 실행 (/turtlesim1, /turtlesim2 네임스페이스)
ros2 launch turtlesim multisim.launch.py

# 터미널 2: turtlesim2의 거북이가 turtlesim1의 거북이를 그대로 따라 하게 만들기
ros2 run turtlesim mimic --ros-args --remap input/pose:=/turtlesim1/turtle1/pose --remap output/cmd_vel:=/turtlesim2/turtle1/cmd_vel

# 터미널 3: turtlesim1의 거북이만 움직여도 두 거북이가 함께 움직임
ros2 topic pub --rate 1 /turtlesim1/turtle1/cmd_vel geometry_msgs/msg/Twist "{linear: {x: 2.0}, angular: {z: -1.8}}"
```

끝낼 때는 터미널 1에서 Ctrl+C를 누르세요. launch로 띄운 두 노드가 함께 종료되고, `process has finished cleanly`가 출력됩니다.

## 10. rosbag: 토픽을 녹화하고 다시 재생하기

```
cd ~/data

# 녹화 시작. 반드시 Ctrl+C로 멈추세요. 그래야 metadata.yaml이 생깁니다.
ros2 bag record /turtle1/cmd_vel /turtle1/pose

# 녹화 내용 확인 (실제 폴더 이름은 ls로 확인)
ros2 bag info rosbag2_<날짜_시간>

# 거북이를 처음 위치로 돌린 뒤 같은 움직임 재생
ros2 service call /reset std_srvs/srv/Empty
ros2 bag play rosbag2_<날짜_시간>
```

- 녹화 파일은 Mac의 `data/` 폴더에 mcap 형식으로 저장됩니다. `.gitignore`에서 `rosbag2_*/`를 제외해 두었으므로 커밋되지 않습니다.
- `ros2 bag play` 중에는 키보드로 재생을 조절할 수 있습니다.
  - **스페이스바:** 일시정지/재개
  - **→:** 메시지 하나씩 재생
  - **↑ / ↓:** 재생 속도 10%씩 올리기/내리기

## 마무리 (Mac 터미널)

```bash
cd ~/robotics/robotics-study && docker compose down
```

**추천 학습 순서:** 1 → 2 → 3 → 7(`rqt_graph`로 연결 관계를 눈으로 확인) → 4 → 5 → 6 → 8 → 9 → 10. 공식 Jazzy 입문 튜토리얼의 "Beginner: CLI tools" 순서와 같습니다.
