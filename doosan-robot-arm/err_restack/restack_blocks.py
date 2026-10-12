# -*- coding: utf-8 -*-
# =============================================================================
#  restack_blocks.py - 두산 로봇팔 블록 3개 다시 쌓기 Custom Code (DRL)
#
#  대상    : Doosan Robotics 컨트롤러 S/W DRSUP V2.10.3
#            (Task Writer / Task Builder 의 Custom Code 에 넣어 실행)
#  그리퍼  : ROBOTIS RH-P12-RN(A), 플랜지 시리얼 Modbus RTU
#            그리퍼 초기화 Custom Code 가 먼저 실행되어 있어야 합니다.
#            (modbus_fc03(), modbus_fc16(), g_slaveid, gripper_move() 를 사용합니다)
#  동작    : TOWER_POS 에 크기가 다른 정육면체 3개가 무작위 순서로 쌓여 있을 때,
#            위에서부터 잡아 그리퍼가 멈춘 위치(Present Position)로 크기를 판별하고,
#            같은 자리에 아래부터 큰 것 -> 중간 -> 작은 것 순으로 다시 쌓습니다.
#            맨 아래가 이미 가장 큰 블록이면 그대로 둡니다.
#  전제    : - 그리퍼가 아래(-z)를 향하고, 손가락이 블록 면과 나란한 자세로 시작합니다.
#            - 탑은 TOWER_POS 에 중심이 맞게 쌓여 있습니다.
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

# 탑 위치: 처음 탑과 다시 쌓을 탑이 같은 자리. 탑 중심의 (x, y) [mm, DR_BASE]
TOWER_POS = (500.0, -150.0)

# 블록 판별 보정값: 각 블록을 잡았을 때의 그리퍼 Present Position [pulse]
#   0 = 완전 열림, 740 = 완전 닫힘이라 블록이 클수록 값이 작습니다.
#   None 이면 스트로크에 비례한다고 보고 추정합니다 (부정확할 수 있음).
#   CALIBRATION_MODE = True 로 한 번 실행하면 실제 값을 측정해 TP 에 알려 줍니다.
GRIP_POS_LARGE  = None
GRIP_POS_MEDIUM = None
GRIP_POS_SMALL  = None


# -----------------------------------------------------------------------------
#  [2] 고급 설정 - 필요할 때만 수정
# -----------------------------------------------------------------------------
CALIBRATION_MODE = False  # True: 아래부터 LARGE, MEDIUM, SMALL 로 쌓아 두고 실행 -> 보정값 측정

BUFFER_DIRECTION_DEG = 90.0  # 임시 자리 3곳을 탑 옆에 일렬로 둘 방향 [deg, 베이스 +X 에서 반시계]. 90 = +Y
BUFFER_SPACING       = None  # 임시 자리 간격 [mm]. None = 블록 크기와 그리퍼 폭으로 자동 계산
GRIP_POS_TOLERANCE   = None  # 판별 허용 오차 [pulse]. None = 이웃 보정값 간격의 40%

GRIP_DEPTH       = 20.0  # 블록 윗면에서 손가락 끝까지 내려가 잡는 깊이 [mm] (손가락 길이 안에서)
                         #   손가락 끝은 항상 블록 아래 면보다 5mm 이상 위에 둡니다.
                         #   크기를 모르는 맨 위 블록은 SMALL 기준으로 제한하고, 판별 뒤 더 깊이 잡을
                         #   수 있으면 다시 잡습니다.
PLACE_GAP        = 1.0   # 놓을 때 블록 바닥과 아래 면 사이 간격 [mm] (이만큼 떨어뜨림)
APPROACH_DIST    = 30.0  # 집기/놓기 위치 위 이 거리부터는 저속으로 이동 [mm]
TRAVEL_CLEARANCE = 30.0  # 이동 높이 여유: 운반 중인 블록 바닥과 탑 꼭대기 사이 [mm]
TRAVEL_Z         = None  # 이동 높이 [mm]. None = 자동 계산, 숫자 = 지정 (자동 최소값보다 낮으면 알람)
TOOL_ORI         = None  # 그리퍼 자세 (rx, ry, rz) [deg]. None = 시작 자세 방향 사용
DRY_RUN_OFFSET_Z = 0.0   # 리허설용. 예) 50.0 -> 50mm 위에서 그리퍼를 닫지 않고 경로만 확인

