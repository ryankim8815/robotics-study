#!/usr/bin/env python3
"""write_text.py (DRL Custom Code) 를 PC 에서 미리 실행해 펜 경로를 확인하는 도구.

로봇 없이 DRL 함수(movel, get_current_posx, tp_popup ...)를 가짜(stub)로 바꿔
write_text.py 를 그대로 실행하고, 결과 경로를 PNG 로 저장합니다.
로봇에 올리는 파일이 아닙니다.

사용 예:
    python3 preview.py
    python3 preview.py --text "ROBOT 2026"
    python3 preview.py --set CHAR_HEIGHT=20 --set "CANVAS_TOP_LEFT=(600, 150)"
    python3 preview.py --start 450 0 120 0 180 0 --out path.png
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


class DrlExit(Exception):
    """DRL exit() 이 호출됨 (설정 오류 등)."""


def make_namespace(start_pose, moves, popups):
    """write_text.py 가 쓰는 DRL API 만 흉내 내는 실행 네임스페이스."""
    ns = dict(DRL_CONSTANTS)
    state = {"pose": None}

    def current():
        if state["pose"] is None:
            if start_pose is not None:
                state["pose"] = list(start_pose)
            else:  # 기본: 캔버스 중앙, 펜이 아래를 향하는 자세
                c = [ns[k] for k in ("CANVAS_TOP_LEFT", "CANVAS_TOP_RIGHT",
                                     "CANVAS_BOTTOM_RIGHT", "CANVAS_BOTTOM_LEFT")]
                # WRITE_Z 지정: 펜 든 높이보다 50mm 위 허공 / None: z=0 (= 쓰기 높이)
                z = 0.0 if ns["WRITE_Z"] is None else float(ns["WRITE_Z"]) + float(ns["PEN_UP_Z"]) + 50.0
                state["pose"] = [sum(p[0] for p in c) / 4.0, sum(p[1] for p in c) / 4.0,
                                 z, 0.0, 180.0, 0.0]
        return state["pose"]

    def posx(*v):
        if len(v) != 6:
            raise TypeError("posx() needs 6 values, got %d" % len(v))
        return [float(a) for a in v]

    def movel(pos, vel=None, acc=None, time=None, radius=None, ref=None,
              mod=DRL_CONSTANTS["DR_MV_MOD_ABS"], **_):
        if ref != DRL_CONSTANTS["DR_BASE"] or mod != DRL_CONSTANTS["DR_MV_MOD_ABS"]:
            raise ValueError("preview expects absolute moves in DR_BASE")
        src = list(current())
        moves.append((src, list(pos), float(vel), float(acc), float(radius or 0.0)))
        state["pose"] = list(pos)
        return 0

    def get_current_posx(ref=DRL_CONSTANTS["DR_BASE"], ori_type=None):
        return list(current()), 2

    def tp_popup(message, pm_type=0, button_type=0):
        popups.append((pm_type, message))
        kind = {0: "MESSAGE", 1: "WARNING", 2: "ALARM"}.get(pm_type, str(pm_type))
        print("[tp_popup %s] %s" % (kind, message))
        return 0

    def tp_log(message):
        print("[tp_log] %s" % message)
        return 0

    def drl_exit():
        raise DrlExit()

    ns.update(posx=posx, movel=movel, get_current_posx=get_current_posx,
              tp_popup=tp_popup, tp_log=tp_log, exit=drl_exit,
              wait=lambda t: 0, set_ref_coord=lambda c: 0)
    return ns


def run_drl(path, overrides, start_pose):
    """마지막 tw_main() 호출을 떼고 실행 -> 설정 덮어쓰기 -> tw_main() 실행."""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    tree.body = [n for n in tree.body
                 if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                         and getattr(n.value.func, "id", "") == "tw_main")]
    moves, popups = [], []
    ns = make_namespace(start_pose, moves, popups)
    exec(compile(tree, path, "exec"), ns)
    ns.update(overrides)
    ok = True
    try:
        ns["tw_main"]()
    except DrlExit:
        ok = False
    return ns, moves, popups, ok


def seg_time(d, v, a):
    """사다리꼴 속도 프로파일 기준 대략적인 이동 시간 [s]."""
    if d <= 0:
        return 0.0
    if d >= v * v / a:
        return d / v + v / a
    return 2.0 * math.sqrt(d / a)


def inside_convex(p, poly):
    sign = 0
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        cr = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        if abs(cr) < 1e-9:
            continue
        s = 1 if cr > 0 else -1
        if sign and s != sign:
            return False
        sign = s
    return True


def analyze(ns, moves):
    """펜 경로를 그리기/이동으로 나누고 안전 조건을 검사합니다."""
    z_down = min(m[1][2] for m in moves)
    z_up = z_down + float(ns["PEN_UP_Z"])
    corners = [ns[k] for k in ("CANVAS_TOP_LEFT", "CANVAS_TOP_RIGHT",
                               "CANVAS_BOTTOM_RIGHT", "CANVAS_BOTTOM_LEFT")]
    draw, travel, problems = [], [], []
    if ns["WRITE_Z"] is not None:
        expected = float(ns["WRITE_Z"]) + float(ns["DRY_RUN_OFFSET_Z"])
        if abs(z_down - expected) > EPS:
            problems.append("쓰기 높이 %.2f 가 WRITE_Z(+리허설 오프셋) %.2f 와 다름" % (z_down, expected))
    total_t = 0.0
    for src, dst, vel, acc, _ in moves:
        d = math.dist(src[:3], dst[:3])
        total_t += seg_time(d, vel, acc)
        on_paper = abs(src[2] - z_down) < EPS and abs(dst[2] - z_down) < EPS
        if on_paper:
            draw.append((src, dst))
            for p in (src, dst):
                if not inside_convex(p, corners):
                    problems.append("canvas 밖 점: (%.1f, %.1f)" % (p[0], p[1]))
        else:
            travel.append((src, dst))
            moved_xy = math.dist(src[:2], dst[:2]) > EPS
            low = min(src[2], dst[2]) < z_up - EPS
            if moved_xy and low:
                problems.append("펜을 덜 든 채 수평 이동: (%.1f, %.1f, %.1f) -> (%.1f, %.1f, %.1f)"
                                % (tuple(src[:3]) + tuple(dst[:3])))
    # 찍기(점): 펜 내림 직후 같은 자리에서 바로 펜 올림
    dots = []
    for m, n in zip(moves, moves[1:]):
        down = abs(m[1][2] - z_down) < EPS and m[0][2] > z_down + EPS
        up = abs(n[0][2] - z_down) < EPS and n[1][2] > z_down + EPS
        if down and up and math.dist(m[1][:2], n[1][:2]) < EPS:
            dots.append(m[1])
    return {
        "z_down": z_down, "z_up": z_up, "corners": corners,
        "draw": draw, "travel": travel, "dots": dots, "problems": problems,
        "draw_len": sum(math.dist(a[:2], b[:2]) for a, b in draw),
        "travel_len": sum(math.dist(a[:3], b[:3]) for a, b in travel),
        "time": total_t,
    }


def plot(ns, res, start, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tl, tr, br, bl = res["corners"]
    th = math.atan2(br[1] - bl[1], br[0] - bl[0])
    c, s = math.cos(th), math.sin(th)

    def reader(p):  # 캔버스 아래 변이 수평이 되도록 회전 = 글씨를 읽는 사람 시점
        return (p[0] * c + p[1] * s, -p[0] * s + p[1] * c)

    def top(p):     # 로봇 위에서 본 베이스 좌표 (가로: Y, 반전해서 +Y 가 왼쪽 / 세로: X)
        return (p[1], p[0])

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, f, title in ((axes[0], reader, "Reader view (canvas bottom edge horizontal)"),
                         (axes[1], top, "Robot top view (base frame: up=+X, left=+Y)")):
        quad = [f(p) for p in (tl, tr, br, bl, tl)]
        ax.plot([q[0] for q in quad], [q[1] for q in quad], color="#888", lw=1)
        for name, p in (("TL", tl), ("TR", tr), ("BR", br), ("BL", bl)):
            q = f(p)
            ax.annotate(name, q, color="#888", fontsize=8, xytext=(3, 3), textcoords="offset points")
        for a, b in res["travel"]:
            qa, qb = f(a), f(b)
            ax.plot([qa[0], qb[0]], [qa[1], qb[1]], color="#7fb3ff", lw=0.5, ls="--")
        for a, b in res["draw"]:
            qa, qb = f(a), f(b)
            ax.plot([qa[0], qb[0]], [qa[1], qb[1]], color="k", lw=1.6, solid_capstyle="round")
        for p in res["dots"]:
            q = f(p)
            ax.plot(q[0], q[1], "ko", ms=2.5)
        q = f(start)
        ax.plot(q[0], q[1], "r^", ms=7, label="start")
        if f is top:
            ax.plot(0, 0, "s", color="#444", ms=9, label="robot base")
            ax.invert_xaxis()
            ax.set_xlabel("Y [mm]")
            ax.set_ylabel("X [mm]")
        else:
            ax.set_xticks([])
            ax.set_yticks([])
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=10)
        ax.legend(loc="best", fontsize=8)
        ax.grid(alpha=0.2)
    fig.suptitle("TEXT = %r" % ns["TEXT"])
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)


def main():
    ap = argparse.ArgumentParser(description="write_text.py 펜 경로 미리보기")
    ap.add_argument("drl", nargs="?", default=os.path.join(HERE, "write_text.py"))
    ap.add_argument("--text", help="TEXT 를 이 값으로 바꿔서 실행")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="설정 덮어쓰기 (Python 리터럴), 여러 번 사용 가능")
    ap.add_argument("--start", nargs=6, type=float, metavar=("X", "Y", "Z", "RX", "RY", "RZ"),
                    help="가상 시작 자세 (기본: 캔버스 중앙, WRITE_Z+PEN_UP_Z+50 높이, 0 180 0)")
    ap.add_argument("--out", default="preview.png", help="저장할 PNG 경로")
    ap.add_argument("--no-plot", action="store_true", help="그림 없이 요약만 출력")
    args = ap.parse_args()

    overrides = {}
    for item in args.set:
        name, _, value = item.partition("=")
        overrides[name.strip()] = ast.literal_eval(value.strip())
    if args.text is not None:
        overrides["TEXT"] = args.text

    ns, moves, popups, ok = run_drl(args.drl, overrides, args.start)
    if not ok:
        print("\n=> 설정 오류로 DRL 이 exit() 했습니다. 위 ALARM 메시지를 확인하세요.")
        return 1

    res = analyze(ns, moves)
    start = moves[0][0]
    print("\n=== 요약 ===")
    print("TEXT            : %r (%d자)" % (ns["TEXT"], len(ns["TEXT"])))
    print("쓰기 / 펜 든 z  : %.1f / %.1f mm" % (res["z_down"], res["z_up"]))
    print("movel 횟수      : %d" % len(moves))
    print("쓰기 / 이동 거리: %.0f / %.0f mm" % (res["draw_len"], res["travel_len"]))
    print("예상 시간(대략) : %.0f s (블렌딩/통신 지연 미반영)" % res["time"])
    if res["problems"]:
        print("\n[경고] %d건" % len(res["problems"]))
        for p in res["problems"][:20]:
            print("  - " + p)
    else:
        print("검사            : 모든 쓰기 점이 캔버스 안, 수평 이동은 모두 펜을 든 상태")

    if not args.no_plot:
        try:
            plot(ns, res, start, args.out)
            print("그림 저장       : %s" % os.path.abspath(args.out))
        except ImportError:
            print("(matplotlib 이 없어 그림은 건너뜁니다: pip install matplotlib)")
    return 1 if res["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
