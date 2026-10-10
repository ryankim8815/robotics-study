# 두산 로봇팔 블록 탑 쌓기 (DRL Custom Code)

두산 로봇팔(컨트롤러 S/W **DRSUP V2.10.3**)과 ROBOTIS **RH-P12-RN(A)** 그리퍼로
크기가 다른 정육면체 블록 3개를 **큰 것 → 중간 → 작은 것** 순서로 한 탑에 쌓는 Custom Code 태스크입니다.
블록 크기 3개, 그리퍼를 고려한 지면 z, 블록 위치 3개, 탑 위치를 변수로 지정합니다.

## 파일 구성

| 파일 | 설명 |
|---|---|
| `stack_blocks.py` | 로봇에 넣는 Custom Code(DRL)입니다. 설정과 실행 코드가 한 파일에 들어 있습니다. |
| `simulate.py` | PC에서 미리 돌려 보는 도구입니다. 블록을 잡고 옮기는 과정을 따라가며 충돌과 최종 탑을 검사합니다. 로봇에는 올리지 않습니다. |

## 동작 순서

1. 설정값을 검사합니다(블록 크기 순서, 그리퍼 벌림 폭, 위치 겹침, 숫자 범위). 문제가 있으면 TP에 알람을 띄우고 멈춥니다.
2. 그리퍼 Custom Code의 `gripper_move()`가 정의되어 있는지 확인합니다.
3. 현재 TCP 자세를 읽고 확인 팝업을 띄웁니다. **Resume**을 누르면 시작합니다.
4. 이동 높이(`TRAVEL_Z`)까지 수직으로 올라간 뒤 그리퍼를 엽니다.
5. LARGE → MEDIUM → SMALL 순서로 블록마다 반복합니다.
   - **집기**: 블록 위로 이동 → 빠르게 내려감 → 마지막 `APPROACH_DIST`는 천천히 → `gripper_move(740)` → 천천히 올라감 → 이동 높이
   - **놓기**: 탑 위로 이동 → 빠르게 내려감 → 마지막 `APPROACH_DIST`는 천천히 → `gripper_move(0)` → 천천히 올라감 → 이동 높이
6. 시작 XY 위치로 돌아갑니다.

블록을 들고 이동할 때는 항상 `TRAVEL_Z` 높이에서 움직입니다. 이 높이는 **완성된 탑보다** 운반 중인 블록 바닥이 `TRAVEL_CLEARANCE` 이상 높도록 자동으로 계산합니다.

```
 z
 ▲
 │  TRAVEL_Z  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   블록을 들고 이동하는 높이
 │
 │                          ┌────┐
 │                          │ S  │
 │                       ┌──┴────┴──┐
 │                       │    M     │
 │                    ┌──┴──────────┴──┐
 │                    │       L        │
 │  FLOOR_Z ━━━━━━━━━━┷━━━━━━━━━━━━━━━━┷━━━━   손가락 끝이 지면에 닿는 TCP z
 │                         TOWER_POS
```

### 높이 계산

| 항목 | 계산 |
|---|---|
| 파지 높이(블록 바닥 → 손가락 끝) `g` | `블록 크기 − min(GRIP_DEPTH, 블록 크기 / 2)` |
| 집기 TCP z | `FLOOR_Z + g` |
| 놓기 TCP z | `아래 면 높이 + g + PLACE_GAP` (아래 면: L은 지면, M은 L 윗면, S는 M 윗면) |
| 이동 높이 `TRAVEL_Z`(자동) | `FLOOR_Z + (L + M + S) + g(L) + TRAVEL_CLEARANCE` |

기본값(60/45/30mm, `FLOOR_Z = 20`)으로 계산하면 다음과 같습니다.

| 블록 | 집기 z | 놓기 z | 놓은 뒤 바닥 / 윗면 z |
|---|---|---|---|
| LARGE 60 | 60.0 | 61.0 | 20 / 80 |
| MEDIUM 45 | 45.0 | 106.0 | 80 / 125 |
| SMALL 30 | 35.0 | 141.0 | 125 / 155 |

이동 높이는 225.0입니다.

## 준비 사항

- **그리퍼 초기화**: 사용 중인 그리퍼 Custom Code를 **이 코드보다 먼저** 실행해야 합니다. 이 코드가 토크 ON과 Goal Current 설정을 하고, `gripper_move()`를 정의합니다.
  이 코드에서는 `gripper_move(0)`(열림)과 `gripper_move(740)`(완전 닫힘)만 호출합니다.