VEL_TRAVEL   = 200.0     # 이동 속도 [mm/s]
VEL_APPROACH = 30.0      # 집기/놓기 직전 저속 [mm/s]
ACC          = 400.0     # 가속도 [mm/s^2]

GRIPPER_OPEN_POS    = 0      # gripper_move() 열림 값
GRIPPER_CLOSE_POS   = 740    # gripper_move() 완전 닫힘 값 (블록에 닿으면 전류 제한으로 멈춤)
GRIPPER_STROKE_MM   = 106.0  # 그리퍼 최대 벌림 폭 [mm] (RH-P12-RN(A) Rev.1: 106, Rev.0: 109)
GRIP_SETTLE_TIMEOUT = 3.0    # 그리퍼가 멈출 때까지 기다리는 최대 시간 [s]

CONFIRM_BEFORE_START = True  # 시작 전 TP 팝업으로 내용 확인 (Resume 을 눌러야 진행)
RETURN_TO_START      = True  # 완료 후 시작 XY 위치로 복귀


# =============================================================================
#  [3] 내부 구현 - 수정하지 않아도 됩니다
# =============================================================================
RB_NAMES = ("LARGE", "MEDIUM", "SMALL")   # 블록 번호 0, 1, 2
RB_MIN_BLOCK = 5.0        # 최소 블록 크기 [mm]
RB_FINGER_MARGIN = 6.0    # 가장 큰 블록 + 이 값 <= 그리퍼 최대 벌림 폭 [mm]
RB_FINGER_W = 10.0        # 손가락 두께 가정 [mm] (임시 자리 간격 계산용)
RB_SPACING_MARGIN = 15.0  # 임시 자리 간격 여유 [mm]
RB_EMPTY_MARGIN = 20      # 위치값이 완전 닫힘 - 이 값 이상이면 빈손 [pulse]
RB_SETTLE_STEP = 2        # 연속 두 번 읽은 위치 차이가 이 값 이하면 멈춘 것으로 봄 [pulse]
RB_POS_RANGE = (-100, 1150)  # 정상 Present Position 범위 [pulse] (Max Position Limit 1150)
RB_SUPPORT_CLEAR = 5.0    # 손가락 끝과 블록 아래 면(받치는 면) 사이 최소 여유 [mm]
RB_REGRIP_MIN = 2.0       # 판별 뒤 이만큼 이상 더 깊이 잡을 수 있으면 다시 잡음 [mm]
RB_STATE = {"swap_logged": False}
RB_REG_START = 285        # Modbus 40286(Moving) ~ 40292(Present Position 상위 워드)
RB_REG_COUNT = 7
RB_CAL_ORDER = (2, 1, 0)  # 보정 모드에서 가정하는 순서 (위 -> 아래): SMALL, MEDIUM, LARGE
RB_DRY_ORDER = (2, 0, 1)  # 리허설에서 가정하는 순서 (위 -> 아래): 임시 자리 3곳을 모두 쓰는 경우
RB_EPS = 0.01


def rb_fail(msg):
    """오류를 TP 알람 팝업으로 알리고 프로그램을 멈춥니다."""
    tp_popup("[restack_blocks] " + msg, DR_PM_ALARM, 1)
    exit()
    raise RuntimeError(msg)  # exit() 가 즉시 멈추지 않는 경우에도 모션이 나가지 않도록


def rb_num(name, value, lo, hi):
    try:
        v = float(value)
    except Exception:
        rb_fail(name + " must be a number.")
    if v < lo or v > hi:
        rb_fail("{0}={1} is out of range [{2}, {3}].".format(name, value, lo, hi))
    return v


def rb_xy(name, p):
    try:
        if len(p) != 2:
            raise ValueError()
        return (float(p[0]), float(p[1]))
    except Exception:
        rb_fail(name + " must be (x, y) in mm.")


