# -*- coding: utf-8 -*-
# =============================================================================
#  stack_blocks.py - 두산 로봇팔 정육면체 블록 3개 탑 쌓기 Custom Code (DRL)
#
#  대상    : Doosan Robotics 컨트롤러 S/W DRSUP V2.10.3
#            (Task Writer / Task Builder 의 Custom Code 에 넣어 실행)
#  그리퍼  : ROBOTIS RH-P12-RN(A)
#            그리퍼 초기화 Custom Code 가 먼저 실행되어 gripper_move(위치) 를
#            쓸 수 있어야 합니다 (0 = 열림, 740 = 완전 닫힘).
#  동작    : 크기가 다른 정육면체 3개를 큰 것 -> 중간 -> 작은 것 순으로
#            TOWER_POS 에 쌓습니다.
#  전제    : - 그리퍼가 아래(-z)를 향하고, 손가락이 블록 면과 나란한 자세로 시작합니다.
#              (TOOL_ORI = None 이면 시작 자세의 방향을 그대로 씁니다)
#            - 블록은 평평한 지면에 놓여 있고, 회전 방향이 그리퍼 손가락과 맞춰져 있습니다.
#  좌표    : 베이스 좌표계(DR_BASE), 단위 mm.
# =============================================================================


# =============================================================================
#  [1] 사용자 설정 - 이 블록만 수정하세요
# =============================================================================

# 블록 크기: 정육면체 한 변 길이 [mm]  (LARGE > MEDIUM > SMALL)
BLOCK_SIZE_LARGE  = 60.0
BLOCK_SIZE_MEDIUM = 45.0
BLOCK_SIZE_SMALL  = 30.0

# 그리퍼를 고려한 지면 z [mm, DR_BASE 절대값]
#   그리퍼를 연 상태에서 손가락 끝이 지면에 막 닿을 때의 TCP z.
#   예시값입니다. 반드시 실제 값으로 바꾸세요.
FLOOR_Z = 20.0

# 블록 위치: 블록 중심의 (x, y) [mm, DR_BASE]
BLOCK_POS_LARGE  = (450.0,  200.0)
BLOCK_POS_MEDIUM = (450.0,   50.0)
BLOCK_POS_SMALL  = (450.0, -100.0)

# 탑을 쌓을 위치: 탑 중심의 (x, y) [mm, DR_BASE]
TOWER_POS = (600.0, 50.0)


# -----------------------------------------------------------------------------
#  [2] 고급 설정 - 필요할 때만 수정
# -----------------------------------------------------------------------------
GRIP_DEPTH       = 20.0  # 블록 윗면에서 손가락 끝까지 내려가 잡는 깊이 [mm] (블록 높이 절반까지만)
PLACE_GAP        = 1.0   # 놓을 때 블록 바닥과 아래 면 사이 간격 [mm] (이만큼 떨어뜨림)
APPROACH_DIST    = 30.0  # 집기/놓기 위치 위 이 거리부터는 저속으로 이동 [mm]
TRAVEL_CLEARANCE = 30.0  # 이동 높이 여유: 운반 중인 블록 바닥과 가장 높은 장애물 사이 [mm]
TRAVEL_Z         = None  # 이동 높이 [mm]. None = 자동 계산, 숫자 = 지정 (자동 최소값보다 낮으면 알람)
TOOL_ORI         = None  # 그리퍼 자세 (rx, ry, rz) [deg]. None = 시작 자세 방향 사용
DRY_RUN_OFFSET_Z = 0.0   # 리허설용. 예) 50.0 -> 모든 동작을 50mm 위에서 하고 그리퍼는 닫지 않음

VEL_TRAVEL   = 200.0     # 이동 속도 [mm/s]
VEL_APPROACH = 30.0      # 집기/놓기 직전 저속 [mm/s]
ACC          = 400.0     # 가속도 [mm/s^2]

GRIPPER_OPEN_POS  = 0       # gripper_move() 열림 값
GRIPPER_CLOSE_POS = 740     # gripper_move() 완전 닫힘 값 (블록에 닿으면 전류 제한으로 멈춤)
GRIPPER_WAIT_SEC  = 1.5     # 그리퍼 동작 대기 [s] (최대 닫힘 속도 75 mm/s)
GRIPPER_STROKE_MM = 106.0   # 그리퍼 최대 벌림 폭 [mm] (RH-P12-RN(A) Rev.1: 106, Rev.0: 109)

CONFIRM_BEFORE_START = True  # 시작 전 TP 팝업으로 내용 확인 (Resume 을 눌러야 진행)
RETURN_TO_START      = True  # 완료 후 시작 XY 위치로 복귀


# =============================================================================
#  [3] 내부 구현 - 수정하지 않아도 됩니다
# =============================================================================
BS_NAMES = ("LARGE", "MEDIUM", "SMALL")
BS_MIN_BLOCK = 5.0       # 최소 블록 크기 [mm]
BS_FINGER_MARGIN = 6.0   # 가장 큰 블록 + 이 값 <= 그리퍼 최대 벌림 폭 [mm]
BS_EPS = 0.01