- **잡는 힘**: 블록 크기와 상관없이 `740`(완전 닫힘)을 보냅니다. 그리퍼는 블록에 닿으면 멈추고, 초기화 코드의 Goal Current(275번 레지스터, 현재 `400`) 전류로 블록을 잡습니다.
  블록이 미끄러지면 Goal Current를 올리고, 블록이 눌려 찌그러지면 내리세요.
- **그리퍼 자세**: 그리퍼는 아래(-z)를 향해야 하고, 손가락은 블록 면과 나란해야 합니다. 이전 태스크에서 이 자세로 맞춰 두면 `TOOL_ORI = None`일 때 그 방향을 그대로 씁니다. 숫자로 직접 지정하려면 `TOOL_ORI = (0, 180, 0)`처럼 넣습니다.
- **블록 방향**: 블록의 면이 그리퍼 손가락과 나란하게 놓여 있어야 합니다(z축 회전을 맞춤). 탑도 같은 방향으로 쌓입니다.
- **지면**: 블록이 놓인 곳과 탑 위치가 같은 높이의 평평한 면이어야 합니다.
- **시작 위치**: 이전 태스크에서 블록과 부딪히지 않는 위쪽 공간으로 로봇을 옮겨 둡니다.

## 값 지정 방법

### 지면 z `FLOOR_Z`

1. 그리퍼를 연 상태(`gripper_move(0)`)로 지면 위에서 조그로 천천히 내립니다.
2. **손가락 끝이 지면에 막 닿을 때** TP에서 베이스 좌표 Z를 읽어 `FLOOR_Z`에 적습니다.

TCP를 어디로 잡았든(플랜지, 손가락 끝 등) 상관없습니다. 모든 높이를 같은 TCP 기준의 `FLOOR_Z`에서 계산하기 때문입니다. 다만 측정할 때와 실행할 때 TCP 설정이 같아야 합니다.

기본값 `20.0`은 예시일 뿐입니다. 실제보다 낮게 넣으면 손가락이 지면을 찍습니다.

### 블록 위치 / 탑 위치

1. TCP를 블록 **중심** 위로 맞춥니다(손가락 사이 한가운데).
2. TP에서 베이스 좌표 X, Y를 읽어 `(x, y)`로 적습니다.

탑 위치는 비어 있는 곳의 중심입니다. `TOWER_POS`를 LARGE 블록 위치와 같게 두면 LARGE를 제자리에 다시 놓고 그 위에 쌓습니다.

### 배치 간격

- 처음부터 바닥에 함께 있는 블록끼리(블록 3개, 그리고 탑 자리와 MEDIUM/SMALL) 겹치면 알람으로 멈춥니다. 겹침 기준은 중심 거리가 `(두 블록 크기의 합) / 2`보다 작을 때입니다.
- 열린 손가락(최대 106mm)이 이웃 블록에 닿지 않도록 **중심 사이를 `63 + 이웃 블록 크기 × 0.71` mm 이상**(열린 폭의 절반 53 + 손가락 두께 10 + 이웃 블록 대각선의 절반) 띄우는 것을 권장합니다. 기본값처럼 150mm씩 띄우면 충분합니다.
  이보다 가까우면 `simulate.py`가 경고를 냅니다.

## 변수

`stack_blocks.py` 위쪽의 **[1] 사용자 설정**만 고치면 됩니다. **[2] 고급 설정**은 필요할 때만 고칩니다. 좌표는 모두 베이스 좌표계(DR_BASE), 단위 mm입니다.

### [1] 사용자 설정

| 변수 | 기본값 | 설명 |
|---|---|---|
| `BLOCK_SIZE_LARGE` | `60.0` | 가장 큰 블록의 한 변 [mm] |
| `BLOCK_SIZE_MEDIUM` | `45.0` | 중간 블록의 한 변 [mm] |
| `BLOCK_SIZE_SMALL` | `30.0` | 가장 작은 블록의 한 변 [mm]. `LARGE > MEDIUM > SMALL`이어야 합니다. |
| `FLOOR_Z` | `20.0` (예시) | 그리퍼를 고려한 지면 z. 손가락 끝이 지면에 닿을 때의 TCP z입니다. |
| `BLOCK_POS_LARGE` | `(450, 200)` | 가장 큰 블록의 중심 `(x, y)` |
| `BLOCK_POS_MEDIUM` | `(450, 50)` | 중간 블록의 중심 `(x, y)` |
| `BLOCK_POS_SMALL` | `(450, -100)` | 가장 작은 블록의 중심 `(x, y)` |
| `TOWER_POS` | `(600, 50)` | 탑을 쌓을 중심 `(x, y)` |

### [2] 고급 설정

