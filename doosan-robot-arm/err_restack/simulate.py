#!/usr/bin/env python3
"""restack_blocks.py (DRL Custom Code) 를 PC 에서 미리 실행해 검사하는 시뮬레이터.

gripper_init.py(그리퍼 초기화 Custom Code 개선판, --init 으로 원본 지정 가능)와 restack_blocks.py 를
실제 순서대로 그대로 실행합니다.
DRL 함수는 가짜(stub)로 바꾸고, RH-P12-RN(A) 그리퍼는 Modbus RTU 장치 수준으로 흉내 냅니다.
  - CRC16 검사, FC03/FC06/FC16 처리, 실제 레지스터 맵(Present Position 은 하위/상위 워드)
  - 플랜지 시리얼처럼 응답을 여러 조각으로 나눠 돌려주고, 읽지 않은 응답은 버퍼에 남김
  - 손가락은 75 mm/s 로 움직이다 블록에 닿으면 멈추고, 그 위치값을 돌려줌
로봇에 올리는 파일이 아닙니다.

사용 예:
    python3 simulate.py                       # 쌓인 순서 6가지를 모두 실행
    python3 simulate.py --order SLM           # 위에서부터 SMALL, LARGE, MEDIUM 순서 하나만 자세히
    python3 simulate.py --calibrate           # 보정 모드 (위에서부터 S, M, L)
    python3 simulate.py --order MSL --pos-bias 60   # 보정값이 크게 틀린 경우
    python3 simulate.py --order SML --missing SMALL # 블록 하나가 없는 경우 (빈손)
    python3 simulate.py --order SML --mute-after 2  # 초기화 뒤 그리퍼 응답이 끊긴 경우
    python3 simulate.py --order SML --mute-after 0  # 그리퍼가 처음부터 응답하지 않는 경우
    python3 simulate.py --order SML --mute-after 0 --init gripper_init_original.py  # 원본: 끝나지 않음
"""
import argparse
import ast
import itertools
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ("LARGE", "MEDIUM", "SMALL")
LETTER = {"L": "LARGE", "M": "MEDIUM", "S": "SMALL"}
DRL_CONSTANTS = {
    "DR_BASE": 0, "DR_TOOL": 1, "DR_WORLD": 2,
    "DR_PM_MESSAGE": 0, "DR_PM_WARNING": 1, "DR_PM_ALARM": 2,
    "DR_MV_MOD_ABS": 0, "DR_MV_MOD_REL": 1,
    "DR_EIGHTBITS": 8, "DR_PARITY_NONE": "N", "DR_STOPBITS_ONE": 1,
}
EPS = 0.01
FINGER_W = 10.0       # 손가락 두께 가정 [mm] (경고 판단용)
MAX_DROP = 5.0        # 이보다 높이서 놓으면 경고 [mm]
SAMPLE_MM = 2.0       # 이동 구간 충돌 검사 간격 [mm]
FULL_CLOSE = 740      # 완전 닫힘 위치값
STROKE_MM = 106.0     # 최대 벌림 폭
PULSE_PER_S = FULL_CLOSE / STROKE_MM * 75.0   # 최대 닫힘 속도 75 mm/s


class DrlExit(BaseException):
    """DRL exit() 이 호출됨. DRL 코드의 except Exception 에 잡히지 않도록 BaseException."""


class SimTimeout(BaseException):
    """시뮬레이션 시간이 한도를 넘음 (끝나지 않는 대기 의심)."""


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return bytes([crc & 0xFF, crc >> 8])


def seg_time(d, v, a):
    """사다리꼴 속도 프로파일 기준 대략적인 이동 시간 [s]."""
    if d <= 0:
        return 0.0
    if d >= v * v / a:
        return d / v + v / a
    return 2.0 * math.sqrt(d / a)


