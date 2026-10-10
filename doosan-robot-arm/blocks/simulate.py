#!/usr/bin/env python3
"""stack_blocks.py (DRL Custom Code) 를 PC 에서 미리 실행해 동작 순서와 충돌을 검사하는 도구.

DRL 함수와 gripper_move() 를 가짜(stub)로 바꿔 stack_blocks.py 를 그대로 실행합니다.
블록을 실제로 잡고 옮기는 것처럼 상태를 추적해서 결과를 검사합니다.
로봇에 올리는 파일이 아닙니다.

사용 예:
    python3 simulate.py
    python3 simulate.py --set BLOCK_SIZE_LARGE=80 --set "TOWER_POS=(600, 0)"
    python3 simulate.py --start 400 0 300 0 180 0
"""
import argparse
import ast
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DRL_CONSTANTS = {
    "DR_BASE": 0, "DR_TOOL": 1, "DR_WORLD": 2,
    "DR_PM_MESSAGE": 0, "DR_PM_WARNING": 1, "DR_PM_ALARM": 2,
    "DR_MV_MOD_ABS": 0, "DR_MV_MOD_REL": 1,
}
EPS = 0.01
FINGER_W = 10.0      # 손가락 두께 가정 [mm] (경고 판단용)
MAX_DROP = 5.0       # 이보다 높이서 놓으면 경고 [mm]
SAMPLE_MM = 2.0      # 이동 구간 충돌 검사 간격 [mm]


class DrlExit(BaseException):
    """DRL exit() 이 호출됨. DRL 코드의 except Exception 에 잡히지 않도록 BaseException."""


