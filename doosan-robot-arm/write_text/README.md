# 두산 로봇팔 글씨 쓰기 (DRL Custom Code)

두산 로봇팔(컨트롤러 S/W **DRSUP V2.10.3**)로 캔버스에 영문 문장을 쓰는 Custom Code 태스크입니다.
캔버스 4꼭지점 좌표, 쓸 문장(최대 20자), 펜을 들어 올릴 z 높이를 변수로 지정하면
문장을 캔버스 가운데에 한 줄로 씁니다. 글자는 코드에 들어 있는 단선(single-stroke) 폰트로 씁니다.

## 파일 구성

| 파일 | 설명 |
|---|---|
| `write_text.py` | 로봇에 넣는 Custom Code(DRL)입니다. 설정, 폰트, 실행 코드가 한 파일에 들어 있습니다. |
| `preview.py` | PC에서 미리 돌려 보는 도구입니다. 로봇에는 올리지 않습니다. |

## 동작 순서

1. 설정값을 검사합니다(문장, 숫자 범위, 꼭지점 순서). 문제가 있으면 TP에 알람을 띄우고 멈춥니다.
2. 현재 TCP 자세를 읽습니다. 자세(rx, ry, rz)는 그대로 유지하고, **글씨는 `WRITE_Z` 높이에서** 씁니다(`None`이면 현재 TCP z).
3. 확인 팝업을 띄웁니다(글자 높이, 획 수, 쓰기 z와 그 출처). **Resume**을 누르면 시작합니다.
4. 시작 위치가 펜 든 높이(`WRITE_Z + PEN_UP_Z`)보다 낮으면 제자리에서 그 높이까지 수직으로 올립니다. 더 높으면 그대로 출발합니다.
5. 획마다 `시작점 위로 이동 → 펜 내림 → 획을 따라 쓰기 → 펜 올림`을 반복합니다.
6. 펜을 든 채로 시작 XY 위치로 돌아갑니다. 높이는 펜 든 높이와 시작 높이 중 높은 쪽입니다.

모든 수평 이동은 펜을 든 높이(`WRITE_Z + PEN_UP_Z`) 이상에서 합니다. `WRITE_Z` 높이에서는 글씨를 쓸 때만 움직입니다.

## 준비 사항

- **TCP**: Workcell Manager에서 TCP를 펜 끝으로 설정합니다(툴 무게 포함). 캔버스 좌표와 z가 모두 펜 끝 기준입니다.
- **캔버스 수평**: 캔버스는 베이스 XY 평면과 평행해야 합니다. z 하나로 전체를 쓰기 때문에 기울어져 있으면 한쪽은 안 써지고 다른 쪽은 눌립니다.
- **펜 홀더**: 스프링이 들어간 펜 홀더를 권장합니다. z가 1~2mm 틀려도 흡수해 줍니다.
- **이전 태스크**: 펜이 수직으로 선 자세로 캔버스 위쪽(펜 든 높이 이상)에 로봇을 옮겨 둡니다(예: Move L).
  이 코드는 시작 자세의 방향(rx, ry, rz)만 가져다 쓰고, 높이는 `WRITE_Z`를 씁니다.
  `WRITE_Z = None`으로 두면 이전 태스크가 펜 끝을 종이에 막 닿게 맞춘 z를 그대로 씁니다.

## 캔버스 4꼭지점 지정

위/아래/왼쪽/오른쪽은 **글씨를 읽는 사람 기준**입니다.

```
                          (글씨 위쪽)
   CANVAS_TOP_LEFT ●─────────────────────● CANVAS_TOP_RIGHT
                   │                     │
                   │    Hello Doosan     │
                   │                     │
CANVAS_BOTTOM_LEFT ●─────────────────────● CANVAS_BOTTOM_RIGHT
                         (글씨 아래쪽)
                              ▲
                         읽는 사람 위치
```

좌표 얻는 방법은 이렇습니다.

1. 펜 끝을 조그(jog)로 캔버스의 각 꼭지점에 가져갑니다.
2. TP에서 **베이스 좌표계(Base)** 의 X, Y 값을 읽어 `(x, y)`로 적습니다(단위 mm).