class FakeGripper(object):
    """RH-P12-RN(A) Modbus RTU 흉내: 레지스터 + 손가락 움직임 + 블록 접촉."""

    def __init__(self, sim, bias, noise, rng, mute_after, swap_read):
        self.sim = sim
        self.bias = bias
        self.noise = noise
        self.rng = rng
        self.mute_after = mute_after  # 이 개수만큼 요청을 처리한 뒤로는 응답하지 않음 (통신 끊김 시험)
        self.swap_read = swap_read    # Present Position 을 상위 워드 먼저 돌려줌 (워드 순서 판별 시험)
        self.n_frames = 0
        self.torque = 0
        self.goal_current = 0
        self.goal = 0
        self.pos = 0.0
        self.moving = False
        self.stop_at = None   # 닫는 중 블록에 닿을 위치
        self.contact = None   # 닿을 블록
        self.stalled = False  # 블록을 잡고 멈춘 상태

    def true_pos(self, width):
        return FULL_CLOSE * (1.0 - width / STROKE_MM) + self.bias + self.rng.randint(-self.noise, self.noise)

    def set_goal(self, goal):
        self.goal = goal
        if goal < self.pos - 0.5:          # 여는 방향: 잡고 있던 블록을 놓음
            if self.stalled:
                self.sim.release()
            self.stalled, self.stop_at, self.contact = False, None, None
        elif goal > self.pos + 0.5:        # 닫는 방향: 손가락 사이 블록에 닿으면 멈춤
            b = self.sim.block_between_fingers()
            if b is not None and self.true_pos(b["size"]) < goal:
                self.stop_at, self.contact = self.true_pos(b["size"]), b
        self.moving = abs(self.goal - self.pos) > 0.5

    def update(self, dt):
        if not self.moving or dt <= 0:
            return
        target = self.stop_at if self.stop_at is not None else self.goal
        step = PULSE_PER_S * dt
        if abs(target - self.pos) <= step:
            self.pos = float(target)
            self.moving = False
            if self.stop_at is not None:
                self.stalled = True
                self.sim.attach(self.contact)
        else:
            self.pos += step if target > self.pos else -step

    def register(self, addr):
        pos = int(round(self.pos))
        current = self.goal_current if self.stalled else (150 if self.moving else 0)
        if addr == 285:
            return 1 if self.moving else 0         # 하위 바이트 Moving, 상위 바이트 Moving Status(0)
        if addr == 287:
            return current & 0xFFFF
        if addr in (290, 291):
            lo, hi = pos & 0xFFFF, (pos >> 16) & 0xFFFF
            if self.swap_read:
                lo, hi = hi, lo
            return lo if addr == 290 else hi
        if addr == 256:
            return self.torque
        if addr == 275:
            return self.goal_current & 0xFFFF
        return 0

    def handle(self, frame):
        """요청 프레임 -> 응답 프레임 (CRC 가 틀리면 응답 없음)."""
        if len(frame) < 4 or crc16(frame[:-2]) != frame[-2:]:
            self.sim.add_error("CRC 가 틀린 요청 프레임: %s" % frame.hex())
            return b""
        self.n_frames += 1
        if self.mute_after is not None and self.n_frames > self.mute_after:
            return b""
        sid, fc = frame[0], frame[1]
        if sid != 1:
            return b""
        if fc == 3:
            start, cnt = int.from_bytes(frame[2:4], "big"), int.from_bytes(frame[4:6], "big")
            body = b"".join(self.register(start + i).to_bytes(2, "big") for i in range(cnt))
            resp = bytes([sid, 3, 2 * cnt]) + body
        elif fc == 6:
            addr, val = int.from_bytes(frame[2:4], "big"), int.from_bytes(frame[4:6], "big")
            if addr == 256:
                self.torque = val
            elif addr == 275:
                self.goal_current = val - 65536 if val >= 32768 else val
            resp = frame[:6]
        elif fc == 16:
            start, cnt = int.from_bytes(frame[2:4], "big"), int.from_bytes(frame[4:6], "big")
            vals = [int.from_bytes(frame[7 + 2 * i:9 + 2 * i], "big") for i in range(cnt)]
            if start == 282 and cnt == 2:
                goal = vals[0] + (vals[1] << 16)        # Goal Position: 하위 워드 먼저
                if not 0 <= goal <= 1150:
                    return self.exception(sid, fc, 3)
                if self.torque != 1:
                    self.sim.add_error("Torque Enable 전에 Goal Position 을 씀")
                self.set_goal(goal)
            resp = frame[:6]
        else:
            return self.exception(sid, fc, 1)
        return resp + crc16(resp)

    def exception(self, sid, fc, code):
        resp = bytes([sid, fc | 0x80, code])
        return resp + crc16(resp)


