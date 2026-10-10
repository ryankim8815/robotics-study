# ROS 2 Jazzy 학습 환경 (M1 Mac + Docker)

## 디렉토리 구조

```
robotics-study/
├── compose.yaml            # 서비스 정의 (novnc + ROS 이미지별 프로파일)
├── .env.example            # 환경 설정 예시 (git 커밋 대상) → .env 로 복사해서 사용
├── .env                    # 로컬 환경 설정 (git 제외): 기본 프로파일, ROS_DOMAIN_ID, GUI 해상도
├── config/bashrc           # → /root/.bashrc  (ROS 환경 자동 source)
├── docker/
│   ├── novnc/              # 브라우저 GUI 서버 이미지 (arm64 네이티브)
│   └── native/             # (선택) arm64 네이티브 ROS 이미지
├── notes/                  # 학습 노트 (날짜-주제.md, 예: 2026-1007-turtlesim.md)
├── ws/                     # → /root/ros2_ws  (colcon 워크스페이스, src/에 패키지 작성)
└── data/                   # → /root/data     (rosbag, 맵, URDF 등)
```

## osrf/ros Jazzy 이미지

| 태그 (동일 이미지) | 베이스 | 설치 메타패키지 | 포함 내용 | 압축 크기 | 아키텍처 |
|---|---|---|---|---|---|
| `jazzy-desktop` (`jazzy-desktop-noble`) | `ros:jazzy-ros-base-noble` | `ros-jazzy-desktop` | ros-base + RViz2, rqt, turtlesim, demo/examples 노드, teleop, image_tools | 1.26 GB | amd64 |
| `jazzy-desktop-full` (`jazzy-desktop-full-noble`) | `osrf/ros:jazzy-desktop-noble` | `ros-jazzy-desktop-full` | desktop + perception + simulation + ros_gz_sim_demos | 1.42 GB | amd64 |
| `jazzy-simulation` (`jazzy-simulation-noble`) | `ros:jazzy-ros-base-noble` | `ros-jazzy-simulation` | ros-base + Gazebo Harmonic + ros_gz (bridge/sim/image), GUI 도구 없음 | 0.73 GB | amd64 |

참고로, 상위 공식 이미지인 `ros:jazzy-ros-core`(154 MB), `ros:jazzy-ros-base`(= `ros:jazzy`, 287 MB), `ros:jazzy-perception`(987 MB)은 **arm64를 지원합니다**.

## 사용법

처음 한 번, 예시 설정 파일을 복사해 `.env`를 만듭니다. `.env`는 git에서 제외되므로 내 환경에 맞게 자유롭게 고쳐도 됩니다.

```bash
cd ~/robotics/robotics-study && cp .env.example .env
```

`.env`가 없으면 기본 프로파일(`COMPOSE_PROFILES`)이 지정되지 않아서, `docker compose up -d`를 해도 novnc만 뜹니다.

novnc와 desktop-full 컨테이너를 띄웁니다.

```bash
cd ~/robotics/robotics-study && docker compose up -d
```

브라우저에서 GUI 화면을 엽니다.

```bash
open http://localhost:8080
```

컨테이너 셸에 들어갑니다. 터미널이 더 필요하면 이 명령을 다시 실행하면 됩니다.

```bash
docker compose exec desktop-full bash
```

컨테이너 안에서는 이렇게 실습할 수 있습니다.

```
# 브라우저에 turtlesim 창이 나타납니다
ros2 run turtlesim turtlesim_node

# 다른 터미널에서 키보드로 거북이 조종
ros2 run turtlesim turtle_teleop_key

# 패키지 만들기
cd ~/ros2_ws/src && ros2 pkg create --build-type ament_python my_pkg

# colcon build 후 환경 다시 불러오기 (bashrc 별칭)
cb
```

다른 이미지를 쓰려면 `docker compose --profile simulation up -d`처럼 프로파일을 지정하거나, `.env`의 `COMPOSE_PROFILES`를 바꾸세요.

## M1 호환성 (검증 결과)

2026-10-07, Docker Desktop 29.5 (Apple Silicon)에서 확인했습니다.