class Sim(object):
    def __init__(self, start_pose, with_gripper):
        self.start_pose = start_pose
        self.with_gripper = with_gripper
        self.pose = None
        self.blocks = None   # [{"name", "size", "x", "y", "bottom"}]
        self.held = None     # (block, 손가락 끝 - 블록 바닥)
        self.opened = None   # 그리퍼 상태: True 열림 / False 닫힘 / None 모름
        self.events = []     # 출력용 동작 기록
        self.errors = []
        self.warnings = []
        self.time = 0.0
        self.n_moves = 0
        self.ns = None

    # ---- 초기 상태 ---------------------------------------------------------
    def init_world(self):
        ns = self.ns
        self.floor = float(ns["FLOOR_Z"])
        self.stroke = float(ns["GRIPPER_STROKE_MM"])
        self.blocks = []
        for name in ("LARGE", "MEDIUM", "SMALL"):
            x, y = ns["BLOCK_POS_" + name]
            self.blocks.append({"name": name, "size": float(ns["BLOCK_SIZE_" + name]),
                                "x": float(x), "y": float(y), "bottom": self.floor})
        if self.start_pose is not None:
            self.pose = list(self.start_pose)
        else:  # 기본: 블록과 탑 위치의 가운데, 지면 300mm 위, 그리퍼가 아래를 향한 자세
            pts = [ns["BLOCK_POS_" + n] for n in ("LARGE", "MEDIUM", "SMALL")] + [ns["TOWER_POS"]]
            self.pose = [sum(p[0] for p in pts) / 4.0, sum(p[1] for p in pts) / 4.0,
                         self.floor + 300.0, 0.0, 180.0, 0.0]

    def find(self, name):
        return [b for b in self.blocks if b["name"] == name][0]

    # ---- DRL stub ----------------------------------------------------------
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
            kind = {0: "MESSAGE", 1: "WARNING", 2: "ALARM"}.get(pm_type, str(pm_type))
            print("[tp_popup %s] %s" % (kind, message))
            return 0

        def tp_log(message):
            print("[tp_log] %s" % message)
            return 0

        def drl_exit():
            raise DrlExit()

        def wait(t):
            sim.time += float(t)
            return 0

        ns.update(posx=posx, movel=movel, get_current_posx=get_current_posx,
                  tp_popup=tp_popup, tp_log=tp_log, exit=drl_exit, wait=wait)
        if self.with_gripper:
            ns["gripper_move"] = self.gripper_move
        return ns

    # ---- 모션 / 충돌 검사 ----------------------------------------------------
    def move(self, dst, vel, acc):
        src = self.pose
        d = math.dist(src[:3], dst[:3])
        self.time += seg_time(d, vel, acc)
        self.n_moves += 1
        n = max(1, int(math.ceil(d / SAMPLE_MM)))
        for i in range(1, n + 1):
            t = float(i) / n
            p = [src[k] + (dst[k] - src[k]) * t for k in range(3)]
            self.check_point(p)
        self.pose = list(dst)

    def check_point(self, p):
        if p[2] < self.floor - EPS:
            self.add_error("손가락 끝이 지면 아래로 내려감: z=%.1f (FLOOR_Z %.1f)" % (p[2], self.floor))
        held = self.held[0] if self.held else None
        if held:  # 운반 중인 블록이 다른 블록과 겹치는지
            hb = p[2] - self.held[1]
            if hb < self.floor - EPS:
                self.add_error("%s 블록이 지면을 파고듦" % held["name"])
            for b in self.blocks:
                if b is held:
                    continue
                d = math.dist(p[:2], (b["x"], b["y"]))
                z_overlap = min(hb + held["size"], b["bottom"] + b["size"]) - max(hb, b["bottom"])
                if d < (held["size"] + b["size"]) / 2.0 - EPS and z_overlap > EPS:
                    self.add_error("운반 중인 %s 블록이 %s 블록과 충돌" % (held["name"], b["name"]))
        for b in self.blocks:  # 손가락이 다른 블록과 부딪히는지
            if b is held or p[2] >= b["bottom"] + b["size"] - EPS:
                continue
            d = math.dist(p[:2], (b["x"], b["y"]))
            if self.opened and d < 2.0:
                continue  # 열린 손가락이 블록을 양옆에서 감싸며 내려가는 정상 동작
            if not self.opened and d < b["size"] / 2.0:
                self.add_error("닫힌 손가락이 %s 블록 위로 내려가 부딪힘" % b["name"])
                continue
            if self.opened:
                reach = self.stroke / 2.0 + FINGER_W
            else:
                reach = (held["size"] / 2.0 if held else 0.0) + FINGER_W
            if d < reach + b["size"] * 0.7072:
                self.add_warning("손가락이 %s 블록과 가까움 (중심 거리 %.0f mm): 간격을 넓히세요"
                                 % (b["name"], d))

    # ---- 그리퍼 --------------------------------------------------------------
    def gripper_move(self, value):
        ns = self.ns
        p = self.pose
        if value == ns["GRIPPER_CLOSE_POS"]:
            self.opened = False
            target = None
            for b in self.blocks:
                inside = b["bottom"] + EPS < p[2] < b["bottom"] + b["size"] - EPS
                if math.dist(p[:2], (b["x"], b["y"])) < 2.0 and inside:
                    target = b
            if target is None:
                self.add_error("빈 그리퍼를 닫음 @ (%.1f, %.1f, %.1f)" % tuple(p[:3]))
                self.events.append(("그리퍼 닫기 (빈손)", p, ""))
                return 0
            self.held = (target, p[2] - target["bottom"])
            self.events.append(("%s 잡기" % target["name"], p,
                                "손가락 끝: 블록 바닥 +%.1f mm (윗면 -%.1f mm)"
                                % (self.held[1], target["size"] - self.held[1])))
        elif value == ns["GRIPPER_OPEN_POS"]:
            self.opened = True
            if self.held is None:
                self.events.append(("그리퍼 열기", p, ""))
                return 0
            b, off = self.held
            self.held = None
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
            if drop > MAX_DROP:
                self.add_warning("%s 블록을 %.1f mm 높이에서 놓음" % (b["name"], drop))
            b["bottom"] = support
            self.events.append(("%s 놓기" % b["name"], p, "낙하 %.1f mm, 아래: %s" % (drop, below)))
        else:
            self.add_warning("알 수 없는 gripper_move(%r)" % (value,))
        return 0

    def add_error(self, msg):
        if msg not in self.errors:
            self.errors.append(msg)

    def add_warning(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)


def seg_time(d, v, a):
    """사다리꼴 속도 프로파일 기준 대략적인 이동 시간 [s]."""
    if d <= 0:
        return 0.0
    if d >= v * v / a:
        return d / v + v / a
    return 2.0 * math.sqrt(d / a)