class Sim(object):
    def __init__(self, order, missing, start_pose, bias, noise, seed, mute_after=None, swap_read=False,
                 time_limit=1800.0):
        self.order = order            # 위 -> 아래 블록 이름
        self.missing = missing
        self.start_pose = start_pose
        self.time_limit = time_limit
        self.rng = random.Random(seed)
        self.gripper = FakeGripper(self, bias, noise, self.rng, mute_after, swap_read)
        self.rx = bytearray()         # 플랜지 시리얼 수신 버퍼
        self.serial_open = False
        self.pose = None
        self.blocks = None
        self.held = None              # (block, TCP z - 블록 바닥)
        self.events, self.errors, self.warnings, self.logs = [], [], [], []
        self.time = 0.0
        self.n_moves = 0
        self.ns = None

    # ---- 초기 상태 ---------------------------------------------------------
    def init_world(self):
        ns = self.ns
        self.floor = float(ns["FLOOR_Z"])
        self.stroke = float(ns["GRIPPER_STROKE_MM"])
        tx, ty = map(float, ns["TOWER_POS"])
        sizes = {n: float(ns["BLOCK_SIZE_" + n]) for n in NAMES}
        self.blocks = []
        bottom = self.floor
        for name in reversed(self.order):   # 아래부터 쌓음
            if name == self.missing:
                continue
            self.blocks.append({"name": name, "size": sizes[name], "x": tx, "y": ty, "bottom": bottom})
            bottom += sizes[name]
        if self.start_pose is not None:
            self.pose = list(self.start_pose)
        else:   # 기본: 탑 위 300mm, 그리퍼가 아래를 향한 자세
            self.pose = [tx - 100.0, ty, self.floor + 300.0, 0.0, 180.0, 0.0]

    def find(self, name):
        return [b for b in self.blocks if b["name"] == name][0]

    def advance(self, dt):
        self.time += dt
        self.gripper.update(dt)
        if self.time > self.time_limit:
            raise SimTimeout()

    # ---- 그리퍼와 블록 ----------------------------------------------------------
    def block_between_fingers(self):
        p = self.pose
        for b in self.blocks:
            if self.held and b is self.held[0]:
                continue
            if math.dist(p[:2], (b["x"], b["y"])) < 2.0 and b["bottom"] + EPS < p[2] < b["bottom"] + b["size"] - EPS:
                return b
        return None

    def attach(self, b):
        self.held = (b, self.pose[2] - b["bottom"])
        self.events.append(("잡음", b["name"], list(self.pose), "위치값 %d" % round(self.gripper.pos)))

    def release(self):
        b, off = self.held
        self.held = None
        p = self.pose
        b["x"], b["y"], b["bottom"] = p[0], p[1], p[2] - off
        support, below = self.floor, "지면"
        for c in self.blocks:
            if c is b:
                continue
            top = c["bottom"] + c["size"]
            d = math.dist((b["x"], b["y"]), (c["x"], c["y"]))
            if d < (b["size"] + c["size"]) / 2.0 - EPS and top <= b["bottom"] + EPS and top > support:
                support, below = top, c["name"]
        drop = b["bottom"] - support
        if drop < -EPS:
            self.add_error("%s 블록을 아래 블록 속으로 놓음 (%.1f mm)" % (b["name"], drop))
        elif drop > MAX_DROP:
            self.add_warning("%s 블록을 %.1f mm 높이에서 놓음" % (b["name"], drop))
        b["bottom"] = support
        self.events.append(("놓음", b["name"], list(p), "낙하 %.1f mm, 아래: %s" % (drop, below)))

    # ---- DRL stub ------------------------------------------------------------
    def namespace(self):
        ns = dict(DRL_CONSTANTS)
        sim = self

        def posx(*v):
            if len(v) != 6:
                raise TypeError("posx() needs 6 values, got %d" % len(v))
            return [float(a) for a in v]

        def movel(pos, vel=None, acc=None, time=None, radius=None, ref=None,
                  mod=DRL_CONSTANTS["DR_MV_MOD_ABS"], **_):
            if ref != DRL_CONSTANTS["DR_BASE"] or mod != DRL_CONSTANTS["DR_MV_MOD_ABS"]:
                raise ValueError("simulate expects absolute moves in DR_BASE")
            sim.move(list(pos), float(vel), float(acc))
            return 0

        def get_current_posx(ref=DRL_CONSTANTS["DR_BASE"], ori_type=None):
            if sim.blocks is None:
                sim.init_world()
            return list(sim.pose), 2

        def tp_popup(message, pm_type=0, button_type=0):
            if "\n" in message or len(message.encode()) > 256:
                sim.add_error("tp_popup 메시지가 256 byte 를 넘거나 줄바꿈 포함")
            kind = {0: "MESSAGE", 1: "WARNING", 2: "ALARM"}.get(pm_type, str(pm_type))
            sim.logs.append("[tp_popup %s] %s" % (kind, message))
            return 0

        def tp_log(message):
            sim.logs.append("[tp_log] %s" % message)
            return 0

        def drl_exit():
            raise DrlExit()

        def wait(t):
            sim.advance(float(t))
            return 0

        def flange_serial_open(**_):
            sim.serial_open = True
            return 0

        def flange_serial_close():
            sim.serial_open = False
            return 0

        def flange_serial_write(data):
            if type(data) is not bytes:
                raise TypeError("flange_serial_write() needs bytes")
            if not sim.serial_open:
                sim.add_error("열리지 않은 플랜지 시리얼에 씀")
                return -1
            sim.advance(0.005)
            sim.rx += sim.gripper.handle(data)
            return 0

        def flange_serial_read(timeout=None):
            if not sim.rx:
                sim.advance(float(timeout or 0.0))
                return -1, None
            n = sim.rng.randint(1, len(sim.rx))      # 응답이 나뉘어 오는 상황 재현
            chunk = bytes(sim.rx[:n])
            del sim.rx[:n]
            sim.advance(0.005)
            return n, chunk

        def modbus_send_make(data):
            return bytes(data) + crc16(bytes(data))

        def modbus_recv_check(data):
            return len(data) >= 3 and crc16(bytes(data[:-2])) == bytes(data[-2:])

        ns.update(posx=posx, movel=movel, get_current_posx=get_current_posx, tp_popup=tp_popup,
                  tp_log=tp_log, exit=drl_exit, wait=wait, d2r=math.radians, sin=math.sin, cos=math.cos,
                  flange_serial_open=flange_serial_open, flange_serial_close=flange_serial_close,
                  flange_serial_write=flange_serial_write, flange_serial_read=flange_serial_read,
                  modbus_send_make=modbus_send_make, modbus_recv_check=modbus_recv_check)
        return ns

    # ---- 모션 / 충돌 검사 ----------------------------------------------------
    def move(self, dst, vel, acc):
        src = self.pose
        d = math.dist(src[:3], dst[:3])
        n = max(1, int(math.ceil(d / SAMPLE_MM)))
        dt = seg_time(d, vel, acc) / n
        for i in range(1, n + 1):
            t = float(i) / n
            p = [src[k] + (dst[k] - src[k]) * t for k in range(3)]
            self.pose = p + list(dst[3:])
            self.advance(dt)
            self.check_point(p)
        self.pose = list(dst)
        self.n_moves += 1

    def check_point(self, p):
        if p[2] < self.floor - EPS:
            self.add_error("손가락 끝이 지면 아래로 내려감: z=%.1f" % p[2])
        held = self.held[0] if self.held else None
        opened = self.gripper.goal <= 50
        if held:
            hb = p[2] - self.held[1]
            for b in self.blocks:
                if b is held:
                    continue
                d = math.dist(p[:2], (b["x"], b["y"]))
                z_overlap = min(hb + held["size"], b["bottom"] + b["size"]) - max(hb, b["bottom"])
                if d < (held["size"] + b["size"]) / 2.0 - EPS and z_overlap > EPS:
                    self.add_error("운반 중인 %s 블록이 %s 블록과 충돌" % (held["name"], b["name"]))
        for b in self.blocks:
            if b is held or p[2] >= b["bottom"] + b["size"] - EPS:
                continue
            d = math.dist(p[:2], (b["x"], b["y"]))
            if opened and d < 2.0:
                continue   # 열린 손가락이 블록을 양옆에서 감싸며 내려가는 정상 동작
            if not opened and d < b["size"] / 2.0:
                self.add_error("닫힌 손가락이 %s 블록 위로 내려가 부딪힘" % b["name"])
                continue
            reach = (self.stroke / 2.0 if opened else (held["size"] / 2.0 if held else 0.0)) + FINGER_W
            if d < reach + b["size"] * 0.7072:
                self.add_warning("손가락이 %s 블록과 가까움 (중심 거리 %.0f mm)" % (b["name"], d))

    def add_error(self, msg):
        if msg not in self.errors:
            self.errors.append(msg)

    def add_warning(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)