| 항목 | osrf/ros (amd64, Rosetta) | native (arm64) |
|---|---|---|
| ros2 CLI, pub/sub, turtlesim, rqt | ✅ | ✅ |
| RViz2 (OpenGL 4.5, llvmpipe) | ✅ | ✅ |
| Gazebo 서버 (`gz sim -s`, headless) | ✅ | ✅ RTF ≈ 1.0 |
| Gazebo GUI (`gz sim`) | ❌ "Create main window"에서 멈춤 | ✅ |
| 컨테이너 간 DDS 통신 (amd64 ↔ arm64) | ✅ | ✅ |

Gazebo GUI가 필요한 단계부터는 `native` 프로파일을 사용하세요. 자세한 내용은 아래에 있습니다.

## native 프로파일

native 환경에서 Gazebo 튜토리얼 예제(`diff_drive`)를 직접 돌려봤습니다. 로봇이 ROS 명령대로 움직였고, RViz에서도 위치 정보(odometry)가 정상으로 표시됐습니다.

### 1. native가 왜 필요한가

`osrf/ros:jazzy-*` 이미지는 Intel(amd64)용으로만 배포됩니다. 그래서 M1에서는 Rosetta가 명령어를 번역하면서 실행합니다.

- ROS 명령어, 토픽 통신, turtlesim, RViz는 이 상태로도 잘 됩니다.
- Gazebo 창(`gz sim`)은 시작 단계(`Create main window`)에서 멈춥니다.
  - 렌더링 관련 설정을 세 가지 바꿔봤지만 모두 같은 곳에서 멈췄습니다. 그래서 에뮬레이션 자체의 한계로 봤습니다.
  - 같은 Gazebo를 M1용(arm64)으로 실행하면 정상 동작합니다.

### 2. native 프로파일은 무엇인가

osrf가 공개한 Dockerfile을 보면, 이미지를 만드는 방법은 사실상 `apt install ros-jazzy-desktop-full` 한 줄입니다. ROS 공식 저장소에는 이 패키지들의 M1용 버전도 있습니다. 그래서 같은 설치를 M1용 베이스 이미지 위에서 직접 하도록 만든 것이 native입니다([docker/native/Dockerfile](docker/native/Dockerfile)).

| 구분 | `osrf/ros:jazzy-desktop-full` | native (`ros2-jazzy-native:desktop-full`) |
|---|---|---|
| 베이스 이미지 | `osrf/ros:jazzy-desktop-noble` (Intel 전용) | `ros:jazzy-ros-base-noble` (공식 이미지, M1 지원) |
| 설치 패키지 | `ros-jazzy-desktop-full` | 동일 + Gazebo·SLAM 실습용 패키지 (TurtleBot3 시뮬레이션·조종, slam_toolbox, nav2_map_server, nav2_bringup) |
| 받는 방법 | `docker pull` (완성된 이미지) | 내 Mac에서 빌드 (약 3~4분) |
| 패키지 버전 | 2026-06 시점으로 고정 (ros_gz_sim 1.0.22) | 빌드한 날의 최신 버전 (ros_gz_sim 1.0.24) |
| 실행 방식 | Rosetta 번역 | M1에서 직접 실행 |
| Gazebo 창 | ❌ | ✅ |

### 3. 사용 순서

이미지를 빌드하고 띄웁니다(처음 한 번만 빌드되고, 다음부터는 바로 뜹니다).

```bash
cd ~/robotics/robotics-study && docker compose --profile native up -d --build
```

컨테이너 셸에 들어갑니다. 터미널이 더 필요하면 이 명령을 다시 실행하면 됩니다.

```bash
docker compose exec native bash
```

컨테이너 안에서 예제를 실행합니다. 결과는 브라우저 `http://localhost:8080`에 나타납니다.

```
# 터미널 1: Gazebo + ROS↔Gazebo 연결(ros_gz 브리지) + RViz를 한 번에 실행
ros2 launch ros_gz_sim_demos diff_drive.launch.py

# 터미널 2: 파란 차량에 이동 명령 보내기
ros2 topic pub -r 10 /model/vehicle_blue/cmd_vel geometry_msgs/msg/Twist "{linear: {x: 1.0}, angular: {z: 0.5}}"
```

같은 패키지에 예제가 20개 더 있습니다. 카메라, 라이다, IMU, GPS(navsat), TF 브리지, 관절 상태(joint_states) 등이고, `ls /opt/ros/jazzy/share/ros_gz_sim_demos/launch/`로 목록을 볼 수 있습니다.