def bs_fail(msg):
    """오류를 TP 알람 팝업으로 알리고 프로그램을 멈춥니다."""
    tp_popup("[stack_blocks] " + msg, DR_PM_ALARM, 1)
    exit()
    raise RuntimeError(msg)  # exit() 가 즉시 멈추지 않는 경우에도 모션이 나가지 않도록


def bs_num(name, value, lo, hi):
    try:
        v = float(value)
    except Exception:
        bs_fail(name + " must be a number.")
    if v < lo or v > hi:
        bs_fail("{0}={1} is out of range [{2}, {3}].".format(name, value, lo, hi))
    return v


def bs_xy(name, p):
    try:
        if len(p) != 2:
            raise ValueError()
        return (float(p[0]), float(p[1]))
    except Exception:
        bs_fail(name + " must be (x, y) in mm.")


def bs_dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def bs_grip_height(size):
    """블록 바닥에서 손가락 끝까지 높이. 윗면에서 GRIP_DEPTH (최대 블록 절반) 내려가 잡습니다."""
    return size - min(GRIP_DEPTH, size / 2.0)


def bs_plan():
    """설정을 검사하고 블록별 집기/놓기 높이와 이동 높이를 계산합니다.

    반환: (단계 목록, 탑 위치, 이동 높이)
          단계 = {"name", "size", "pick": (x, y), "pick_z", "place_z"}
    """
    floor = bs_num("FLOOR_Z", FLOOR_Z, -2000.0, 2000.0)
    stroke = bs_num("GRIPPER_STROKE_MM", GRIPPER_STROKE_MM, 10.0, 300.0)
    sizes = [bs_num("BLOCK_SIZE_LARGE", BLOCK_SIZE_LARGE, BS_MIN_BLOCK, 1000.0),
             bs_num("BLOCK_SIZE_MEDIUM", BLOCK_SIZE_MEDIUM, BS_MIN_BLOCK, 1000.0),
             bs_num("BLOCK_SIZE_SMALL", BLOCK_SIZE_SMALL, BS_MIN_BLOCK, 1000.0)]
    if not (sizes[0] > sizes[1] > sizes[2]):
        bs_fail("Block sizes must be LARGE > MEDIUM > SMALL.")
    if sizes[0] + BS_FINGER_MARGIN > stroke:
        bs_fail("LARGE block {0:.0f} mm is too big for gripper stroke {1:.0f} mm.".format(sizes[0], stroke))

    for name, value, lo, hi in (
        ("GRIP_DEPTH", GRIP_DEPTH, 1.0, 200.0),
        ("PLACE_GAP", PLACE_GAP, 0.0, 10.0),
        ("APPROACH_DIST", APPROACH_DIST, 5.0, 200.0),
        ("TRAVEL_CLEARANCE", TRAVEL_CLEARANCE, 10.0, 500.0),
        ("DRY_RUN_OFFSET_Z", DRY_RUN_OFFSET_Z, 0.0, 300.0),
        ("VEL_TRAVEL", VEL_TRAVEL, 1.0, 1000.0),
        ("VEL_APPROACH", VEL_APPROACH, 1.0, 250.0),
        ("ACC", ACC, 10.0, 5000.0),
        ("GRIPPER_WAIT_SEC", GRIPPER_WAIT_SEC, 0.0, 10.0),
    ):
        bs_num(name, value, lo, hi)
    if TOOL_ORI is not None:
        try:
            if len(TOOL_ORI) != 3:
                raise ValueError()
            [float(v) for v in TOOL_ORI]
        except Exception:
            bs_fail("TOOL_ORI must be None or (rx, ry, rz) in deg.")

    pos = [bs_xy("BLOCK_POS_LARGE", BLOCK_POS_LARGE),
           bs_xy("BLOCK_POS_MEDIUM", BLOCK_POS_MEDIUM),
           bs_xy("BLOCK_POS_SMALL", BLOCK_POS_SMALL)]
    tower = bs_xy("TOWER_POS", TOWER_POS)

    # 동시에 바닥에 있는 것끼리 겹치면 안 됩니다:
    #   처음 놓인 블록끼리, 그리고 탑(맨 아래 LARGE) vs 아직 옮기지 않은 MEDIUM / SMALL
    pairs = [(0, pos[0], 1, pos[1]), (0, pos[0], 2, pos[2]), (1, pos[1], 2, pos[2]),
             (0, tower, 1, pos[1]), (0, tower, 2, pos[2])]
    for k, (ia, pa, ib, pb) in enumerate(pairs):
        need = (sizes[ia] + sizes[ib]) / 2.0
        d = bs_dist(pa, pb)
        if d < need:
            a = "TOWER" if k >= 3 else BS_NAMES[ia]
            bs_fail("{0} and {1} overlap: distance {2:.0f} mm < {3:.0f} mm.".format(a, BS_NAMES[ib], d, need))

    # 이동 높이: 운반 중인 블록 바닥이 완성된 탑 높이보다 TRAVEL_CLEARANCE 이상 위
    off = DRY_RUN_OFFSET_Z
    z_travel = floor + sum(sizes) + bs_grip_height(sizes[0]) + TRAVEL_CLEARANCE + off
    if TRAVEL_Z is not None:
        tz = bs_num("TRAVEL_Z", TRAVEL_Z, -2000.0, 3000.0)
        if tz < z_travel - BS_EPS:
            bs_fail("TRAVEL_Z {0:.1f} is too low. Min is {1:.1f}.".format(tz, z_travel))
        z_travel = tz

    steps = []
    bottom = floor  # 다음 블록이 놓일 면의 높이
    for i in range(3):
        g = bs_grip_height(sizes[i])
        steps.append({"name": BS_NAMES[i], "size": sizes[i], "pick": pos[i],
                      "pick_z": floor + g + off,
                      "place_z": bottom + g + PLACE_GAP + off})
        bottom += sizes[i]
    return steps, tower, z_travel