def strip_call(path, func):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    tree.body = [n for n in tree.body
                 if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                         and getattr(n.value.func, "id", "") == func)]
    return compile(tree, path, "exec")


def run(order, overrides, args):
    """gripper_init.py -> restack_blocks.py 순서로 실행. 반환: (sim, 정상 종료 여부)."""
    sim = Sim(order, args.missing, args.start, args.pos_bias, args.pos_noise, args.seed, args.mute_after,
              args.swap_read_words, args.time_limit)
    ns = sim.namespace()
    sim.ns = ns
    try:
        with open(args.init, encoding="utf-8") as f:
            exec(compile(f.read(), args.init, "exec"), ns)
        exec(strip_call(args.drl, "rb_main"), ns)
        ns.update(overrides)
        ns["rb_main"]()
    except DrlExit:
        return sim, False
    except SimTimeout:
        sim.add_error("시뮬레이션 시간 %.0f s 초과: 끝나지 않는 대기 (초기화 루프 등)" % sim.time_limit)
        return sim, False
    return sim, True


def check_tower(sim):
    """최종 탑: TOWER_POS 에 LARGE, MEDIUM, SMALL 순서로 중심이 맞게 쌓였는지."""
    tx, ty = map(float, sim.ns["TOWER_POS"])
    bottom = sim.floor
    for name in NAMES:
        b = sim.find(name)
        if math.dist((b["x"], b["y"]), (tx, ty)) > 0.5:
            sim.add_error("%s 블록이 탑 위치에 없음: (%.1f, %.1f)" % (name, b["x"], b["y"]))
        if abs(b["bottom"] - bottom) > EPS:
            sim.add_error("%s 블록 바닥 높이 %.1f (기대값 %.1f)" % (name, b["bottom"], bottom))
        bottom += b["size"]
    if sim.held:
        sim.add_error("끝났는데 블록을 잡고 있음")


