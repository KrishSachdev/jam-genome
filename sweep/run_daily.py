#!/usr/bin/env python3
"""One-command daily sweep: probe, commit, push, and report what's left.

Usage:
    python sweep/run_daily.py --solo    # collector paused (full 2,400/day)
    python sweep/run_daily.py           # collector running (~670/day)

Loudly reminds you to re-enable collection once the sweep is finished,
because a forgotten pause silently costs traffic data that can never be
re-fetched.
"""
import json
import subprocess
import sys
from pathlib import Path

SP = Path(__file__).resolve().parent
ROOT = SP.parent
STATE = SP / "sweep_state.json"


def run(cmd, **kw):
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=ROOT, **kw)


def progress():
    if not STATE.exists():
        return 0, 0
    st = json.loads(STATE.read_text())
    return len(st["done"]), len(st["segments"])


def main():
    solo = "--solo" in sys.argv
    before, _ = progress()

    cmd = [sys.executable, "sweep/sweep.py"] + (["--solo"] if solo else [])
    if run(cmd).returncode != 0:
        sys.exit("sweep failed - nothing committed")

    after, segments = progress()
    if after == before:
        print("\nno new cells probed (no allowance left today) - nothing to commit")
        return

    run(["git", "add", "sweep/sweep_state.json"])
    run(["git", "commit", "-m", f"sweep: {after:,} cells, {segments:,} segments"])
    if run(["git", "pull", "--rebase"]).returncode != 0:
        sys.exit("pull --rebase failed - resolve manually, then `git push`")
    if run(["git", "push"]).returncode != 0:
        sys.exit("push failed - run `git push` manually once resolved")

    # remaining cells, using sweep.py's own grid definition
    sys.path.insert(0, str(SP))
    import sweep as SW
    total = len(SW.build_grid())
    left = total - after

    print("\n" + "=" * 62)
    print(f"  {after:,}/{total:,} cells ({after/total*100:.1f}%)  |  {segments:,} segments")
    if left:
        print(f"  {left:,} cells left - run this again after 05:30 IST tomorrow")
    else:
        print("  SWEEP COMPLETE.")
        if solo:
            print("\n  >>> RE-ENABLE COLLECTION NOW <<<")
            print("  cron-job.org -> 'jam-genome collect' -> toggle ON")
            print("  Every paused day is traffic data you can never get back.")
    print("=" * 62)


if __name__ == "__main__":
    main()