def bs_require_gripper():
    """그리퍼 초기화 Custom Code 의 gripper_move() 가 있는지 확인합니다."""
    try:
        gripper_move
    except NameError:
        bs_fail("gripper_move() is not defined. Run the gripper init custom code first.")


def bs_gripper(pos):
    gripper_move(pos)
    wait(GRIPPER_WAIT_SEC)


def bs_move(xy, z, ori, vel):
    movel(posx(xy[0], xy[1], z, ori[0], ori[1], ori[2]), vel=vel, acc=ACC, ref=DR_BASE)


def bs_descend(xy, z, z_travel, ori):
    """이동 높이에서 목표 z 로: APPROACH_DIST 위까지는 빠르게, 나머지는 천천히."""
    z_app = min(z + APPROACH_DIST, z_travel)
    if z_app < z_travel - BS_EPS:
        bs_move(xy, z_app, ori, VEL_TRAVEL)
    bs_move(xy, z, ori, VEL_APPROACH)


def bs_ascend(xy, z, z_travel, ori):
    """목표 z 에서 이동 높이로: APPROACH_DIST 까지는 천천히, 나머지는 빠르게."""
    z_app = min(z + APPROACH_DIST, z_travel)
    bs_move(xy, z_app, ori, VEL_APPROACH)
    if z_app < z_travel - BS_EPS:
        bs_move(xy, z_travel, ori, VEL_TRAVEL)


def bs_main():
    steps, tower, z_travel = bs_plan()
    bs_require_gripper()

    cur, sol = get_current_posx(ref=DR_BASE)
    start = [float(cur[i]) for i in range(6)]
    ori = start[3:6] if TOOL_ORI is None else [float(v) for v in TOOL_ORI]
    dry = DRY_RUN_OFFSET_Z > 0

    if CONFIRM_BEFORE_START:
        tp_popup("Stack L/M/S {0:.0f}/{1:.0f}/{2:.0f} mm at ({3:.1f}, {4:.1f}) / floor z {5:.1f} / "
                 "travel z {6:.1f}{7}. Press Resume to start.".format(
                     steps[0]["size"], steps[1]["size"], steps[2]["size"], tower[0], tower[1],
                     float(FLOOR_Z), z_travel, " / DRY RUN (no grip)" if dry else ""),
                 DR_PM_MESSAGE)

    # 시작 위치에서 수직으로 이동 높이까지 올린 뒤 그리퍼를 엽니다
    if start[2] < z_travel - BS_EPS:
        bs_move(start[:2], z_travel, start[3:6], VEL_TRAVEL)
    bs_gripper(GRIPPER_OPEN_POS)

    for st in steps:
        tp_log("stack_blocks: pick {0} ({1:.0f} mm)".format(st["name"], st["size"]))
        bs_move(st["pick"], z_travel, ori, VEL_TRAVEL)
        bs_descend(st["pick"], st["pick_z"], z_travel, ori)
        if dry:
            tp_log("stack_blocks: dry run - gripper stays open")
        else:
            bs_gripper(GRIPPER_CLOSE_POS)
        bs_ascend(st["pick"], st["pick_z"], z_travel, ori)

        tp_log("stack_blocks: place {0}".format(st["name"]))
        bs_move(tower, z_travel, ori, VEL_TRAVEL)
        bs_descend(tower, st["place_z"], z_travel, ori)
        if not dry:
            bs_gripper(GRIPPER_OPEN_POS)
        bs_ascend(tower, st["place_z"], z_travel, ori)

    if RETURN_TO_START:
        bs_move(start[:2], max(start[2], z_travel), start[3:6], VEL_TRAVEL)
    tp_log("stack_blocks: done")


# =============================================================================
#  [4] 실행
# =============================================================================
bs_main()