| 변수 | 기본값 | 설명 |
|---|---|---|
| `GRIP_DEPTH` | `20.0` | 블록 윗면에서 손가락 끝까지 내려가 잡는 깊이 [mm]. 블록 높이의 절반을 넘지 않게 자동으로 줄입니다(30mm 블록이면 15mm). |
| `PLACE_GAP` | `1.0` | 놓을 때 블록 바닥과 아래 면 사이 간격 [mm]. 이 높이에서 놓아 떨어뜨립니다. |
| `APPROACH_DIST` | `30.0` | 집기/놓기 위치 위 이 거리부터 저속으로 움직입니다 [mm]. |
| `TRAVEL_CLEARANCE` | `30.0` | 운반 중인 블록 바닥과 완성된 탑 꼭대기 사이 여유 [mm] |
| `TRAVEL_Z` | `None` | 이동 높이 [mm]. `None`이면 자동 계산합니다. 숫자를 넣었는데 자동 최소값보다 낮으면 알람으로 멈춥니다. |
| `TOOL_ORI` | `None` | 그리퍼 자세 `(rx, ry, rz)` [deg]. `None`이면 시작 자세 방향을 씁니다. |
| `DRY_RUN_OFFSET_Z` | `0.0` | 리허설용입니다. 예를 들어 `50.0`이면 모든 집기/놓기를 50mm 위에서 하고 그리퍼는 닫지 않습니다. |
| `VEL_TRAVEL` | `200.0` | 이동 속도 [mm/s] |
| `VEL_APPROACH` | `30.0` | 집기/놓기 직전 저속 [mm/s] |
| `ACC` | `400.0` | 가속도 [mm/s²] |
| `GRIPPER_OPEN_POS` | `0` | `gripper_move()` 열림 값 |
| `GRIPPER_CLOSE_POS` | `740` | `gripper_move()` 완전 닫힘 값 |
| `GRIPPER_WAIT_SEC` | `1.5` | 그리퍼 명령 뒤 대기 시간 [s]. 최대 닫힘 속도가 75mm/s이므로 106mm를 다 닫는 데 약 1.4초 걸립니다. |
| `GRIPPER_STROKE_MM` | `106.0` | 그리퍼 최대 벌림 폭 [mm]. Rev.1은 106, Rev.0은 109입니다. `LARGE + 6mm`가 이 값을 넘으면 알람으로 멈춥니다. |
| `CONFIRM_BEFORE_START` | `True` | 시작 전 확인 팝업을 띄웁니다. |
| `RETURN_TO_START` | `True` | 끝나면 시작 XY 위치로 돌아갑니다. |

## 태스크에 추가하기 (Task Writer 예)

```
1. Custom Code : 그리퍼 초기화 (gripper_move 정의, 토크 ON, Goal Current)
2. Move J / L  : 블록 위쪽 안전한 위치로 이동 (그리퍼가 아래를 향하게)
3. Custom Code : stack_blocks.py 내용
```

1. 3번 Custom Code에 `stack_blocks.py` 내용을 통째로 붙여넣거나 파일로 불러옵니다(USB).
2. 위쪽 설정 블록에서 블록 크기, `FLOOR_Z`, 블록 위치, 탑 위치를 고칩니다.

Task Builder를 쓴다면 Custom Code 스킬로 같은 순서를 만듭니다. 메뉴 이름이나 위치는 DART Platform 버전에 따라 조금 다를 수 있습니다.
파일을 불러올 때 `.drl` 확장자를 요구하면 파일 이름만 `stack_blocks.drl`로 바꾸면 됩니다.

`gripper_move() is not defined` 알람이 뜨면 그리퍼 초기화 Custom Code가 이 코드보다 앞에 있는지 확인하세요.

## 처음 실행할 때 권장 순서

1. **PC 시뮬레이션**: `simulate.py`로 높이, 순서, 충돌, 최종 탑을 확인합니다(아래 참고).
2. **허공 리허설**: `DRY_RUN_OFFSET_Z = 50.0`으로 두고, TP 속도 슬라이더를 20~30%로 낮춰 실행합니다. 블록 위치와 탑 위치가 맞는지 눈으로 확인합니다. 이때 그리퍼는 닫지 않습니다.
3. **실제 실행**: `DRY_RUN_OFFSET_Z = 0.0`으로 되돌리고, 낮은 속도로 첫 블록을 잡는 순간을 지켜봅니다.
   - 손가락이 블록 윗면에 걸리면 위치(x, y)가 틀린 것입니다.
   - 손가락이 지면에 닿으면 `FLOOR_Z`가 낮은 것입니다.
4. **속도 올리기**: 문제가 없으면 TP 속도 슬라이더나 `VEL_TRAVEL`을 올립니다.

## PC 시뮬레이션 (`simulate.py`)

