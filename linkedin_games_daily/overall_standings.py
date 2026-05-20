#!/usr/bin/env python3
"""Compute cumulative standings across all saved daily results in results/."""

from __future__ import annotations
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

RESULTS_DIR = Path(__file__).parent / "results"

_PLACE = {1: "1st", 2: "2nd", 3: "3rd"}


def main() -> None:
    json_files = sorted(RESULTS_DIR.glob("*.json"))
    if not json_files:
        print(f"No results found in {RESULTS_DIR}/")
        sys.exit(1)

    cumulative: dict[str, float] = {}
    win_counts: dict[str, int] = {}
    all_players: list[str] = []
    days: list[str] = []

    for jf in json_files:
        data = json.loads(jf.read_text(encoding="utf-8"))
        days.append(data["date"])

        for p in data["players"]:
            if p not in cumulative:
                all_players.append(p)
                cumulative[p] = 0.0
                win_counts[p] = 0

        totals: dict[str, float] = data["totals"]
        for p, pts in totals.items():
            cumulative[p] = cumulative.get(p, 0.0) + pts

        top = max(totals.values(), default=0)
        if top > 0:
            for p, pts in totals.items():
                if pts == top:
                    win_counts[p] = win_counts.get(p, 0) + 1

    n_days = len(days)
    sorted_players = sorted(all_players, key=lambda p: -cumulative.get(p, 0.0))

    console = Console(no_color=True, highlight=False, width=120)
    date_range = f"{days[0]}  ->  {days[-1]}" if n_days > 1 else days[0]
    console.print(Panel(
        f"Overall Standings  --  {n_days} day(s)  --  {date_range}",
        padding=(0, 2),
    ))

    table = Table(box=box.SIMPLE_HEAD, show_lines=False, pad_edge=True, header_style="")
    table.add_column("Rank",        justify="center", width=5,  no_wrap=True)
    table.add_column("Player",      min_width=13,               no_wrap=True)
    table.add_column("Total Pts",   justify="right",  min_width=9,  no_wrap=True)
    table.add_column("Daily Wins",  justify="center", min_width=10, no_wrap=True)
    table.add_column("Avg Pts/Day", justify="right",  min_width=11, no_wrap=True)

    prev_pts: float | None = None
    visual_rank = 0
    display_pos = 0
    for player in sorted_players:
        display_pos += 1
        pts = cumulative.get(player, 0.0)
        if pts != prev_pts:
            visual_rank = display_pos
        prev_pts = pts

        wins = win_counts.get(player, 0)
        avg = pts / n_days if n_days else 0.0
        pts_str = str(int(pts)) if pts == int(pts) else f"{pts:g}"
        table.add_row(
            _PLACE.get(visual_rank, str(visual_rank)),
            player,
            pts_str,
            str(wins),
            f"{avg:.1f}",
        )

    console.print()
    console.print(table)

    top_pts = cumulative.get(sorted_players[0], 0.0) if sorted_players else 0.0
    overall_winners = [p for p in sorted_players if cumulative.get(p, 0.0) == top_pts]
    pts_str = str(int(top_pts)) if top_pts == int(top_pts) else f"{top_pts:g}"

    if len(overall_winners) == 1:
        msg = Text(
            f"Overall Winner: {overall_winners[0]}  ({pts_str} pts over {n_days} day(s))",
            justify="center",
        )
        panel = Panel(msg, title="All-Time Leader", padding=(1, 4))
    else:
        names = " & ".join(overall_winners)
        msg = Text(
            f"All-Time Tie: {names}  ({pts_str} pts each over {n_days} day(s))",
            justify="center",
        )
        panel = Panel(msg, title="All-Time Tie!", padding=(1, 4))

    console.print(panel)


if __name__ == "__main__":
    main()
