#!/usr/bin/env python3
"""Grade a Minecraft first-person gameplay-ledger reconstruction. Pure stdlib, deterministic.

The video is a long FIRST-PERSON recording of a player exploring a generated Minecraft world:
walking, looking around, mining blocks (the camera turns to each block as it breaks), placing
blocks to build structures, and fighting mobs with a sword or a bow. The agent reconstructs the
ordered ledger of deliberate actions: for each event, `action` (mine / place / kill), `target`
(block or mob type), `t` (the time in the video, in seconds, at which it happens), and for kills
the `tool` (sword / bow).

Scoring is an ORDER-PRESERVING, TIME-WINDOWED, RECALL-WEIGHTED F-beta over the (action, target)
sequence: a predicted event may align to a ground-truth event only if the (action, target) tokens
match AND the predicted time is within +/-TIME_TOL seconds of the true time; among all such matches
the score is the longest common subsequence (so alignment stays monotone in time and one missed /
extra / wrong event costs only that event). This is the maintainer-requested "order-preserving LCS
plus a time tolerance": the time window makes the ORDER real — a ledger with the right multiset but
the wrong timing (events shuffled onto the wrong parts of the video) can no longer collect credit.

    reward = 0.85 * F2(action, target; time-windowed LCS)  +  0.15 * weapon-F1 over aligned kills

(the 0.15 weapon weight applies only when the ground truth has kills to score; with no kills it
folds into the F2 term, so the oracle reaches 1.0 for any render). beta=2 weights recall 2x
precision (reconstructing the WHOLE ledger is the task). The oracle (every event at its true time)
scores exactly 1.0; empty / all-wrong / wrong-time answers score ~0.
The +/-10 s window absorbs the agent's time-reading imprecision and the render's timing jitter while
staying far tighter than the ~238 min span, so a shuffled ledger cannot align.

Ground truth (ordered tokens with per-event video time `t`) is baked verifier-side at
/tests/ground_truth.json.
"""
import argparse, json, re
from pathlib import Path
GT_PATH = Path(__file__).with_name("ground_truth.json")
TIME_TOL = 10.0   # seconds; a prediction aligns only within this window of the true event time

def norm(s): return re.sub(r"[^a-z0-9]", "", str(s).lower())

def act_norm(a):
    a = norm(a)
    if a in ("mine","mined","break","broke","dig","dug"): return "mine"
    if a in ("place","placed","put","set","build","built"): return "place"
    if a in ("kill","killed","mobkill","defeat","defeated","slay","slew"): return "kill"
    return a

def token(ev): return (act_norm(ev.get("action") or ev.get("event")), norm(ev.get("target") or ev.get("block")))

def parse_time(ev):
    """Video time of an event in seconds, or None if absent/unparseable. Accepts a number of seconds
    or a clock string 'mm:ss' / 'h:mm:ss' (also '1m20s')."""
    v = ev.get("t", ev.get("time", ev.get("timestamp", ev.get("video_time"))))
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip()
    if re.fullmatch(r"\d+(\.\d+)?", s): return float(s)
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{1,2}(?:\.\d+)?)", s)
    if m:
        h = float(m.group(1) or 0); return h*3600 + float(m.group(2))*60 + float(m.group(3))
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", s)
    if m and any(m.groups()):
        return float(m.group(1) or 0)*3600 + float(m.group(2) or 0)*60 + float(m.group(3) or 0)
    return None

def weapon_norm(w):
    w = norm(w)
    if "bow" in w or "arrow" in w or "ranged" in w: return "bow"
    if "sword" in w or "melee" in w or "blade" in w: return "sword"
    return w

def matches(pt, pta, gt, gta):
    """Predicted (token pt, time pta) may align to GT (token gt, time gta): same token, in window."""
    if pt != gt: return False
    if pta is None or gta is None: return False
    return abs(pta - gta) <= TIME_TOL