로봇 없이 `stack_blocks.py`를 그대로 실행합니다. DRL 함수와 `gripper_move()`는 가짜(stub)로 바꿔 끼웁니다.
블록을 실제로 잡고 옮기는 것처럼 상태를 따라가며 검사합니다. Python 3.8 이상이 필요하고, 추가 패키지는 필요 없습니다.

현재 설정 그대로 실행:

```bash
python3 simulate.py
```

설정을 덮어써서 실행(Python 리터럴):

```bash
python3 simulate.py --set BLOCK_SIZE_LARGE=80 --set "TOWER_POS=(600, 0)"
```

가상 시작 자세를 지정하기(X Y Z RX RY RZ):

```bash
python3 simulate.py --start 400 0 300 0 180 0
```

`gripper_move()`가 없는 상황을 시험하기:

```bash
python3 simulate.py --no-gripper
```

출력되는 내용은 다음과 같습니다.

- **그리퍼 동작 순서**: 잡기/놓기 위치, 손가락이 잡은 높이, 놓을 때 떨어진 거리와 아래에 있는 블록
- **최종 탑**: 블록별 바닥/윗면 z와 중심 좌표
- **검사**:
  - 오류: 운반 중인 블록이 다른 블록과 부딪힘, 손가락이 지면 아래로 내려감, 빈 그리퍼를 닫음, 탑 순서나 높이가 틀림
  - 경고: 열린 손가락이 이웃 블록과 가까움, 5mm 넘게 떨어뜨림
- **예상 소요 시간**: 기본값 기준 약 46초(그리퍼 대기 포함)

오류가 있거나 설정 알람이 나면 종료 코드 1로 끝납니다.

## 알람 메시지

| 메시지 | 원인 / 조치 |
|---|---|
| `Block sizes must be LARGE > MEDIUM > SMALL.` | 블록 크기 순서가 틀렸거나 같은 크기가 있습니다. |
| `LARGE block N mm is too big for gripper stroke ...` | 가장 큰 블록 + 6mm가 그리퍼 최대 벌림 폭보다 큽니다. |
| `X and Y overlap: distance ...` | 처음 놓인 블록끼리, 또는 탑 자리와 블록이 겹칩니다. 위치를 띄우세요. |
| `TRAVEL_Z ... is too low. Min is ...` | 지정한 이동 높이가 탑 높이에 비해 낮습니다. 최소값 이상으로 올리거나 `None`으로 둡니다. |
| `gripper_move() is not defined. ...` | 그리퍼 초기화 Custom Code가 먼저 실행되지 않았습니다. |
| `TOOL_ORI must be None or (rx, ry, rz) in deg.` | `TOOL_ORI` 형식이 틀렸습니다. |
| `NAME must be (x, y) in mm.` / `NAME must be a number.` | 좌표나 숫자 형식이 틀렸습니다. |
| `NAME=value is out of range [lo, hi].` | 숫자 설정이 허용 범위를 벗어났습니다. |

## 한계와 주의

- **잡기 성공 여부를 확인하지 않습니다.** 그리퍼 위치를 읽지 않기 때문에, 블록을 놓쳐도 다음 동작을 계속합니다.
- **블록 회전(yaw)은 보정하지 않습니다.** 블록이 손가락과 나란히 놓여 있어야 합니다.
- **이동 높이를 보수적으로 잡습니다.** 완성된 탑 기준으로 정하므로, 블록이 크면 이동 높이가 꽤 높아집니다. 작업 반경 안인지 확인하세요.
- **PC 시뮬레이션으로만 검증했습니다.** 실제 로봇에서는 반드시 허공 리허설과 저속 실행부터 하세요.

## 참고

| 항목 | 내용 |
|---|---|
| [`movel`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/movel) | 직선 이동(`vel`, `acc`, `ref=DR_BASE`) |
| [`get_current_posx`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/get_current_posx-ref) | 현재 TCP 자세 `(posx, sol)` |
| [`tp_popup`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/tp_popup-message-pm_type-dr_pm_message-button_type) / [`tp_log`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/tp_log-message) | TP 팝업과 로그. 256 byte 이내, 줄바꿈 불가 |
| [`exit`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/exit), `wait` | 프로그램 정지, 대기 |
| [RH-P12-RN(A) e-Manual](https://emanual.robotis.com/docs/en/platform/rh_p12_rna/) | 스트로크 106mm(Rev.1), 최대 파지력 170N, 최대 닫힘 속도 75mm/s. Modbus 주소: Torque Enable 40257, Goal Current 40276, Goal Position 40283 |

DRL 명령은 모두 2.x/3.x 공통의 기본 명령입니다. 링크는 온라인 Programming Manual(3.2.0)이며, V2.10 전용 페이지는 공개 매뉴얼에서 찾지 못했습니다.