def run(path, overrides, start_pose, with_gripper):
    """마지막 bs_main() 호출을 떼고 실행 -> 설정 덮어쓰기 -> bs_main() 실행."""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    tree.body = [n for n in tree.body
                 if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                         and getattr(n.value.func, "id", "") == "bs_main")]
    sim = Sim(start_pose, with_gripper)
    ns = sim.namespace()
    sim.ns = ns
    exec(compile(tree, path, "exec"), ns)
    ns.update(overrides)
    try:
        ns["bs_main"]()
    except DrlExit:
        return sim, False
    return sim, True


def check_tower(sim):
    """최종 탑: TOWER_POS 에 LARGE, MEDIUM, SMALL 순서로 중심이 맞게 쌓였는지."""
    ns = sim.ns
    tx, ty = ns["TOWER_POS"]
    bottom = sim.floor
    for name in ("LARGE", "MEDIUM", "SMALL"):
        b = sim.find(name)
        if math.dist((b["x"], b["y"]), (tx, ty)) > 0.5:
            sim.add_error("%s 블록이 탑 위치에 없음: (%.1f, %.1f)" % (name, b["x"], b["y"]))
        if abs(b["bottom"] - bottom) > EPS:
            sim.add_error("%s 블록 바닥 높이 %.1f (기대값 %.1f)" % (name, b["bottom"], bottom))
        bottom += b["size"]


def main():
    ap = argparse.ArgumentParser(description="stack_blocks.py 동작 시뮬레이션")
    ap.add_argument("drl", nargs="?", default=os.path.join(HERE, "stack_blocks.py"))
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="설정 덮어쓰기 (Python 리터럴), 여러 번 사용 가능")
    ap.add_argument("--start", nargs=6, type=float, metavar=("X", "Y", "Z", "RX", "RY", "RZ"),
                    help="가상 시작 자세 (기본: 블록/탑 위치의 가운데, FLOOR_Z+300, 0 180 0)")
    ap.add_argument("--no-gripper", action="store_true",
                    help="gripper_move() 가 정의되지 않은 상황을 시험")
    args = ap.parse_args()

    overrides = {}
    for item in args.set:
        name, _, value = item.partition("=")
        overrides[name.strip()] = ast.literal_eval(value.strip())

    sim, ok = run(args.drl, overrides, args.start, not args.no_gripper)
    if not ok:
        print("\n=> 설정 오류로 DRL 이 exit() 했습니다. 위 ALARM 메시지를 확인하세요.")
        return 1

    ns = sim.ns
    dry = float(ns["DRY_RUN_OFFSET_Z"]) > 0
    print("\n=== 그리퍼 동작 순서 ===")
    for i, (what, p, note) in enumerate(sim.events, 1):
        print("%2d. %-12s @ (%7.1f, %7.1f, %6.1f)  %s" % (i, what, p[0], p[1], p[2], note))

    if dry:
        if any(not e[0].startswith("그리퍼 열기") for e in sim.events):
            sim.add_error("리허설인데 그리퍼를 닫음")
        moved = [b["name"] for b in sim.blocks
                 if (b["x"], b["y"]) != tuple(map(float, ns["BLOCK_POS_" + b["name"]]))]
        if moved:
            sim.add_error("리허설인데 블록이 움직임: " + ", ".join(moved))
        print("\n(리허설 모드: DRY_RUN_OFFSET_Z = %.1f, 블록은 옮기지 않음)" % float(ns["DRY_RUN_OFFSET_Z"]))
    else:
        check_tower(sim)
        print("\n=== 최종 탑 ===")
        for name in ("LARGE", "MEDIUM", "SMALL"):
            b = sim.find(name)
            print("%-6s  %5.1f mm  바닥 z %6.1f  윗면 z %6.1f  중심 (%.1f, %.1f)"
                  % (name, b["size"], b["bottom"], b["bottom"] + b["size"], b["x"], b["y"]))

    print("\nmovel 횟수 %d, 예상 시간(대략) %.0f s (그리퍼 대기 포함)" % (sim.n_moves, sim.time))
    for w in sim.warnings:
        print("[경고] " + w)
    for e in sim.errors:
        print("[오류] " + e)
    if not sim.errors and not sim.warnings:
        print("검사: 충돌 없음, 블록이 순서대로 탑에 쌓임" if not dry else "검사: 충돌 없음")
    return 1 if sim.errors else 0


if __name__ == "__main__":
    sys.exit(main())