```python
CANVAS_TOP_LEFT     = (560.0,  148.5)
CANVAS_TOP_RIGHT    = (560.0, -148.5)
CANVAS_BOTTOM_RIGHT = (350.0, -148.5)
CANVAS_BOTTOM_LEFT  = (350.0,  148.5)
```

기본값은 A4 용지(297 × 210 mm)를 가로로 놓은 예시입니다. 로봇 앞 X 350~560mm에 놓고, 로봇 쪽에서 +X 방향을 바라보며 읽는 배치입니다. 실제 값으로 바꿔서 쓰세요.

- **순서를 바꿔 넣으면 글씨가 거울상으로 써집니다.** 그래서 코드가 미리 검사하고 알람으로 멈춥니다.
- 캔버스가 비스듬히 놓였거나 정확한 직사각형이 아니어도 됩니다. 4꼭지점 사이를 보간해서 맞춥니다.

## 쓰기 높이 `WRITE_Z` 지정

1. 펜 끝을 캔버스 위로 가져가서 조그로 천천히 내립니다. 펜 끝이 종이에 **막 닿는** 위치에서 멈춥니다.
2. TP에서 베이스 좌표계의 Z 값을 읽어 `WRITE_Z`에 적습니다(단위 mm, 절대값).

```python
WRITE_Z = 20.0   # 예시값. 반드시 실제 값으로 바꾸세요.
```