native를 기본으로 쓰려면 `.env`에서 `COMPOSE_PROFILES=native`로 바꾸세요. 그러면 `docker compose up -d`만 입력해도 native가 뜹니다.

### 4. 어떤 컨테이너가 뜨는지 (직접 확인함)

| 명령 | 실행되는 서비스 |
|---|---|
| `docker compose up -d` | novnc + desktop-full (`.env` 설정 기준) |
| `docker compose --profile native up -d` | novnc + native (`.env` 설정은 무시됨) |
| `docker compose --profile desktop-full --profile native up -d` | 셋 다 |

두 ROS 컨테이너를 같이 띄우면 같은 네트워크와 같은 `ROS_DOMAIN_ID`를 쓰기 때문에 서로 토픽을 주고받습니다. Intel용 컨테이너에서 보낸 메시지를 M1용 컨테이너에서 받는 것까지 확인했습니다. 컴퓨터 여러 대로 ROS를 쓰는 상황을 연습할 때 쓸 수 있습니다.

### 5. 워크스페이스 전환 주의

`ws/` 폴더는 모든 컨테이너가 같이 씁니다. 그런데 `colcon build`로 만든 C++ 실행 파일과 라이브러리는 빌드한 칩 종류(Intel 또는 M1)에서만 실행됩니다. colcon은 칩 종류가 바뀐 것을 알아채지 못해서 다시 빌드하지 않고, 그대로 실행하면 `Exec format error` 같은 오류가 납니다. 그래서 컨테이너를 바꿀 때는 빌드 결과를 지우고 다시 빌드해야 합니다. Python만 쓴 패키지는 대개 그냥 동작하지만, 깔끔하게 다시 빌드하는 편을 권합니다.

```bash
cd ~/robotics/robotics-study && rm -rf ws/build ws/install ws/log
```

그다음 컨테이너 안에서 `cb`(빌드 후 환경 다시 불러오기 별칭)를 실행하세요.

native가 desktop-full의 기능을 모두 포함하므로, Gazebo 단계에 들어서면 왔다 갔다 하지 말고 native로 완전히 옮기는 게 편합니다. 사실 처음부터 native만 써도 됩니다.

### 6. 다른 구성으로 빌드하기와 업데이트

- **구성 바꾸기:** `.env`의 `NATIVE_VARIANT`를 `desktop`, `simulation`, `perception` 중 하나로 바꾸고 `--build`를 붙여 실행하세요. 이미지 이름도 `ros2-jazzy-native:<구성>`으로 따로 생겨서 기존 이미지와 함께 둘 수 있습니다.
- **패키지 최신화:** `--build`만으로는 이전 설치 결과를 재사용하기 때문에 새 패키지를 받지 않습니다. 최신 패키지를 받으려면 아래 명령으로 처음부터 다시 빌드하세요.

```bash
cd ~/robotics/robotics-study && docker compose build --pull --no-cache native
```

### 7. 성능

- 기본 예제 월드(`shapes.sdf`)는 실제 시간과 같은 속도로 돌아갔습니다(RTF ≈ 1.0).
- GPU를 쓸 수 없어 화면을 CPU로 그리기 때문에 CPU 코어 약 5.5개를 사용했습니다.
- 센서가 많은 월드는 느려질 수 있습니다. 그럴 때는 필요 없는 RViz를 닫거나, `.env`의 `DISPLAY_WIDTH`/`DISPLAY_HEIGHT`를 낮춰 화면 해상도를 줄이세요.

## 주의사항

- `.env`는 git에서 제외됩니다. 새 설정 항목을 추가했다면 `.env.example`에도 같은 항목을 넣어 커밋하세요. 토큰 같은 비밀값은 `.env`에만 넣고 `.env.example`에는 넣지 마세요.
- `ws/`는 모든 서비스가 같이 쓰므로, **amd64 ↔ native를 전환할 때는** `ws/build ws/install ws/log`를 지우고 다시 빌드하세요.
- GPU 가속은 없습니다. 모든 OpenGL은 Mesa llvmpipe 소프트웨어 렌더링으로 처리됩니다.
- noVNC는 인증이 없어서 `127.0.0.1`에만 바인딩해 두었습니다. 포트를 외부에 열지 마세요.
