#!/usr/bin/env python3
"""Build a temp review page for the task5_5 claude rollout.

For each of the 22 tasks, emits a card with:
  - title, reward badge, elapsed time
  - the L1 prompt (collapsible)
  - the canonical "ground-truth" video (concatenated from
    ~/Downloads/sequencing_batch2/inputs/<NAME>/clips/clip_NN.mp4 in order)
  - claude's solution.mp4 (from jobs/cc-...)

Outputs:
  - site/task5_5_review.html
  - site/task5_5_review/<task_id>_{truth,claude}.mp4
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from html import escape
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO / "tasks" / "task5_5"
JOBS_DIR = REPO / "jobs"
LOGS_TSV = REPO / "logs" / "rollout-results.tsv"
SITE_DIR = REPO / "site"
ASSETS_DIR = SITE_DIR / "task5_5_review"
SEQ_BATCH = Path.home() / "Downloads" / "sequencing_batch2"


def _concat_clips(clips: list[Path], out_mp4: Path) -> bool:
    """Concat .mp4 files via ffmpeg concat demuxer with stream copy."""
    if out_mp4.exists():
        return True
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    list_file = out_mp4.with_suffix(".txt")
    list_file.write_text("\n".join(f"file '{c.resolve()}'" for c in clips) + "\n")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(list_file), "-c", "copy", "-movflags", "+faststart", str(out_mp4)],
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        # Stream copy may fail if codecs/timebases drift; fall back to re-encode.
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                 "-i", str(list_file), "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "23", "-c:a", "aac", "-movflags", "+faststart", str(out_mp4)],
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"  concat failed for {out_mp4.name}: {e}")
            return False
    finally:
        list_file.unlink(missing_ok=True)


def _last_reward(task_name: str) -> tuple[float | None, int | None]:
    """Read the most recent reward + elapsed for `task_name` from the TSV."""
    reward, elapsed = None, None
    if not LOGS_TSV.exists():
        return reward, elapsed
    for line in LOGS_TSV.open():
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5 or parts[1] != task_name:
            continue
        try:
            reward = float(parts[2])
            elapsed = int(parts[4])
        except ValueError:
            pass
    return reward, elapsed


def _last_reward_details(task_name: str) -> dict | None:
    """Read the latest cc job's reward.json details for nd/lis/adj subscores."""
    jobs = sorted(JOBS_DIR.glob(f"cc-{task_name}-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for job in jobs:
        for rj in job.rglob("**/verifier/reward.json"):
            try:
                return json.loads(rj.read_text()).get("details") or {}
            except Exception:
                continue
    return None


def _claude_output(task_name: str) -> Path | None:
    """Locate the most recent claude cc job's solution.mp4 for `task_name`."""
    jobs = sorted(JOBS_DIR.glob(f"cc-{task_name}-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for job in jobs:
        for art in job.rglob("artifacts/solution.mp4"):
            return art
    return None


def _video_name(task_dir: Path) -> str:
    toml = tomllib.loads((task_dir / "task.toml").read_text())
    src = toml["metadata"]["source"]  # "sequencing_batch2/<NAME> (level=L1, rep_01)"
    return src.split("/", 1)[1].split(" (", 1)[0]


def _reward_class(r: float | None) -> str:
    if r is None: return "missing"
    if r >= 0.9: return "high"
    if r >= 0.6: return "mid"
    if r >= 0.3: return "low"
    return "zero"


def render() -> str:
    rows = []
    for task_dir in sorted(TASKS_DIR.glob("video-edit-bench-task-5-5-task*"),
                           key=lambda d: int(d.name.rsplit("task", 1)[-1])):
        tid = int(task_dir.name.rsplit("task", 1)[-1])
        name = _video_name(task_dir)
        instr = (task_dir / "steps/solve/instruction.md").read_text()
        reward, elapsed = _last_reward(task_dir.name)
        det = _last_reward_details(task_dir.name) or {}
        nd_s  = det.get("nd_score")   # already (1 − TD)
        lis_s = det.get("lis_score")
        adj_s = det.get("adj_score")
        # Multiplicative composite: harsh — any near-zero factor zeros the total.
        if nd_s is not None and lis_s is not None and adj_s is not None:
            new_score = nd_s * lis_s * adj_s
        else:
            new_score = None

        # Ground-truth concat (canonical original order).
        gt_clips_dir = SEQ_BATCH / "inputs" / name / "clips"
        gt_clips = sorted(gt_clips_dir.glob("clip_*.mp4"),
                          key=lambda p: int(p.stem.split("_")[1]))
        truth_mp4 = ASSETS_DIR / f"{tid}_truth.mp4"
        truth_ok = bool(gt_clips) and _concat_clips(gt_clips, truth_mp4)

        # Claude's solution.
        claude_src = _claude_output(task_dir.name)
        claude_mp4 = ASSETS_DIR / f"{tid}_claude.mp4"
        if claude_src and not claude_mp4.exists():
            shutil.copy2(claude_src, claude_mp4)
        claude_ok = claude_mp4.exists()

        rows.append({
            "tid": tid, "name": name, "instr": instr,
            "reward": reward, "elapsed": elapsed,
            "nd": nd_s, "lis": lis_s, "adj": adj_s, "new_score": new_score,
            "truth_rel": f"task5_5_review/{tid}_truth.mp4" if truth_ok else None,
            "claude_rel": f"task5_5_review/{tid}_claude.mp4" if claude_ok else None,
            "n_clips": len(gt_clips),
        })
        print(f"  task{tid:>2}  reward={reward}  truth={'ok' if truth_ok else 'MISS'}  "
              f"claude={'ok' if claude_ok else 'MISS'}  ({name})")

    # Sort by reward desc for the page
    rows.sort(key=lambda r: (-(r["reward"] or -1)))
    mean = sum(r["reward"] for r in rows if r["reward"] is not None) / max(1, sum(1 for r in rows if r["reward"] is not None))

    cards = []
    for r in rows:
        cls = _reward_class(r["reward"])
        rstr = f"{r['reward']:.4f}" if r["reward"] is not None else "—"
        estr = f"{r['elapsed']}s" if r["elapsed"] is not None else "—"
        truth_html = (
            f'<video controls preload="metadata" src="{r["truth_rel"]}"></video>'
            if r["truth_rel"] else "<div class='missing'>ground-truth video not built</div>"
        )
        claude_html = (
            f'<video controls preload="metadata" src="{r["claude_rel"]}"></video>'
            if r["claude_rel"] else "<div class='missing'>claude produced no solution.mp4</div>"
        )
        cards.append(f"""
<section class="task task-{cls}" id="task{r['tid']}">
  <header>
    <h2>task{r['tid']} · {escape(r['name'])}</h2>
    <div class="meta">
      <span class="badge badge-{cls}">reward {rstr}</span>
      <span class="badge">elapsed {estr}</span>
      <span class="badge">{r['n_clips']} clips</span>
    </div>
  </header>
  <details><summary>L1 prompt (what the agent read)</summary><pre class="instr">{escape(r['instr'])}</pre></details>
  <div class="videos">
    <div class="vcell">
      <div class="vlabel">📼 Ground truth (canonical order)</div>
      {truth_html}
    </div>
    <div class="vcell">
      <div class="vlabel">🧠 Claude-code (sonnet 4.6) output</div>
      {claude_html}
    </div>
  </div>
</section>""")

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>task5_5 review · claude-code + sonnet 4.6</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 24px auto; max-width: 1200px; padding: 0 16px; color: #1a1a1a; }}
  h1 {{ margin-bottom: 4px; }}
  .summary {{ background: #f7f7f7; padding: 12px 16px; border-radius: 8px; margin-bottom: 24px; font-size: 14px; }}
  .summary b {{ font-size: 16px; }}
  section.task {{ border: 1px solid #e5e5e5; border-radius: 10px; padding: 16px; margin-bottom: 20px; background: #fff; }}
  section.task.task-zero {{ border-left: 4px solid #d33; }}
  section.task.task-low {{ border-left: 4px solid #e90; }}
  section.task.task-mid {{ border-left: 4px solid #ec5; }}
  section.task.task-high {{ border-left: 4px solid #393; }}
  section.task header {{ display: flex; align-items: baseline; gap: 12px; margin-bottom: 10px; }}
  section.task h2 {{ margin: 0; font-size: 16px; font-weight: 600; }}
  .meta {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .badge {{ background: #eee; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
  .badge-zero {{ background: #fcd; color: #800; }}
  .badge-low  {{ background: #fed; color: #850; }}
  .badge-mid  {{ background: #ffd; color: #650; }}
  .badge-high {{ background: #cfc; color: #050; }}
  details {{ margin-bottom: 10px; }}
  summary {{ cursor: pointer; font-size: 13px; color: #555; }}
  pre.instr {{ background: #fafafa; border: 1px solid #eee; border-radius: 6px; padding: 10px; font-size: 12px; line-height: 1.4; overflow-x: auto; max-height: 280px; overflow-y: auto; white-space: pre-wrap; }}
  .videos {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
  .vcell {{ display: flex; flex-direction: column; gap: 4px; }}
  .vlabel {{ font-size: 12px; color: #555; }}
  video {{ width: 100%; max-height: 320px; background: #000; border-radius: 6px; }}
  .missing {{ font-size: 12px; color: #a33; padding: 60px 0; text-align: center; background: #fafafa; border-radius: 6px; }}
  table.stats {{ width: 100%; border-collapse: collapse; margin: 14px 0 24px; font-size: 13px; background: #fff; border: 1px solid #e5e5e5; border-radius: 8px; overflow: hidden; }}
  table.stats th, table.stats td {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid #f0f0f0; }}
  table.stats th {{ background: #fafafa; font-weight: 600; font-size: 12px; color: #555; }}
  table.stats td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  table.stats td.bar {{ width: 220px; padding: 0 10px; }}
  table.stats .bar-track {{ background: #f0f0f0; border-radius: 3px; height: 10px; position: relative; }}
  table.stats .bar-fill {{ height: 100%; border-radius: 3px; }}
  table.stats tr.row-high .bar-fill {{ background: #393; }}
  table.stats tr.row-mid  .bar-fill {{ background: #ec5; }}
  table.stats tr.row-low  .bar-fill {{ background: #e90; }}
  table.stats tr.row-zero .bar-fill {{ background: #d33; }}
  table.stats tr.row-missing .bar-fill {{ background: #ccc; }}
  table.stats a {{ color: #06c; text-decoration: none; }}
  table.stats a:hover {{ text-decoration: underline; }}
  table.stats tfoot td {{ background: #fafafa; font-weight: 600; border-bottom: 0; }}
  h2.ttitle {{ margin: 20px 0 6px; font-size: 14px; font-weight: 600; color: #333; }}
  h2.ttitle .ttitle-sub {{ font-weight: 400; font-size: 12px; color: #888; }}
</style></head>
<body>
<h1>task5_5 review</h1>
<div class="summary">
  <b>22 tasks</b> · agent: <code>claude-code</code> + <code>claude-sonnet-4-6</code> · env: <code>modal</code> ·
  mean reward <b>{mean:.4f}</b> · strict-match {sum(1 for r in rows if r['reward']==1.0)}/22 ·
  non-zero {sum(1 for r in rows if (r['reward'] or 0)>0)}/22 ·
  total wall-clock 20m 41s (22 in parallel)
</div>
{_stats_table_product(rows)}
{_stats_table(rows)}
{"".join(cards)}
</body></html>
"""


def _stats_table_product(rows: list[dict]) -> str:
    """Multiplicative score table: (1−TD) · LIS · ADJ.

    Harsher than the harbor weighted-sum reward: any single weak component drags
    the total to zero. Surfaces the 3 factors so it's clear *which* one tanked.
    """
    sorted_rows = sorted(rows, key=lambda r: -(r["new_score"] or -1))
    trs = []
    for r in sorted_rows:
        ns = r["new_score"]
        cls = _reward_class(ns)
        def fmt(x):
            return f"{x:.3f}" if x is not None else "—"
        pct = int(round((ns or 0) * 100))
        trs.append(f"""
<tr class="row-{cls}">
  <td><a href="#task{r['tid']}">task{r['tid']}</a></td>
  <td>{escape(r['name'])}</td>
  <td class="num">{r['n_clips']}</td>
  <td class="num">{fmt(r['nd'])}</td>
  <td class="num">{fmt(r['lis'])}</td>
  <td class="num">{fmt(r['adj'])}</td>
  <td class="num"><b>{fmt(ns)}</b></td>
  <td class="bar"><div class="bar-track"><div class="bar-fill" style="width: {pct}%"></div></div></td>
</tr>""")
    scored = [r for r in rows if r["new_score"] is not None]
    mean_new = sum(r["new_score"] for r in scored) / max(1, len(scored))
    mean_nd  = sum(r["nd"]  for r in scored) / max(1, len(scored))
    mean_lis = sum(r["lis"] for r in scored) / max(1, len(scored))
    mean_adj = sum(r["adj"] for r in scored) / max(1, len(scored))
    return f"""
<h2 class="ttitle">Alt scoring: (1 − TD) × LIS × ADJ &nbsp;<span class="ttitle-sub">multiplicative — any near-zero factor zeros the total</span></h2>
<table class="stats">
  <thead><tr>
    <th>task</th><th>video</th><th class="num">clips</th>
    <th class="num">1−TD</th><th class="num">LIS</th><th class="num">ADJ</th>
    <th class="num">score</th><th>&nbsp;</th>
  </tr></thead>
  <tbody>{"".join(trs)}</tbody>
  <tfoot><tr>
    <td colspan="3">mean across {len(scored)} scored tasks</td>
    <td class="num">{mean_nd:.4f}</td>
    <td class="num">{mean_lis:.4f}</td>
    <td class="num">{mean_adj:.4f}</td>
    <td class="num"><b>{mean_new:.4f}</b></td>
    <td></td>
  </tr></tfoot>
</table>
<h2 class="ttitle">Harbor scoring: 0.4·(1−TD) + 0.3·LIS + 0.3·ADJ &nbsp;<span class="ttitle-sub">weighted sum — the reward written by the verifier</span></h2>
"""


def _stats_table(rows: list[dict]) -> str:
    """Overall stats table — one row per task, with a reward bar + jump link."""
    trs = []
    total_elapsed = 0
    for r in rows:
        cls = _reward_class(r["reward"])
        rstr = f"{r['reward']:.4f}" if r["reward"] is not None else "—"
        estr = f"{r['elapsed']}s" if r["elapsed"] is not None else "—"
        pct = int(round((r["reward"] or 0) * 100))
        if r["elapsed"]: total_elapsed += r["elapsed"]
        trs.append(f"""
<tr class="row-{cls}">
  <td><a href="#task{r['tid']}">task{r['tid']}</a></td>
  <td>{escape(r['name'])}</td>
  <td class="num">{r['n_clips']}</td>
  <td class="num">{rstr}</td>
  <td class="bar"><div class="bar-track"><div class="bar-fill" style="width: {pct}%"></div></div></td>
  <td class="num">{estr}</td>
</tr>""")
    n_done = sum(1 for r in rows if r["reward"] is not None)
    return f"""
<table class="stats">
  <thead><tr>
    <th>task</th><th>video</th><th class="num">clips</th>
    <th class="num">reward</th><th>&nbsp;</th><th class="num">elapsed</th>
  </tr></thead>
  <tbody>{"".join(trs)}</tbody>
  <tfoot><tr>
    <td colspan="2">{n_done} tasks scored</td>
    <td class="num">{sum(r['n_clips'] for r in rows)}</td>
    <td class="num">mean {sum((r['reward'] or 0) for r in rows)/max(1,n_done):.4f}</td>
    <td></td>
    <td class="num">Σ {total_elapsed}s</td>
  </tr></tfoot>
</table>
"""


def main():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    html = render()
    out = SITE_DIR / "task5_5_review.html"
    out.write_text(html)
    print(f"\nwrote {out}")
    print(f"open file://{out.resolve()}")


if __name__ == "__main__":
    main()