- 기본값 `20.0`은 예시일 뿐입니다. 실제보다 낮게 넣으면 펜이 캔버스를 누르며 충돌합니다. 처음에는 꼭 [허공 리허설](#처음-실행할-때-권장-순서)을 하세요.
- 캔버스의 몇 군데(꼭지점 근처)에서 Z를 재 보고 차이가 1mm 넘게 나면 캔버스 수평부터 맞추세요.
- `WRITE_Z = None`이면 시작할 때의 TCP z를 씁니다. 이전 태스크에서 높이를 맞추거나, 이전 태스크에서 변수로 계산해 넣을 때 쓰면 됩니다(예: `WRITE_Z = my_z`).

## 변수

`write_text.py` 위쪽의 **[1] 사용자 설정**만 고치면 됩니다. **[2] 고급 설정**은 필요할 때만 고칩니다.

### [1] 사용자 설정

| 변수 | 기본값 | 설명 |
|---|---|---|
| `CANVAS_TOP_LEFT` 외 3개 | A4 예시 | 캔버스 4꼭지점 `(x, y)` [mm, 베이스 좌표] |
| `TEXT` | `"Hello Doosan"` | 쓸 문장. 최대 20자 |
| `WRITE_Z` | `20.0` (예시) | 글씨를 쓸 z [mm, 베이스 좌표 절대값]. 펜 끝이 종이에 막 닿는 TCP z입니다. `None`이면 시작할 때의 TCP z를 씁니다. |
| `PEN_UP_Z` | `15.0` | 펜을 들어 올릴 높이 [mm]. `WRITE_Z` 기준 +z 상대값(1~200) |

### [2] 고급 설정

| 변수 | 기본값 | 설명 |
|---|---|---|
| `CHAR_HEIGHT` | `0.0` | 대문자 높이 [mm]. `0`이면 캔버스에 맞춰 가장 크게 씁니다. 지정한 값이 캔버스에 안 들어가면 최대값을 알려 주고 멈춥니다. |
| `CANVAS_MARGIN` | `10.0` | 캔버스 가장자리 여백 [mm] |
| `LETTER_SPACING` | `0.25` | 자간. 대문자 높이 대비 비율입니다. |
| `DRY_RUN_OFFSET_Z` | `0.0` | 리허설용입니다. 예를 들어 `20.0`이면 `WRITE_Z`보다 20mm 위 허공에서 씁니다. |
| `VEL_DRAW` | `50.0` | 쓰기 속도 [mm/s] |
| `VEL_TRAVEL` | `150.0` | 펜을 든 상태의 이동 속도 [mm/s] |
| `VEL_PEN` | `30.0` | 펜 올림/내림 속도 [mm/s] |
| `ACC` | `300.0` | 가속도 [mm/s²] |
| `BLEND_RADIUS` | `0.0` | 획 안 꼭짓점의 블렌딩 반경 [mm]. `0`이면 점마다 멈춰서 정확하게 씁니다. `0.5~1.0`이면 곡선이 부드러워집니다. 구간 길이의 40%를 넘지 않게 자동으로 줄입니다. |
| `CONFIRM_BEFORE_START` | `True` | 시작 전 확인 팝업을 띄웁니다. |
| `RETURN_TO_START` | `True` | 끝나면 펜을 든 채 시작 XY로 돌아갑니다. |
| `CHECK_CORNER_ORDER` | `True` | 꼭지점 순서(거울상)를 검사합니다. 로봇을 천장이나 벽에 달아서 베이스 z축이 아래를 향하면 `False`로 둡니다. |

## 지원 문자

```
A-Z  a-z  0-9  공백  . , ! ? - ' " : / + = ( )
```

- 최대 20자이고 한 줄로 씁니다(줄바꿈 없음).
- 지원하지 않는 문자가 있으면 알람에 해당 문자를 보여 주고 멈춥니다. 한글 같은 비ASCII 문자는 `U+C548`처럼 코드로 보여 줍니다.

## 태스크에 추가하기

### Task Writer

1. 앞 단계에 펜 끝이 종이에 닿는 위치로 가는 이동 명령(예: Move L)을 둡니다.
2. 그다음에 **Custom Code** 명령을 추가합니다.
3. `write_text.py` 내용을 통째로 붙여넣거나 파일로 불러옵니다(USB).
4. 위쪽 설정 블록에서 꼭지점, `TEXT`, `PEN_UP_Z`를 고칩니다.

### Task Builder

Custom Code 스킬을 추가하고 같은 방법으로 코드를 넣습니다.

메뉴 이름이나 위치는 DART Platform 버전에 따라 조금 다를 수 있습니다. 파일을 불러올 때 `.drl` 확장자를 요구하면 파일 이름만 `write_text.drl`로 바꾸면 됩니다.

## 처음 실행할 때 권장 순서

1. **PC 미리보기**: `preview.py`로 글씨 배치와 경로를 확인합니다(아래 참고).
2. **허공 리허설**: `DRY_RUN_OFFSET_Z = 20.0`으로 두고, TP 속도 슬라이더를 20~30%로 낮춰 실행합니다. 경로, 펜 들기, 작업 반경을 확인합니다.
3. **실제 쓰기**: `DRY_RUN_OFFSET_Z = 0.0`으로 되돌립니다. 글씨가 흐리면 `WRITE_Z`를 0.5~1mm 낮추고, 눌려서 번지면 높입니다.
4. **다듬기**: 곡선이 각져 보이면 `BLEND_RADIUS = 0.5`를 넣고, 필요하면 `VEL_DRAW`를 올립니다.

## PC 미리보기 (`preview.py`)

로봇 없이 `write_text.py`를 그대로 실행합니다. DRL 함수(`movel`, `get_current_posx`, `tp_popup` 등)는 가짜(stub)로 바꿔 끼웁니다.
Python 3.8 이상이 필요하고, 그림을 저장하려면 matplotlib가 필요합니다(없으면 요약만 출력).

현재 설정 그대로 미리보기:

```bash
python3 preview.py
```

문장만 바꿔 보기:

```bash
python3 preview.py --text "ROBOT 2026"
```

다른 설정도 덮어써 보기(Python 리터럴):

```bash
python3 preview.py --set CHAR_HEIGHT=20 --set "CANVAS_TOP_LEFT=(600, 150)"
```

가상 시작 자세를 지정하기(X Y Z RX RY RZ). 지정하지 않으면 캔버스 중앙, `WRITE_Z + PEN_UP_Z + 50`mm 높이에서 시작합니다(`WRITE_Z = None`이면 z=0):

```bash
python3 preview.py --start 450 0 120 0 180 0 --out path.png
```

출력되는 내용은 다음과 같습니다.

- **요약**: 쓰기/펜 든 z, `movel` 횟수, 쓰기/이동 거리, 대략적인 소요 시간(예: 12자 기준 약 1분)
- **안전 검사**: 쓰는 점이 모두 캔버스 안에 있는지, 수평 이동을 모두 펜을 든 상태에서 하는지, 실제 쓰기 높이가 `WRITE_Z`(+리허설 오프셋)와 같은지
- **`preview.png`**: 왼쪽은 읽는 사람 시점, 오른쪽은 로봇 위에서 본 베이스 좌표 시점입니다. 검은 선이 쓰기, 파란 점선이 펜을 든 이동입니다.

설정 오류가 있으면 로봇과 같은 알람 메시지를 출력하고 종료 코드 1로 끝납니다.

## 알람 메시지

| 메시지 | 원인 / 조치 |
|---|---|
| `TEXT is empty.` / `TEXT has N chars (max 20).` | 문장이 비었거나 20자를 넘습니다. |
| `Unsupported characters in TEXT: ...` | 지원하지 않는 문자가 있습니다. [지원 문자](#지원-문자)를 확인하세요. |
| `TEXT has nothing to draw.` | 공백만 있습니다. |
| `Corner order is mirrored. ...` | 왼쪽과 오른쪽 꼭지점이 뒤바뀌었습니다. 이대로 쓰면 거울상이 됩니다. |
| `Corners must form a convex quad ...` | 꼭지점 순서가 꼬였거나(대각선끼리 바뀜) 한 줄 위에 있습니다. |
| `CHAR_HEIGHT x mm does not fit. Max is y mm.` | 글자가 캔버스보다 큽니다. `CHAR_HEIGHT`를 y 이하로 줄이거나 `0`(자동)으로 둡니다. |
| `CANVAS_MARGIN is too large ...` / `Canvas is too small ...` | 여백이 너무 크거나 캔버스가 10mm보다 작습니다. |
| `NAME=value is out of range [lo, hi].` | 숫자 설정이 허용 범위를 벗어났습니다. |

## 글자 추가/수정

폰트는 `write_text.py`의 `TW_FONT`에 있습니다.

```python
#   문자: (글자 폭, [획1, 획2, ...]),  획 = [(x, y), ...]
'T': (7, [[(0, 10), (7, 10)], [(3.5, 10), (3.5, 0)]]),
'.': (0, [[(0, 0)]]),          # 점이 1개인 획 = 찍기
```

- 단위는 폰트 단위입니다. 기준선 y=0, 대문자 높이 10, 소문자 높이 7, 아래로 내려가는 부분(g, j, p, q, y)은 -3까지입니다.
- 글자 폭은 다음 글자까지의 거리입니다. 자간은 따로 더해집니다.
- 고친 뒤에는 `python3 preview.py --text "..."`로 모양을 확인하세요.

## 한계와 주의

- 캔버스가 수평이라고 가정합니다(z 하나).
- 정확한 직사각형이 아닌 캔버스는 보간 때문에 글자가 조금 비뚤어질 수 있습니다.
- 이 코드는 PC 시뮬레이션(`preview.py`)으로만 검증했습니다. **실제 로봇에서는 반드시 허공 리허설부터** 하세요.

## 참고 (DRL 명령)

| 명령 | 용도 |
|---|---|
| [`movel`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/movel) | 직선 이동(`vel`, `acc`, `radius`, `ref=DR_BASE`). SW V2.8 이상에서는 블렌딩 반경이 이동 거리의 절반을 넘으면 자동으로 줄어듭니다. |
| `posx` | 작업 공간 자세 `(x, y, z, rx, ry, rz)` |
| [`get_current_posx`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/get_current_posx-ref) | 현재 TCP 자세 `(posx, sol)` |
| [`tp_popup`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/tp_popup-message-pm_type-dr_pm_message-button_type) | TP 팝업. 256 byte 이내, 줄바꿈 불가 |
| [`tp_log`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/tp_log-message) | TP 로그 |
| [`exit`](https://manual.doosanrobotics.com/en/programming-manual/3.2.0/publish/exit) | 프로그램 정지 |

위 명령은 모두 2.x/3.x 공통의 기본 DRL 명령입니다. 링크는 온라인 Programming Manual(3.2.0)이며, V2.10 전용 페이지는 공개 매뉴얼에서 찾지 못했습니다.
