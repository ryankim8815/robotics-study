# 두산 로봇팔 블록 다시 쌓기 (DRL Custom Code)

두산 로봇팔(컨트롤러 S/W **DRSUP V2.10.3**)과 ROBOTIS **RH-P12-RN(A)** 그리퍼로,
**무작위 순서로 쌓인** 정육면체 블록 3개를 **같은 자리에** 아래부터 큰 것 → 중간 → 작은 것 순서로 다시 쌓는 Custom Code 태스크입니다.

블록 크기는 그리퍼로 잡았을 때 손가락이 멈춘 위치(Present Position)로 판별합니다.

## 파일 구성

| 파일 | 설명 |
|---|---|
| `restack_blocks.py` | 로봇에 넣는 Custom Code(DRL)입니다. 설정과 실행 코드가 한 파일에 들어 있습니다. |
| `gripper_init.py` | 그리퍼 초기화 Custom Code **개선판**입니다. 지금 쓰는 초기화 코드 대신 로봇에 등록하는 것을 권장합니다. 함수 이름과 사용법은 같습니다([아래](#그리퍼-초기화-코드-개선판) 참고). |
| `gripper_init_original.py` | 지금 쓰는 초기화 코드 원문에 `gripper_move()`를 붙인 사본입니다. `restack_blocks.py`는 이 원본으로도 동작합니다. |
| `simulate.py` | PC에서 미리 돌려 보는 도구입니다. 그리퍼를 Modbus 장치 수준으로 흉내 내서, 쌓인 순서 6가지를 모두 검사합니다. 로봇에는 올리지 않습니다. |

## 크기 판별 원리

1. 그리퍼에 `gripper_move(740)`(완전 닫힘)을 보냅니다. 기본 동작 모드가 전류 기반 위치 제어라서, 손가락은 블록에 닿으면 그 자리에서 멈춥니다(Goal Current 400 mA로 잡음).
2. Modbus FC03으로 그리퍼 상태를 읽습니다. 연속 두 번 읽은 위치값의 차이가 2 이하가 되면 멈춘 것으로 봅니다.

   | 레지스터 | Modbus 주소 | 내용 |
   |---|---|---|
   | 285 | 40286 | Moving |
   | 287 | 40288 | Present Current [mA] |
   | 290, 291 | 40291, 40292 | Present Position. `gripper_move()`가 `[stroke, 0]`으로 쓰는 순서(하위 워드 먼저)로 먼저 읽습니다. 값이 정상 범위(−100~1150)를 벗어나면 반대 순서로 다시 해석합니다. 값이 16비트 안이라 두 순서를 구분할 수 있습니다. |

3. 멈춘 위치값을 보정값 `GRIP_POS_LARGE/MEDIUM/SMALL` 중 가장 가까운 것과 비교합니다. 허용 오차 안에 들면 그 블록으로 판별합니다. 블록이 클수록 손가락이 덜 닫히므로 값이 작습니다.
4. 위치값이 완전 닫힘 근처(720 이상)면 빈손입니다.

상태를 읽기 전에는 항상 수신 버퍼를 먼저 비웁니다. 원본 `gripper_move()`는 응답을 읽지 않아 버퍼에 응답이 남기 때문입니다(개선판은 응답을 읽어 확인합니다). 응답이 여러 조각으로 나뉘어 와도 모아서 읽고, CRC(`modbus_recv_check`)로 확인합니다.

## 동작 순서

1. 설정값을 검사하고 그리퍼 통신을 확인합니다(움직이기 전). 확인 팝업에서 **Resume**을 누르면 시작합니다.
2. **위의 두 블록**을 차례로 잡아 크기를 판별하고, 임시 자리 1, 2에 내려놓습니다.
   - 탑 꼭대기 높이는 쌓인 순서와 상관없이 `FLOOR_Z + (L + M + S)`입니다. 그래서 무엇인지 모르는 맨 위 블록도 잡을 수 있습니다.
   - 블록을 하나 내려놓을 때마다, 판별한 크기만큼 꼭대기 높이를 낮춥니다.
   - 크기를 모를 때는 SMALL 기준 깊이까지만 내려가 잡습니다. 판별 뒤 그 블록을 더 깊이 잡을 수 있으면(`GRIP_DEPTH`가 클 때) 다시 잡습니다.
3. **맨 아래 블록**은 남은 하나로 정해집니다.
   - LARGE면 **그대로 둡니다**(잡기 4번).
   - 아니면 그 블록도 잡아서 측정값이 맞는지 확인하고 임시 자리 3에 내려놓습니다(잡기 6번).
4. 임시 자리에서 큰 것부터 탑 자리로 옮겨 쌓습니다. 잡을 때마다 측정값이 기대한 블록과 맞는지 다시 확인합니다.
5. 시작 XY 위치로 돌아갑니다.

```
  (위에서 본 모습, BUFFER_DIRECTION_DEG = 90 → +Y 방향)

   탑(TOWER_POS)     임시 자리 1       임시 자리 2       임시 자리 3
        ■ ───────────── □ ───────────── □ ───────────── □   → +Y
        └── 간격 ──┘
```

판별에 실패하면 **그 자리에서 그리퍼를 열고** 수직으로 올라간 뒤 알람으로 멈춥니다. 실패로 보는 경우는 빈손, 어느 보정값과도 맞지 않는 측정값, 같은 블록이 두 번 판별됨, 기대한 블록과 다름, 통신 끊김입니다. 이때 블록은 잡으려던 자리에 그대로 남습니다.
통신이 끊긴 경우를 대비해, 이때 여는 명령은 응답을 확인하지 않고 보냅니다.

### 임시 자리 자동 배치

탑에서 `BUFFER_DIRECTION_DEG` 방향으로, 간격만큼씩 떨어뜨려 3곳을 일렬로 둡니다. 간격은 블록 크기와 그리퍼 폭으로 자동 계산합니다.

```
간격 = 그리퍼 최대 벌림 폭 / 2 + 손가락 두께 10 + 가장 큰 블록 × 0.71 + 여유 15  (5mm 단위 올림)
```

기본값(60mm 블록, 106mm 그리퍼)이면 간격은 125mm이고, 임시 자리는 `(500, -25)`, `(500, 100)`, `(500, 225)`입니다.
그 방향에 장애물이 없고 작업 반경 안인지 꼭 확인하세요. 비어 있는 방향에 맞춰 `BUFFER_DIRECTION_DEG`를 바꾸면 됩니다(0 = +X, 90 = +Y, 180 = −X, −90 = −Y).

### 높이 (기본값: 60/45/30mm, `FLOOR_Z = 20`)

| 항목 | 계산 | 값 |
|---|---|---|
| 크기를 모르는 블록을 잡는 깊이 | `min(GRIP_DEPTH, SMALL − 5)` | 윗면에서 20mm |
| 크기를 아는 블록을 잡는 깊이 | `min(GRIP_DEPTH, 블록 − 5)` | 20 / 20 / 20mm |
| 첫 번째 블록 잡는 TCP z | `FLOOR_Z + 135 − 20` | 135 |
| 이동 높이(자동) | `FLOOR_Z + (L + M + S) + (L − 20) + TRAVEL_CLEARANCE` | 225 |
| 다시 쌓기 놓는 TCP z | L / M / S | 61 / 106 / 136 |

손가락 끝은 항상 블록 아래 면(받치는 면)보다 5mm 이상 위에 둡니다. 맨 위 블록의 크기를 몰라도 SMALL 기준으로 깊이를 제한하면, 그 아래 블록과 닿지 않습니다.

## 준비 사항

- **그리퍼 초기화 Custom Code를 이 코드보다 먼저** 실행해야 합니다. 이 코드는 `modbus_fc03()`, `modbus_fc16()`, `g_slaveid`, `gripper_move()`를 그대로 씁니다. 초기화 코드는 개선판 `gripper_init.py`를 권장합니다.
- **TCP와 `FLOOR_Z`**: `blocks/stack_blocks.py`와 같습니다. 그리퍼를 연 상태로 손가락 끝이 지면에 막 닿을 때의 TCP z를 `FLOOR_Z`로 씁니다.
- **처음 탑**: `TOWER_POS`에 중심이 맞게 쌓여 있어야 합니다. 블록 면은 손가락과 나란해야 합니다.
- **임시 자리 3곳은 비워 두세요.**
- **블록 크기 차이**: 이웃한 크기끼리 10mm 이상 차이 나는 것을 권장합니다. 1mm가 위치값 약 7에 해당하므로, 차이가 작으면 판별 여유가 줄어듭니다.
- **블록 재질**: 단단해야 합니다. 스펀지처럼 눌리는 블록은 위치값이 흔들립니다.

## 그리퍼 초기화 코드 개선판

`gripper_init.py`는 지금 쓰는 초기화 코드와 함수 이름, 사용법이 같습니다(`modbus_fc03/06/16()`, `recv_check()`, `gripper_move(stroke)`). 바뀐 점은 다음과 같습니다.

| 원본 | 개선판 |
|---|---|
| 응답 바이트가 오기만 하면 성공으로 봅니다. CRC를 검사하지 않는데도 실패 시 "CRC Check Fail"을 찍습니다. | `modbus_recv_check()`로 CRC를 확인하고, 응답이 요청과 맞는지도 확인합니다. 예외 응답이 오면 코드를 로그로 남깁니다. |
| 그리퍼가 응답하지 않으면 `while(True)`를 무한 반복합니다. | `GRIPPER_INIT_RETRY`(5)번 시도한 뒤 알람으로 멈춥니다. |
| `gripper_move()`가 응답을 읽지 않아 수신 버퍼에 응답이 남습니다. | 응답을 읽어 확인합니다(3번 재시도). 끝내 응답이 없거나 거부되면 알람으로 멈춥니다. 명령 뒤 `wait(1)`은 그대로라 기존 태스크(`blocks/stack_blocks.py` 등)와 호환됩니다. |
| 응답 원문을 매번 TP 로그로 찍습니다. | 실패할 때만 찍습니다. `GRIPPER_LOG_RAW = True`로 두면 원래처럼 찍습니다. |

slave id, 통신 속도, Goal Current는 파일 위쪽 변수(`GRIPPER_SLAVE_ID`, `GRIPPER_BAUDRATE`, `GRIPPER_GOAL_CURRENT`)로 바꿀 수 있습니다.

## 보정값 측정 (`CALIBRATION_MODE`)

보정값을 `None`으로 두면 `740 × (1 − 블록 크기 / 106)`으로 추정합니다(60/45/30mm → 321/426/531). 하지만 손가락이 링크 구조라 실제 값과 다를 수 있으니, **처음 한 번은 꼭 측정하세요.**

1. 블록을 **아래부터 LARGE, MEDIUM, SMALL** 순서로 `TOWER_POS`에 쌓습니다.
2. `CALIBRATION_MODE = True`로 두고 실행합니다.
3. 로봇이 다음 순서로 세 블록의 위치값을 잽니다.
   - SMALL과 MEDIUM은 임시 자리로 옮기면서 잽니다.
   - LARGE는 제자리에서 잡았다 놓기만 합니다.
4. 끝나면 탑을 원래대로 다시 쌓고, 팝업으로 값을 알려 줍니다.

   ```
   Calibration: GRIP_POS_LARGE = 323, GRIP_POS_MEDIUM = 426, GRIP_POS_SMALL = 531. Copy these to the settings.
   ```

5. 그 값을 `GRIP_POS_LARGE/MEDIUM/SMALL`에 적고 `CALIBRATION_MODE = False`로 되돌립니다.

평소 실행에서도 잡을 때마다 `restack: grip pos 335 current 398 -> LARGE (ref 321)` 형태로 TP 로그를 남깁니다. 값이 기준에서 조금씩 멀어지면 다시 보정하세요.

## 변수

`restack_blocks.py` 위쪽의 **[1] 사용자 설정**만 고치면 됩니다. **[2] 고급 설정**은 필요할 때만 고칩니다. 좌표는 모두 베이스 좌표계(DR_BASE), 단위 mm입니다.

### [1] 사용자 설정

| 변수 | 기본값 | 설명 |
|---|---|---|
| `BLOCK_SIZE_LARGE` | `60.0` | 가장 큰 블록의 한 변 [mm] |
| `BLOCK_SIZE_MEDIUM` | `45.0` | 중간 블록의 한 변 [mm] |
| `BLOCK_SIZE_SMALL` | `30.0` | 가장 작은 블록의 한 변 [mm] |
| `FLOOR_Z` | `20.0` (예시) | 그리퍼를 고려한 지면 z(손가락 끝이 지면에 닿을 때의 TCP z) |
| `TOWER_POS` | `(500, -150)` | 처음 탑이자 다시 쌓을 탑의 중심 `(x, y)` |
| `GRIP_POS_LARGE` | `None` | LARGE를 잡았을 때의 위치값(보정값). `None`이면 추정합니다. |
| `GRIP_POS_MEDIUM` | `None` | MEDIUM 보정값 |
| `GRIP_POS_SMALL` | `None` | SMALL 보정값. 셋 다 지정하거나 셋 다 `None`이어야 합니다. |

### [2] 고급 설정

| 변수 | 기본값 | 설명 |
|---|---|---|
| `CALIBRATION_MODE` | `False` | 보정값 측정 모드(위 참고) |
| `BUFFER_DIRECTION_DEG` | `90.0` | 임시 자리를 둘 방향 [deg]. 베이스 +X에서 반시계 방향으로 잽니다. |
| `BUFFER_SPACING` | `None` | 임시 자리 간격 [mm]. `None`이면 자동 계산합니다. 직접 넣은 값이 최소값보다 작으면 알람으로 멈춥니다. |
| `GRIP_POS_TOLERANCE` | `None` | 판별 허용 오차 [pulse]. `None`이면 이웃 보정값 간격의 40%입니다(기본 42). |
| `GRIP_DEPTH` | `20.0` | 윗면에서 손가락 끝까지 내려가 잡는 깊이 [mm]. 손가락 길이 안에서 정합니다. 손가락 끝은 블록 아래 면보다 5mm 위까지만 내려갑니다. 크기를 모르는 블록은 SMALL 기준으로 제한하고, 판별 뒤 더 깊이 잡을 수 있으면 다시 잡습니다. |
| `PLACE_GAP` | `1.0` | 놓을 때 블록 바닥과 아래 면 사이 간격 [mm] |
| `APPROACH_DIST` | `30.0` | 집기/놓기 위치 위 이 거리부터 저속으로 움직입니다 [mm]. |
| `TRAVEL_CLEARANCE` | `30.0` | 운반 중인 블록 바닥과 탑 꼭대기 사이 여유 [mm] |
| `TRAVEL_Z` | `None` | 이동 높이. `None`이면 자동 계산합니다. 직접 넣은 값이 자동 최소값보다 낮으면 알람으로 멈춥니다. |
| `TOOL_ORI` | `None` | 그리퍼 자세 `(rx, ry, rz)`. `None`이면 시작 자세 방향을 씁니다. |
| `DRY_RUN_OFFSET_Z` | `0.0` | 리허설용입니다. 그 높이만큼 위에서 그리퍼를 닫지 않고 경로만 확인합니다. 순서는 임시 자리 3곳을 모두 쓰는 경우로 가정합니다. |
| `VEL_TRAVEL` / `VEL_APPROACH` / `ACC` | `200` / `30` / `400` | 이동 속도, 저속, 가속도 |
| `GRIPPER_OPEN_POS` / `GRIPPER_CLOSE_POS` | `0` / `740` | `gripper_move()` 열림/닫힘 값 |
| `GRIPPER_STROKE_MM` | `106.0` | 그리퍼 최대 벌림 폭. Rev.1은 106, Rev.0은 109입니다. |
| `GRIP_SETTLE_TIMEOUT` | `3.0` | 그리퍼가 멈출 때까지 기다리는 최대 시간 [s] |
| `CONFIRM_BEFORE_START` / `RETURN_TO_START` | `True` / `True` | 시작 전 확인 팝업 / 끝나면 시작 위치로 복귀 |

## 태스크에 추가하기 (Task Writer 예)

```
1. Custom Code : 그리퍼 초기화 (gripper_init.py 개선판 권장)
2. Move J / L  : 탑 위쪽 안전한 위치로 이동 (그리퍼가 아래를 향하게)
3. Custom Code : restack_blocks.py 내용
```

## 처음 실행할 때 권장 순서

1. **PC 시뮬레이션**: `python3 simulate.py`로 쌓인 순서 6가지가 모두 `OK`인지 확인합니다.
2. **허공 리허설**: `DRY_RUN_OFFSET_Z = 50.0`으로 두고, TP 속도 슬라이더를 20~30%로 낮춰 실행합니다. 탑 위치와 임시 자리 3곳이 맞는지 봅니다.
3. **보정**: `CALIBRATION_MODE = True`로 보정값을 재서 변수에 넣습니다(위 참고).
4. **실제 실행**: 아무 순서로 쌓아 두고 낮은 속도로 실행합니다. TP 로그에서 측정값과 판별 결과를 확인합니다.

## PC 시뮬레이션 (`simulate.py`)

`gripper_init.py`(또는 `--init`으로 지정한 초기화 코드)와 `restack_blocks.py`를 실제 순서대로 그대로 실행합니다. DRL 함수는 가짜(stub)로 바꿔 끼우고, 그리퍼는 Modbus 장치 수준으로 흉내 냅니다.

- CRC 검사와 FC03/06/16 처리, 실제 레지스터 맵을 따릅니다.
- 응답을 여러 조각으로 나눠 돌려주고, 읽지 않은 응답은 버퍼에 남깁니다.
- 손가락은 75mm/s로 움직이다 블록에 닿으면 멈춥니다.

Python 3.8 이상이 필요하고, 추가 패키지는 필요 없습니다.

쌓인 순서 6가지를 모두 실행:

```bash
python3 simulate.py
```

순서 하나만 자세히 보기(위에서부터 SMALL, LARGE, MEDIUM):

```bash
python3 simulate.py --order SLM
```

보정 모드:

```bash
python3 simulate.py --calibrate
```

실제 위치값이 보정값과 60 어긋난 경우(알람이 나야 정상):

```bash
python3 simulate.py --order MSL --pos-bias 60
```

블록 하나가 없는 경우(빈손 알람이 나야 정상):

```bash
python3 simulate.py --order SML --missing SMALL
```

초기화 뒤 그리퍼 응답이 끊긴 경우(통신 알람이 나야 정상):

```bash
python3 simulate.py --order SML --mute-after 2
```

그리퍼가 처음부터 응답하지 않는 경우. 개선판 초기화 코드는 5번 시도한 뒤 알람으로 멈춥니다:

```bash
python3 simulate.py --order SML --mute-after 0
```

같은 상황을 원본 초기화 코드로 실행하면 끝나지 않습니다. 시뮬레이터는 시간 한도를 넘기면 이를 오류로 알려 줍니다:

```bash
python3 simulate.py --order SML --mute-after 0 --init gripper_init_original.py --time-limit 120
```

그리퍼가 Present Position을 상위 워드 먼저 돌려주는 경우(자동 판별 확인):

```bash
python3 simulate.py --order SLM --swap-read-words
```

`GRIP_DEPTH`를 크게 해서, 판별 뒤 다시 잡는 동작을 확인:

```bash
python3 simulate.py --order LSM --set GRIP_DEPTH=35
```

`--set NAME=VALUE`로 설정을 덮어쓸 수 있습니다. 예를 들어 `--set BUFFER_DIRECTION_DEG=0`처럼 씁니다.
실행 결과로는 블록 이동 순서(잡은 위치값, 낙하 거리), 최종 탑, 충돌·낙하 검사 결과, 예상 소요 시간이 나옵니다. 예상 시간은 잡기 6번 기준 약 90초, 4번 기준 약 59초입니다.

## 알람 메시지

| 메시지 | 원인 / 조치 |
|---|---|
| `[gripper] No response after 5 tries. ...` | (개선판 초기화 코드) 그리퍼가 응답하지 않습니다. 배선, 전원, ID, 통신 속도를 확인하세요. |
| `[gripper] gripper_move(N) was not acknowledged ...` | (개선판 초기화 코드) 그리퍼가 명령에 응답하지 않거나 거부했습니다. 그 자리에서 멈춥니다. |
| `Gripper init custom code (...) must run first.` | 그리퍼 초기화 Custom Code가 이 코드보다 앞에 없습니다. |
| `No valid Modbus response from gripper.` | 그리퍼가 응답하지 않습니다. 배선, 전원, slave id, 통신 속도를 확인하세요. |
| `Empty grip (pos N). No block between fingers.` | 빈손으로 닫혔습니다. 블록이 없거나, 탑 위치나 `FLOOR_Z`가 틀렸습니다. |
| `Grip pos N matches no block (...)` | 측정값이 어느 보정값과도 맞지 않습니다. 보정 모드로 다시 측정하세요. |
| `X identified twice` / `Expected X but measured Y` | 판별 결과가 앞뒤가 맞지 않습니다. 보정값이나 블록 상태를 확인하세요. |
| `Gripper did not settle within N s.` | 그리퍼가 멈추지 않습니다. `GRIP_SETTLE_TIMEOUT`을 늘리거나 그리퍼 상태를 확인하세요. |
| `GRIP_POS must be LARGE < MEDIUM < SMALL < 720.` | 보정값 순서가 틀렸습니다. |
| `Set all of GRIP_POS_... or leave all None.` | 보정값을 일부만 넣었습니다. |
| `GRIP_POS_TOLERANCE N is too large.` | 허용 오차가 이웃 보정값 간격의 절반 이상입니다. |
| `BUFFER_SPACING N mm is too small.` | 임시 자리 간격이 손가락 여유보다 좁습니다. |
| `SMALL block N mm is too small to grip safely` | SMALL 블록이 8mm보다 작아, 아래 블록과 여유를 두고 잡을 수 없습니다. |
| `Block sizes must be LARGE > MEDIUM > SMALL.` 등 | 블록 크기나 숫자, 좌표 설정이 잘못됐습니다. |

## 한계와 주의

- **원본 초기화 코드는 그리퍼가 응답하지 않으면 끝나지 않습니다.** 개선판 `gripper_init.py`로 바꾸면 5번 시도한 뒤 알람으로 멈춥니다.
- **개선판 `gripper_move()`는 응답이 없으면 그 자리에서 멈춥니다.** 블록을 잡은 채로 멈출 수 있으니, 그리퍼 상태를 확인한 뒤 손으로 수습하세요. 판별 실패 등 이 코드가 직접 판단해 멈출 때는 그리퍼를 열고 올라간 뒤 멈춥니다.
- **블록 회전(yaw)은 보정하지 않습니다.** 블록이 손가락과 나란히 쌓여 있어야 합니다.
- **PC 시뮬레이션으로만 검증했습니다.** 실제 로봇에서는 반드시 허공 리허설, 보정, 저속 실행 순서로 진행하세요.

## 참고

| 항목 | 내용 |
|---|---|
| [RH-P12-RN(A) e-Manual](https://emanual.robotis.com/docs/en/platform/rh_p12_rna/) | 컨트롤 테이블과 Modbus 주소, 기본 동작 모드(5: 전류 기반 위치 제어), 스트로크 106mm |
| Doosan Programming Manual V2.9.3 | 13.2 Flange I/O(`flange_serial_*`, Robotiq 상태 읽기 예제), 9.4.18 `modbus_send_make`, 9.4.19 `modbus_recv_check`, 8.1 `d2r`, 8.2 `sin`/`cos` |
| [`movel`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/movel), [`get_current_posx`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/get_current_posx-ref), [`tp_popup`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/tp_popup-message-pm_type-dr_pm_message-button_type), [`exit`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/exit) | 모션과 TP 명령 |
