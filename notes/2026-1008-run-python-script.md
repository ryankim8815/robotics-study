# 02. Docker에서 Python 노드 스크립트 실행하기

Mac의 `data/` 폴더에 둔 Python 노드 파일을 컨테이너에서 실행하는 방법입니다. `data/turtle_robot/lesson_13_cmd_vel_parameters.py`를 예시로 듭니다.

- 환경: `osrf/ros:jazzy-desktop-full` (이 레포의 `desktop-full` 서비스)
- 검증: 2026-10-08, 실습 환경과 분리된 일회용 컨테이너에서 아래 명령을 실행해 확인했습니다.

## 경로 관계

Mac의 `data/` 폴더는 컨테이너의 `~/data`(`/root/data`)로 연결되어 있습니다. Mac에서 파일을 고치면 컨테이너에 바로 반영되므로, 고친 뒤 다시 실행하기만 하면 됩니다.

| Mac | 컨테이너 |
|---|---|
| `~/robotics/robotics-study/data/turtle_robot/lesson_13_cmd_vel_parameters.py` | `~/data/turtle_robot/lesson_13_cmd_vel_parameters.py` |

## 예시 파일: lesson_13_cmd_vel_parameters.py

- `/turtle1/cmd_vel`에 0.1초마다 속도(Twist)를 발행하는 노드입니다.
- 노드 이름은 `/lesson_13_cmd_vel_parameters`입니다.
- 파라미터 `linear_speed`(전진 속도)와 `angular_speed`(회전 속도)를 받고, 기본값은 둘 다 1.0입니다.

## 1. 터미널 1: turtlesim 실행

```bash
cd ~/robotics/robotics-study && docker compose exec desktop-full bash
```

```
ros2 run turtlesim turtlesim_node
```

## 2. 터미널 2: 실습 파일 실행

같은 방법으로 셸에 들어가서 실행합니다.

```bash
cd ~/robotics/robotics-study && docker compose exec desktop-full bash
```

```
# 기본값으로 실행 (linear_speed=1.0, angular_speed=1.0)
python3 ~/data/turtle_robot/lesson_13_cmd_vel_parameters.py

# 파라미터 시작값을 지정해서 실행
python3 ~/data/turtle_robot/lesson_13_cmd_vel_parameters.py --ros-args -p linear_speed:=2.0 -p angular_speed:=0.5
```

멈출 때는 Ctrl+C를 누르세요. 오류 없이 종료됩니다.

셸에 들어가지 않고 Mac 터미널에서 한 줄로 실행할 수도 있습니다.

```bash
cd ~/robotics/robotics-study && docker compose exec desktop-full bash -ic 'python3 ~/data/turtle_robot/lesson_13_cmd_vel_parameters.py'
```

`bash -ic`의 `i`는 대화형 셸이라는 뜻입니다. 이렇게 해야 `config/bashrc`가 읽혀서 ROS 환경이 자동으로 불러와집니다.

## 3. 터미널 3: 실행 중에 파라미터 바꿔 보기

```
ros2 param list /lesson_13_cmd_vel_parameters
ros2 param get /lesson_13_cmd_vel_parameters linear_speed
ros2 param set /lesson_13_cmd_vel_parameters linear_speed 2.5

# 실제로 발행되는 속도 확인
ros2 topic echo /turtle1/cmd_vel
```

`param set`으로 바꾼 값이 다음 발행부터 바로 적용됩니다. `topic echo` 출력의 `linear.x`가 `2.5`로 바뀝니다.

## 참고

- **실습 3을 구현하기 전에는:** 코드가 매번 같은 속도를 발행하므로 점점 커지는 원이 아니라 **같은 크기의 원**을 계속 그립니다. 실행 중에 `param set`으로 `linear_speed`를 올리면 원이 커지는 것을 확인할 수 있습니다.
- **다른 lesson 파일:** 파일 이름만 바꿔서 같은 방식으로 실행하면 됩니다. 예: `python3 ~/data/turtle_robot/<파일명>.py`
- **노드 이름 확인:** `ros2 param` 명령에 쓸 노드 이름은 `ros2 node list`로 확인할 수 있습니다. 코드의 `super().__init__('노드이름')`에 적힌 이름입니다.

## 문제 해결: `could not connect to display novnc:0`

turtlesim 같은 GUI 프로그램을 실행했을 때 아래 오류가 나는 경우입니다.

```
qt.qpa.xcb: could not connect to display novnc:0
This application failed to start because no Qt platform plugin could be initialized.
```

- **원인:** 컨테이너를 새로 만들지 않고 재시작하면 이전 실행이 남긴 잠금 파일(`/tmp/.X0-lock`)이 그대로 남습니다. 이 파일 때문에 GUI 서버(Xvnc)가 "이미 실행 중"으로 판단해 시작하지 못한 것입니다. `docker compose logs novnc`에 `Server is already active for display 0`이 찍혀 있으면 이 경우입니다.
- **예방:** [docker/novnc/entrypoint.sh](../docker/novnc/entrypoint.sh)가 시작할 때 남은 잠금 파일을 먼저 지우도록 고쳐 두었습니다.
- **그래도 발생하면:** 아래 명령으로 `novnc` 컨테이너를 새로 만든 뒤 브라우저의 `http://localhost:8080`을 새로고침하세요. `desktop-full`은 다시 띄울 필요가 없습니다.

```bash
cd ~/robotics/robotics-study && docker compose up -d --build --force-recreate novnc
```