def windowed_lcs_pairs(P, Pt, G, Gt):
    """Matched (i, j) pairs of a longest common subsequence under the token+time-window match rule."""
    n, m = len(P), len(G)
    if n == 0 or m == 0: return []
    tbl = [[0]*(m+1) for _ in range(n+1)]
    for i in range(1, n+1):
        pi, pti = P[i-1], Pt[i-1]; row, prev = tbl[i], tbl[i-1]
        for j in range(1, m+1):
            if matches(pi, pti, G[j-1], Gt[j-1]): row[j] = prev[j-1]+1
            else: row[j] = prev[j] if prev[j] >= row[j-1] else row[j-1]
    out, i, j = [], n, m
    while i > 0 and j > 0:
        if matches(P[i-1], Pt[i-1], G[j-1], Gt[j-1]) and tbl[i][j] == tbl[i-1][j-1]+1:
            out.append((i-1, j-1)); i -= 1; j -= 1
        elif tbl[i-1][j] >= tbl[i][j-1]: i -= 1
        else: j -= 1
    return out[::-1]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    a = ap.parse_args()
    gt_raw = json.loads(GT_PATH.read_text())["events"]
    G = [token(e) for e in gt_raw]; Gt = [parse_time(e) for e in gt_raw]
    reason = "ok"; pred_raw = []; P = []; Pt = []
    try:
        raw = json.loads(a.solution.read_text()).get("events", [])
        if not isinstance(raw, list): raise ValueError("events not a list")
        pred_raw = [e for e in raw if isinstance(e, dict)]
        P = [token(e) for e in pred_raw]; Pt = [parse_time(e) for e in pred_raw]
    except Exception as exc:  # noqa: BLE001
        reason = f"unreadable solution.json: {exc}"

    pairs = windowed_lcs_pairs(P, Pt, G, Gt)
    lcs = len(pairs); np_, ng = len(P), len(G)
    n_timed = sum(1 for t in Pt if t is not None)
    prec = (lcs/np_) if np_ else 0.0
    rec = (lcs/ng) if ng else 0.0
    b2 = 4.0
    f1 = ((1+b2)*prec*rec/(b2*prec+rec)) if (b2*prec+rec) > 0 else 0.0

    # Weapon credit only on kills inside the alignment (a kill you never localized earns nothing).
    aligned_kills = [(i, j) for (i, j) in pairs if G[j][0] == "kill"]
    wl = sum(1 for i, j in aligned_kills
             if weapon_norm(pred_raw[i].get("tool") or pred_raw[i].get("weapon") or "")
             == weapon_norm(gt_raw[j].get("tool") or gt_raw[j].get("weapon") or ""))
    nw_g = sum(1 for t in G if t[0] == "kill"); nw_p = sum(1 for t in P if t[0] == "kill")
    f1w = (2*wl/(nw_p+nw_g)) if (nw_p+nw_g) else 0.0
    # Weight the weapon component only when the ground truth actually has kills to score; with no
    # kills its 0.15 folds into the ledger F2, so the oracle reaches 1.0 for ANY render (not just
    # ones that happen to contain a kill). v38 has 139 kills, so this is exactly 0.85*f1 + 0.15*f1w.
    w_weapon = 0.15 if nw_g > 0 else 0.0
    reward = (1.0 - w_weapon)*f1 + w_weapon*f1w
    det = {"reason": reason, "n_ground_truth": ng, "n_predicted": np_, "n_predicted_timed": n_timed,
           "time_tol_s": TIME_TOL, "aligned": lcs,
           "ledger_precision": round(prec,4), "ledger_recall": round(rec,4), "beta": 2.0,
           "ledger_fbeta": round(f1,4), "n_gt_kills": nw_g, "n_pred_kills": nw_p,
           "aligned_kills": len(aligned_kills), "weapon_correct": wl, "weapon_f1": round(f1w,4),
           "weapon_weight": w_weapon,
           "note": "reward = (1-w)*F2(action,target; order-preserving LCS within +/-%gs time window) "
                   "+ w*weapon-F1 over aligned kills, w=0.15 when the GT has kills else 0 "
                   "(so the oracle = 1.0 for any render)" % TIME_TOL}
    a.reward_json.parent.mkdir(parents=True, exist_ok=True)
    a.reward_json.write_text(json.dumps({"reward": round(reward,4), "details": det}, indent=2))
    a.reward_txt.write_text(f"{round(reward,4)}\n")

if __name__ == "__main__": main()