def rb_plan():
    """설정을 검사하고 높이, 임시 자리, 판별 기준을 계산합니다."""
    floor = rb_num("FLOOR_Z", FLOOR_Z, -2000.0, 2000.0)
    stroke = rb_num("GRIPPER_STROKE_MM", GRIPPER_STROKE_MM, 10.0, 300.0)
    close = int(rb_num("GRIPPER_CLOSE_POS", GRIPPER_CLOSE_POS, 1.0, 5000.0))
    sizes = [rb_num("BLOCK_SIZE_LARGE", BLOCK_SIZE_LARGE, RB_MIN_BLOCK, 1000.0),
             rb_num("BLOCK_SIZE_MEDIUM", BLOCK_SIZE_MEDIUM, RB_MIN_BLOCK, 1000.0),
             rb_num("BLOCK_SIZE_SMALL", BLOCK_SIZE_SMALL, RB_MIN_BLOCK, 1000.0)]
    if not (sizes[0] > sizes[1] > sizes[2]):
        rb_fail("Block sizes must be LARGE > MEDIUM > SMALL.")
    if sizes[0] + RB_FINGER_MARGIN > stroke:
        rb_fail("LARGE block {0:.0f} mm is too big for gripper stroke {1:.0f} mm.".format(sizes[0], stroke))

    for name, value, lo, hi in (
        ("GRIP_DEPTH", GRIP_DEPTH, 1.0, 200.0),
        ("PLACE_GAP", PLACE_GAP, 0.0, 10.0),
        ("APPROACH_DIST", APPROACH_DIST, 5.0, 200.0),
        ("TRAVEL_CLEARANCE", TRAVEL_CLEARANCE, 10.0, 500.0),
        ("DRY_RUN_OFFSET_Z", DRY_RUN_OFFSET_Z, 0.0, 300.0),
        ("VEL_TRAVEL", VEL_TRAVEL, 1.0, 1000.0),
        ("VEL_APPROACH", VEL_APPROACH, 1.0, 250.0),
        ("ACC", ACC, 10.0, 5000.0),
        ("GRIP_SETTLE_TIMEOUT", GRIP_SETTLE_TIMEOUT, 0.5, 30.0),
        ("BUFFER_DIRECTION_DEG", BUFFER_DIRECTION_DEG, -360.0, 360.0),
    ):
        rb_num(name, value, lo, hi)
    if TOOL_ORI is not None:
        try:
            if len(TOOL_ORI) != 3:
                raise ValueError()
            [float(v) for v in TOOL_ORI]
        except Exception:
            rb_fail("TOOL_ORI must be None or (rx, ry, rz) in deg.")
    tower = rb_xy("TOWER_POS", TOWER_POS)

    # 판별 기준 위치값: 지정값 또는 스트로크 비례 추정값
    given = (GRIP_POS_LARGE, GRIP_POS_MEDIUM, GRIP_POS_SMALL)
    estimated = all(v is None for v in given)
    if estimated:
        refs = [int(round(close * (1.0 - s / stroke))) for s in sizes]
    elif any(v is None for v in given):
        rb_fail("Set all of GRIP_POS_LARGE/MEDIUM/SMALL, or leave all None.")
    else:
        refs = [int(rb_num("GRIP_POS_" + RB_NAMES[i], given[i], 0.0, float(close))) for i in range(3)]
    empty_pos = close - RB_EMPTY_MARGIN
    if not CALIBRATION_MODE and not (refs[0] < refs[1] < refs[2] < empty_pos):
        rb_fail("GRIP_POS must be LARGE < MEDIUM < SMALL < {0}. Got {1}/{2}/{3}.".format(
            empty_pos, refs[0], refs[1], refs[2]))
    gap = min(refs[1] - refs[0], refs[2] - refs[1])
    if GRIP_POS_TOLERANCE is None:
        tol = max(1, int(gap * 0.4))
    else:
        tol = int(rb_num("GRIP_POS_TOLERANCE", GRIP_POS_TOLERANCE, 1.0, 1000.0))
        if not CALIBRATION_MODE and tol * 2 >= gap:
            rb_fail("GRIP_POS_TOLERANCE {0} is too large. Must be < {1}.".format(tol, (gap + 1) // 2))

    # 임시 자리: 탑에서 BUFFER_DIRECTION_DEG 방향으로 간격만큼씩 3곳
    #   간격 = 열린 손가락 바깥쪽 + 이웃 블록(가장 큰 블록 기준) 대각선 절반 + 여유
    min_spacing = stroke / 2.0 + RB_FINGER_W + sizes[0] * 0.7072
    if BUFFER_SPACING is None:
        spacing = 5.0 * int((min_spacing + RB_SPACING_MARGIN) / 5.0 + 0.999)
    else:
        spacing = rb_num("BUFFER_SPACING", BUFFER_SPACING, 1.0, 2000.0)
        if spacing < min_spacing:
            rb_fail("BUFFER_SPACING {0:.0f} mm is too small. Min is {1:.0f} mm.".format(spacing, min_spacing))
    a = d2r(float(BUFFER_DIRECTION_DEG))
    slots = [(tower[0] + (k + 1) * spacing * cos(a), tower[1] + (k + 1) * spacing * sin(a)) for k in range(3)]

    # 손가락 끝 깊이: 크기를 모르는 블록은 SMALL 이어도 아래 면보다 RB_SUPPORT_CLEAR 위에 오도록 제한
    depth_unknown = min(GRIP_DEPTH, sizes[2] - RB_SUPPORT_CLEAR)
    if depth_unknown < 3.0:
        rb_fail("SMALL block {0:.0f} mm is too small to grip safely (min {1:.0f} mm).".format(
            sizes[2], RB_SUPPORT_CLEAR + 3.0))
    off = DRY_RUN_OFFSET_Z
    total = sum(sizes)
    z_travel = floor + total + (sizes[0] - depth_unknown) + TRAVEL_CLEARANCE + off
    if TRAVEL_Z is not None:
        tz = rb_num("TRAVEL_Z", TRAVEL_Z, -2000.0, 3000.0)
        if tz < z_travel - RB_EPS:
            rb_fail("TRAVEL_Z {0:.1f} is too low. Min is {1:.1f}.".format(tz, z_travel))
        z_travel = tz

    return {"floor": floor, "sizes": sizes, "tower": tower, "slots": slots, "spacing": spacing,
            "refs": refs, "tol": tol, "estimated": estimated, "empty_pos": empty_pos,
            "depth_unknown": depth_unknown, "off": off, "z_travel": z_travel}


def rb_depth(size):
    """크기를 아는 블록을 잡는 깊이: 윗면에서 GRIP_DEPTH, 단 아래 면보다 RB_SUPPORT_CLEAR 위까지."""
    return min(GRIP_DEPTH, size - RB_SUPPORT_CLEAR)


def rb_require_gripper():
    """그리퍼 초기화 Custom Code 의 함수/변수가 있는지 확인합니다."""
    try:
        gripper_move
        modbus_fc03
        modbus_fc16
        g_slaveid
    except NameError:
        rb_fail("Gripper init custom code (gripper_move, modbus_fc03) must run first.")


# ---- 그리퍼 상태 읽기 (Modbus FC03) ------------------------------------------
def rb_flush():
    """gripper_move() 가 읽지 않고 남긴 응답 등, 수신 버퍼에 남은 바이트를 버립니다."""
    for i in range(20):
        res, data = flange_serial_read(0.05)
        if res is None or res <= 0:
            return


def rb_read_status():
    """그리퍼 상태를 읽습니다. 반환: (moving, current_mA, position) 또는 실패 시 None."""
    need = 5 + 2 * RB_REG_COUNT  # slave id, fc, byte count, data, CRC 2
    for attempt in range(3):
        rb_flush()
        flange_serial_write(modbus_fc03(RB_REG_START, RB_REG_COUNT))
        buf = b""
        for i in range(10):  # 플랜지 시리얼은 응답이 나뉘어 올 수 있어 모일 때까지 읽음
            res, data = flange_serial_read(0.1)
            if res is not None and res > 0:
                buf += data
            if len(buf) >= need:
                break
        if (len(buf) >= need and buf[0] == g_slaveid and buf[1] == 3 and buf[2] == 2 * RB_REG_COUNT
                and modbus_recv_check(buf[:need])):
            regs = [int.from_bytes(buf[3 + 2 * i:5 + 2 * i], byteorder='big') for i in range(RB_REG_COUNT)]
            moving = regs[0] & 0xFF                      # 40286 하위 바이트: Moving
            current = regs[2] - 65536 if regs[2] >= 32768 else regs[2]   # 40288 Present Current
            position = rb_position(regs[5], regs[6])     # 40291, 40292: Present Position
            if position is not None:
                return moving, current, position
        wait(0.05)
    return None


def rb_int32(lo, hi):
    v = lo + (hi << 16)
    return v - 2 ** 32 if v >= 2 ** 31 else v


def rb_position(w1, w2):
    """Present Position 레지스터 두 개 -> 위치값. 정상 범위를 벗어나면 None.

    gripper_move() 와 같은 순서(첫 레지스터 = 하위 워드)로 먼저 해석합니다.
    범위(-100 ~ 1150)를 벗어나면 워드 순서가 반대인 것으로 보고 다시 해석합니다.
    값이 16비트 안이라 한쪽 워드는 0(또는 음수면 0xFFFF)이므로 두 순서를 구분할 수 있습니다.
    """
    v = rb_int32(w1, w2)
    if RB_POS_RANGE[0] <= v <= RB_POS_RANGE[1]:
        return v
    v = rb_int32(w2, w1)
    if RB_POS_RANGE[0] <= v <= RB_POS_RANGE[1]:
        if not RB_STATE["swap_logged"]:
            tp_log("restack: Present Position word order is reversed (high word first)")
            RB_STATE["swap_logged"] = True
        return v
    tp_log("restack: invalid Present Position registers {0}, {1}".format(w1, w2))
    return None


def rb_settle(xy, z_travel, ori):
    """그리퍼가 멈출 때까지 상태를 읽습니다. 반환: (moving, current, position)."""
    last = None
    steps = int(GRIP_SETTLE_TIMEOUT / 0.1) + 1
    for i in range(steps):
        st = rb_read_status()
        if st is None:
            rb_abort("No valid Modbus response from gripper.", xy, z_travel, ori)
        if last is not None and abs(st[2] - last[2]) <= RB_SETTLE_STEP:
            return st
        last = st
        wait(0.1)
    rb_abort("Gripper did not settle within {0:.1f} s.".format(GRIP_SETTLE_TIMEOUT), xy, z_travel, ori)


def rb_abort(msg, xy, z_travel, ori):
    """그리퍼를 열고 수직으로 이동 높이까지 올라간 뒤 알람으로 멈춥니다.

    통신이 끊긴 상황일 수 있으므로, 여는 명령은 gripper_move() 대신 응답 확인 없이 보냅니다.
    (gripper_move() 와 같은 명령: Goal Position 282-283 = [열림 값, 0])
    """
    flange_serial_write(modbus_fc16(282, 2, [GRIPPER_OPEN_POS, 0]))
    wait(1.0)
    rb_move(xy, z_travel, ori, VEL_APPROACH)
    rb_fail(msg)


# ---- 모션 ----------------------------------------------------------------------
def rb_move(xy, z, ori, vel):
    movel(posx(xy[0], xy[1], z, ori[0], ori[1], ori[2]), vel=vel, acc=ACC, ref=DR_BASE)


def rb_descend(xy, z, z_travel, ori):
    """이동 높이에서 목표 z 로: APPROACH_DIST 위까지는 빠르게, 나머지는 천천히."""
    z_app = min(z + APPROACH_DIST, z_travel)
    if z_app < z_travel - RB_EPS:
        rb_move(xy, z_app, ori, VEL_TRAVEL)
    rb_move(xy, z, ori, VEL_APPROACH)


def rb_ascend(xy, z, z_travel, ori):
    """목표 z 에서 이동 높이로: APPROACH_DIST 까지는 천천히, 나머지는 빠르게."""
    z_app = min(z + APPROACH_DIST, z_travel)
    rb_move(xy, z_app, ori, VEL_APPROACH)
    if z_app < z_travel - RB_EPS:
        rb_move(xy, z_travel, ori, VEL_TRAVEL)


# ---- 잡기 / 놓기 ------------------------------------------------------------------
def rb_close(p, xy, z_travel, ori):
    """그리퍼를 닫고 멈출 때까지 기다립니다. 반환: (위치값, 전류). 빈손이면 알람."""
    gripper_move(GRIPPER_CLOSE_POS)
    moving, current, pos = rb_settle(xy, z_travel, ori)
    if pos >= p["empty_pos"]:
        rb_abort("Empty grip (pos {0}). No block between fingers.".format(pos), xy, z_travel, ori)
    return pos, current


def rb_open(xy, z_travel, ori):
    gripper_move(GRIPPER_OPEN_POS)
    rb_settle(xy, z_travel, ori)


def rb_identify(p, pos, current, xy, ori, expected, assumed, used, cal):
    """측정한 위치값으로 블록 번호를 정합니다. 보정 모드에서는 가정한 번호를 쓰고 값을 기록합니다."""
    z_travel = p["z_travel"]
    if CALIBRATION_MODE:
        ident = assumed if expected is None else expected
        if ident not in cal:
            cal[ident] = pos
        tp_log("restack: calibration {0} pos {1} current {2}".format(RB_NAMES[ident], pos, current))
        return ident
    ident = min(range(3), key=lambda i: abs(pos - p["refs"][i]))
    tp_log("restack: grip pos {0} current {1} -> {2} (ref {3})".format(
        pos, current, RB_NAMES[ident], p["refs"][ident]))
    if abs(pos - p["refs"][ident]) > p["tol"]:
        rb_abort("Grip pos {0} matches no block (refs {1}/{2}/{3}, tol {4}).".format(
            pos, p["refs"][0], p["refs"][1], p["refs"][2], p["tol"]), xy, z_travel, ori)
    if expected is not None and ident != expected:
        rb_abort("Expected {0} but measured {1} (pos {2}).".format(
            RB_NAMES[expected], RB_NAMES[ident], pos), xy, z_travel, ori)
    if expected is None and ident in used:
        rb_abort("{0} identified twice (pos {1}). Check GRIP_POS values.".format(
            RB_NAMES[ident], pos), xy, z_travel, ori)
    return ident


def rb_grip(p, xy, top_z, depth, ori, expected, assumed, used, cal, release=False):
    """윗면이 top_z 인 블록을 depth 깊이로 잡아 판별한 뒤 이동 높이로 올라옵니다.

    expected: 이미 아는 블록이면 그 번호 (측정값이 다르면 알람), 모르면 None
    assumed : 보정 모드/리허설에서 가정하는 번호
    used    : 이미 판별된 블록 번호 목록 (같은 블록이 두 번 나오면 알람)
    cal     : 보정 모드 측정값 저장용 dict
    release : True 면 측정만 하고 그 자리에서 놓은 뒤 올라옴
    반환    : (블록 번호, 최종으로 잡은 깊이)
    """
    z_travel = p["z_travel"]
    rb_move(xy, z_travel, ori, VEL_TRAVEL)
    rb_descend(xy, top_z - depth, z_travel, ori)
    if p["off"] > 0:
        ident = assumed if expected is None else expected
        tp_log("restack: dry run - assume {0}".format(RB_NAMES[ident]))
    else:
        pos, current = rb_close(p, xy, z_travel, ori)
        ident = rb_identify(p, pos, current, xy, ori, expected, assumed, used, cal)
        want = rb_depth(p["sizes"][ident])
        if release:
            rb_open(xy, z_travel, ori)
        elif expected is None and want > depth + RB_REGRIP_MIN:
            # 크기를 몰라 얕게 잡은 블록: 크기를 알았으니 더 깊이 다시 잡음 (아래 블록과는 여유 유지)
            tp_log("restack: regrip {0} at depth {1:.0f} mm (was {2:.0f})".format(RB_NAMES[ident], want, depth))
            rb_open(xy, z_travel, ori)
            rb_move(xy, top_z - want, ori, VEL_APPROACH)
            pos, current = rb_close(p, xy, z_travel, ori)
            rb_identify(p, pos, current, xy, ori, ident, ident, used, cal)
            depth = want
    rb_ascend(xy, top_z - depth, z_travel, ori)
    return ident, depth


def rb_place(p, xy, z, ori):
    """xy 위 z 로 내려가 그리퍼를 열고 이동 높이로 올라옵니다."""
    z_travel = p["z_travel"]
    rb_move(xy, z_travel, ori, VEL_TRAVEL)
    rb_descend(xy, z, z_travel, ori)
    if p["off"] <= 0:
        gripper_move(GRIPPER_OPEN_POS)
        rb_settle(xy, z_travel, ori)
    rb_ascend(xy, z, z_travel, ori)


def rb_main():
    p = rb_plan()
    rb_require_gripper()
    floor, sizes, tower, slots, off = p["floor"], p["sizes"], p["tower"], p["slots"], p["off"]
    z_travel = p["z_travel"]
    dry = off > 0

    cur, sol = get_current_posx(ref=DR_BASE)
    start = [float(cur[i]) for i in range(6)]
    ori = start[3:6] if TOOL_ORI is None else [float(v) for v in TOOL_ORI]

    # 움직이기 전에 그리퍼 통신부터 확인
    if rb_read_status() is None:
        rb_fail("No valid Modbus response from gripper. Check the gripper init custom code.")

    if CONFIRM_BEFORE_START:
        mode = " / CALIBRATION" if CALIBRATION_MODE else ""
        mode += " / DRY RUN (no grip)" if dry else ""
        tp_popup("Restack L/M/S {0:.0f}/{1:.0f}/{2:.0f} mm at ({3:.1f}, {4:.1f}) / grip pos {5}/{6}/{7}{8} "
                 "tol {9} / buffer {10:.0f} mm @ {11:.0f} deg / travel z {12:.1f}{13}. Press Resume to start.".format(
                     sizes[0], sizes[1], sizes[2], tower[0], tower[1], p["refs"][0], p["refs"][1],
                     p["refs"][2], " (est.)" if p["estimated"] else "", p["tol"], p["spacing"],
                     float(BUFFER_DIRECTION_DEG), z_travel, mode),
                 DR_PM_MESSAGE)

    # 시작 위치에서 수직으로 이동 높이까지 올린 뒤 그리퍼를 엽니다
    if start[2] < z_travel - RB_EPS:
        rb_move(start[:2], z_travel, start[3:6], VEL_TRAVEL)
    gripper_move(GRIPPER_OPEN_POS)
    rb_settle(start[:2], z_travel, start[3:6])

    order = RB_CAL_ORDER if CALIBRATION_MODE else RB_DRY_ORDER  # 보정 모드/리허설에서만 사용
    cal = {}
    top = floor + sum(sizes)   # 쌓인 순서와 상관없이 탑 꼭대기 높이는 같음
    du = p["depth_unknown"]
    slot_of = {}
    removed = []

    # 놓는 높이 = 아래 면 + (블록 크기 - 잡은 깊이) + PLACE_GAP

    # 1) 위의 두 블록: 잡아서 크기를 판별하고 임시 자리에 내려놓음
    for k in range(2):
        tp_log("restack: pick top block {0}/2".format(k + 1))
        ident, d = rb_grip(p, tower, top + off, du, ori, None, order[k], removed, cal)
        rb_place(p, slots[k], floor + (sizes[ident] - d) + PLACE_GAP + off, ori)
        top -= sizes[ident]
        slot_of[ident] = k
        removed.append(ident)

    # 2) 맨 아래 블록: 남은 하나로 정해짐. LARGE 면 그대로, 아니면 임시 자리로
    bottom = [i for i in range(3) if i not in removed][0]
    tp_log("restack: bottom is {0}".format(RB_NAMES[bottom]))
    if bottom == 0:
        if CALIBRATION_MODE and not dry:  # 보정 모드: 제자리에서 잡아 측정만 하고 놓음
            rb_grip(p, tower, top + off, du, ori, 0, 0, removed, cal, release=True)
        build = [1, 2]
        surface = floor + sizes[0]
    else:
        size = sizes[bottom]
        ident, d = rb_grip(p, tower, floor + size + off, rb_depth(size), ori, bottom, bottom, removed, cal)
        rb_place(p, slots[2], floor + (size - d) + PLACE_GAP + off, ori)
        slot_of[bottom] = 2
        build = [0, 1, 2]
        surface = floor

    # 3) 큰 것부터 탑 자리에 다시 쌓음 (잡을 때마다 측정값으로 맞는 블록인지 확인)
    for ident in build:
        tp_log("restack: stack {0}".format(RB_NAMES[ident]))
        size = sizes[ident]
        slot = slots[slot_of[ident]]
        ident, d = rb_grip(p, slot, floor + size + off, rb_depth(size), ori, ident, ident, removed, cal)
        rb_place(p, tower, surface + (size - d) + PLACE_GAP + off, ori)
        surface += size

    if RETURN_TO_START:
        rb_move(start[:2], max(start[2], z_travel), start[3:6], VEL_TRAVEL)

    if CALIBRATION_MODE and not dry:
        msg = "Calibration: GRIP_POS_LARGE = {0}, GRIP_POS_MEDIUM = {1}, GRIP_POS_SMALL = {2}.".format(
            cal.get(0), cal.get(1), cal.get(2))
        if not (cal.get(0) < cal.get(1) < cal.get(2)):
            msg += " WARNING: not LARGE < MEDIUM < SMALL. Check the stack order."
        tp_log("restack: " + msg)
        tp_popup(msg + " Copy these to the settings.", DR_PM_MESSAGE)
    tp_log("restack: done")


# =============================================================================
#  [4] 실행
# =============================================================================
rb_main()