def report(sim, ok, verbose):
    ns = sim.ns
    dry = float(ns.get("DRY_RUN_OFFSET_Z", 0.0)) > 0
    if ok and not dry and not sim.missing:
        check_tower(sim)
    grips = sum(1 for e in sim.events if e[0] == "잡음")
    if verbose:
        print("\n".join(sim.logs))
        print("\n=== 블록 이동 ===")
        for i, (what, name, p, note) in enumerate(sim.events, 1):
            print("%2d. %-6s %-4s @ (%7.1f, %7.1f, %6.1f)  %s" % (i, name, what, p[0], p[1], p[2], note))
        if ok and not dry and not sim.missing:
            print("\n=== 최종 탑 ===")
            for name in NAMES:
                b = sim.find(name)
                print("%-6s %5.1f mm  바닥 z %6.1f  윗면 z %6.1f  중심 (%.1f, %.1f)"
                      % (name, b["size"], b["bottom"], b["bottom"] + b["size"], b["x"], b["y"]))
        print("\nmovel %d회, 잡기 %d회, 예상 시간(대략) %.0f s" % (sim.n_moves, grips, sim.time))
        for w in sim.warnings:
            print("[경고] " + w)
        for e in sim.errors:
            print("[오류] " + e)
        if not ok and any("ALARM" in m for m in sim.logs):
            print("=> DRL 이 알람으로 멈췄습니다 (위 ALARM 메시지 참고).")
        elif not sim.errors and not sim.warnings:
            print("검사: 충돌 없음, 탑이 LARGE -> MEDIUM -> SMALL 순서로 쌓임")
    return grips


def main():
    ap = argparse.ArgumentParser(description="restack_blocks.py 시뮬레이션")
    ap.add_argument("--drl", default=os.path.join(HERE, "restack_blocks.py"))
    ap.add_argument("--init", default=os.path.join(HERE, "gripper_init.py"))
    ap.add_argument("--order", help="처음 쌓인 순서, 위에서부터 L/M/S 세 글자 (예: SLM). 생략하면 6가지 모두")
    ap.add_argument("--calibrate", action="store_true", help="보정 모드 (순서는 위에서부터 SML 로 고정)")
    ap.add_argument("--missing", choices=NAMES, help="이 블록이 없는 상황 (빈손 시험)")
    ap.add_argument("--pos-bias", type=int, default=0, help="실제 그리퍼 위치값을 이만큼 어긋나게 함 [pulse]")
    ap.add_argument("--pos-noise", type=int, default=3, help="위치값 측정 잡음 ± [pulse]")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--mute-after", type=int, metavar="N",
                    help="그리퍼가 요청 N개를 처리한 뒤 응답을 멈춤 (초기화 요청은 2개)")
    ap.add_argument("--swap-read-words", action="store_true",
                    help="그리퍼가 Present Position 을 상위 워드 먼저 돌려줌 (워드 순서 자동 판별 시험)")
    ap.add_argument("--time-limit", type=float, default=1800.0,
                    help="시뮬레이션 시간 한도 [s]. 넘으면 끝나지 않는 대기로 판단")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="설정 덮어쓰기 (Python 리터럴), 여러 번 사용 가능")
    ap.add_argument("--start", nargs=6, type=float, metavar=("X", "Y", "Z", "RX", "RY", "RZ"))
    args = ap.parse_args()

    overrides = {}
    for item in args.set:
        name, _, value = item.partition("=")
        overrides[name.strip()] = ast.literal_eval(value.strip())
    if args.calibrate:
        overrides["CALIBRATION_MODE"] = True
        args.order = args.order or "SML"

    if args.order:
        order = [LETTER[c] for c in args.order.upper()]
        if sorted(order) != sorted(NAMES):
            ap.error("--order 는 L, M, S 를 한 번씩 써야 합니다")
        sim, ok = run(order, overrides, args)
        report(sim, ok, True)
        return 0 if ok and not sim.errors else 1

    print("처음 순서(위->아래)   잡기  결과")
    bad = 0
    for perm in itertools.permutations("LMS"):
        order = [LETTER[c] for c in perm]
        sim, ok = run(order, overrides, args)
        grips = report(sim, ok, False)
        alarm = [m for m in sim.logs if "ALARM" in m]
        status = "OK" if ok and not sim.errors else "실패"
        if status != "OK":
            bad += 1
        detail = (alarm[0] if alarm else "") + " ".join(sim.errors[:2])
        print("%-20s %3d   %s %s%s" % (" ".join(perm), grips, status,
                                       "(경고 %d) " % len(sim.warnings) if sim.warnings else "", detail))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
