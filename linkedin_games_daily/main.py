#!/usr/bin/env python3
"""LinkedIn Games Daily Winner Calculator."""

from __future__ import annotations
import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from config import PLAYER_NAMES, GAME_URLS, GAME_SCORE_DIRECTIONS, HINT_BAN_SENTINEL, MANUAL_RESULTS
from scoring import compute_standings, parse_score, _fmt_pts

console = Console(no_color=True, highlight=False, width=160)

RESULTS_DIR = Path(__file__).parent / "results"

GAME_URLS_ORDER = list(GAME_URLS.keys())

GAME_SHORT = {
    "pinpoint":   "Pinpoint",
    "queens":     "Queens",
    "crossclimb": "Climb",
    "tango":      "Tango",
    "zip":        "Zip",
    "mini_sudoku": "Sudoku",
    "patches":    "Patches",
}

_PLACE = {1: "1st", 2: "2nd", 3: "3rd"}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_scraped(players: list[str], debug: bool) -> dict[str, dict[str, object]]:
    from scraper import scrape_games
    console.print("Scraping LinkedIn Games leaderboards...")
    scraped = scrape_games(players, debug=debug)

    merged: dict[str, dict[str, object]] = {}
    for game in GAME_URLS_ORDER:
        live = scraped.get(game, {})
        has_data = any(v is not None for v in live.values())
        if has_data:
            merged[game] = live
        elif game in MANUAL_RESULTS:
            console.print(f"  {game}: no scraped scores - using MANUAL_RESULTS fallback")
            merged[game] = {p: MANUAL_RESULTS[game].get(p) for p in players}
        else:
            merged[game] = {p: None for p in players}
    return merged


def _load_manual(players: list[str]) -> dict[str, dict[str, object]]:
    return {
        game: {p: MANUAL_RESULTS.get(game, {}).get(p) for p in players}
        for game in MANUAL_RESULTS
    }


# ---------------------------------------------------------------------------
# Rank computation
# ---------------------------------------------------------------------------

def _compute_game_ranks(
    game_results: dict[str, dict[str, object]],
    game_directions: dict[str, str],
    players: list[str],
) -> dict[str, dict[str, tuple | None]]:
    """Return {game: {player: (visual_rank, score_str) or None}}."""
    ranks: dict[str, dict[str, tuple | None]] = {}
    for game, raw_scores in game_results.items():
        direction = game_directions.get(game, "lower_is_better")
        reverse = direction == "higher_is_better"
        parsed = {p: parse_score(raw_scores.get(p)) for p in players}
        valid = {p: s for p, s in parsed.items() if s is not None}
        ordered = sorted(valid, key=lambda p: valid[p], reverse=reverse)

        player_ranks: dict[str, int] = {}
        i = 0
        while i < len(ordered):
            tied_score = valid[ordered[i]]
            j = i
            while j < len(ordered) and valid[ordered[j]] == tied_score:
                j += 1
            for p in ordered[i:j]:
                player_ranks[p] = i + 1
            i = j

        game_ranks: dict[str, tuple | None] = {}
        for p in players:
            raw = raw_scores.get(p)
            if p in player_ranks:
                game_ranks[p] = (player_ranks[p], str(raw))
            else:
                game_ranks[p] = None
        ranks[game] = game_ranks
    return ranks


def _rank_cell(rank_info: tuple | None) -> str:
    if rank_info is None:
        return "-"
    rank, score = rank_info
    return f"{rank}  {score}"


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _build_rich_table(
    game_results: dict[str, dict[str, object]],
    per_game_pts: dict[str, dict[str, float]],
    totals: dict[str, float],
    players: list[str],
    games: list[str],
) -> Table:
    game_ranks = _compute_game_ranks(game_results, GAME_SCORE_DIRECTIONS, players)
    sorted_players = sorted(players, key=lambda p: -totals[p])

    table = Table(
        box=box.SIMPLE_HEAD,
        show_lines=False,
        pad_edge=True,
        header_style="",
    )
    table.add_column("Rank", justify="center", width=5, no_wrap=True)
    table.add_column("Player", min_width=13, no_wrap=True)
    for game in games:
        table.add_column(GAME_SHORT.get(game, game), justify="center", min_width=8, no_wrap=True)
    table.add_column("Pts", justify="right", min_width=5, no_wrap=True)

    prev_total: float | None = None
    visual_rank = 0
    display_pos = 0
    for player in sorted_players:
        display_pos += 1
        total = totals[player]
        if total != prev_total:
            visual_rank = display_pos
        prev_total = total

        rank_label = _PLACE.get(visual_rank, str(visual_rank))
        row: list[str] = [rank_label, player]
        for game in games:
            row.append(_rank_cell(game_ranks.get(game, {}).get(player)))
        row.append(_fmt_pts(total))
        table.add_row(*row)

    return table


def _render_table(
    game_results: dict[str, dict[str, object]],
    per_game_pts: dict[str, dict[str, float]],
    totals: dict[str, float],
    players: list[str],
    games: list[str],
) -> None:
    console.print()
    console.print(_build_rich_table(game_results, per_game_pts, totals, players, games))


def _render_winner(totals: dict[str, float], players: list[str]) -> None:
    top = max(totals[p] for p in players)
    winners = [p for p in players if totals[p] == top]
    pts_label = _fmt_pts(top)

    if len(winners) == 1:
        msg = Text(f"Winner: {winners[0]}  ({pts_label} pts)", justify="center")
        panel = Panel(msg, title="Today's Winner", padding=(1, 4))
    else:
        names = " & ".join(winners)
        msg = Text(f"Tie: {names}  ({pts_label} pts each)", justify="center")
        panel = Panel(msg, title="It's a Tie!", padding=(1, 4))

    console.print(panel)


def _save_daily_results(
    game_results: dict[str, dict[str, object]],
    per_game_pts: dict[str, dict[str, float]],
    totals: dict[str, float],
    players: list[str],
    games: list[str],
    today: date,
) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    date_str = today.strftime("%Y-%m-%d")

    # --- txt: human-readable table written via a file-backed Console ---
    txt_path = RESULTS_DIR / f"{date_str}.txt"
    with open(txt_path, "w", encoding="utf-8") as fh:
        fc = Console(file=fh, no_color=True, highlight=False, width=100)
        fc.print(f"LinkedIn Games — {today.strftime('%A, %B %d %Y')}")
        fc.print()
        fc.print(_build_rich_table(game_results, per_game_pts, totals, players, games))
        top = max(totals[p] for p in players)
        winners = [p for p in players if totals[p] == top]
        if len(winners) == 1:
            fc.print(f"Winner: {winners[0]}  ({_fmt_pts(top)} pts)")
        else:
            fc.print(f"Tie: {' & '.join(winners)}  ({_fmt_pts(top)} pts each)")

    # --- json: structured data for the aggregator ---
    banned: dict[str, list[str]] = {}
    for game, scores in game_results.items():
        b = [p for p, s in scores.items() if s == HINT_BAN_SENTINEL]
        if b:
            banned[game] = b

    json_path = RESULTS_DIR / f"{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({
            "date": date_str,
            "players": players,
            "games": games,
            "totals": totals,
            "per_game_pts": per_game_pts,
            "banned": banned,
        }, fh, indent=2)

    console.print(f"Results saved -> {txt_path.relative_to(Path(__file__).parent)}")


# ---------------------------------------------------------------------------
# Zip + Patches PNG leaderboard card
# ---------------------------------------------------------------------------

ZIP_PATCHES_GAMES = ("zip", "patches")

_MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}


def _build_leaderboard_html(
    game_results: dict[str, dict[str, object]],
    players: list[str],
    sub_totals: dict[str, float],
    sorted_players: list[str],
) -> str:
    today_str = date.today().strftime("%A, %B %d %Y")

    top_total = sub_totals[sorted_players[0]] if sorted_players else 0
    winners = [p for p in sorted_players if sub_totals[p] == top_total]
    winner_label = " & ".join(w.split()[0] for w in winners) + " win" + ("s" if len(winners) == 1 else "") + " today!"

    rows_html = ""
    prev_total: float | None = None
    visual_rank = 0
    display_pos = 0
    for player in sorted_players:
        display_pos += 1
        total = sub_totals[player]
        if total != prev_total:
            visual_rank = display_pos
        prev_total = total

        medal = _MEDAL.get(visual_rank, str(visual_rank))
        zip_raw = game_results.get("zip", {}).get(player) or "—"
        patches_raw = game_results.get("patches", {}).get(player) or "—"
        pts_str = _fmt_pts(total)

        highlight = ' style="background:#fffbeb;"' if visual_rank == 1 else ""
        rows_html += f"""
        <tr{highlight}>
          <td class="medal">{medal}</td>
          <td class="name">{player}</td>
          <td class="score">{zip_raw}</td>
          <td class="score">{patches_raw}</td>
          <td class="pts">{pts_str}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #f3f2ef; display: flex; align-items: center; justify-content: center;
          padding: 18px; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }}
  .card {{ width: 440px; border-radius: 14px; overflow: hidden;
           box-shadow: 0 4px 18px rgba(0,0,0,0.18); background: #fff; }}
  .header {{ background: #0a66c2; color: #fff; padding: 18px 20px 14px; }}
  .header h1 {{ font-size: 20px; font-weight: 700; letter-spacing: 0.3px; }}
  .header p  {{ font-size: 12px; opacity: 0.85; margin-top: 3px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead tr {{ background: #f3f2ef; }}
  thead th {{ font-size: 11px; font-weight: 600; color: #666;
              text-transform: uppercase; letter-spacing: 0.5px;
              padding: 9px 12px; text-align: left; }}
  thead th.r {{ text-align: right; }}
  tbody tr {{ border-top: 1px solid #e8e8e8; }}
  tbody tr:hover {{ background: #f9f9f9; }}
  td {{ padding: 10px 12px; font-size: 14px; color: #1a1a1a; }}
  td.medal {{ width: 36px; font-size: 18px; text-align: center; padding-left: 8px; }}
  td.name  {{ font-weight: 600; }}
  td.score {{ color: #444; text-align: center; }}
  td.pts   {{ font-weight: 700; color: #0a66c2; text-align: right; }}
  .footer {{ background: #0a66c2; color: #fff; text-align: center;
             padding: 12px; font-size: 14px; font-weight: 600; letter-spacing: 0.2px; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>Zip + Patches</h1>
    <p>{today_str}</p>
  </div>
  <table>
    <thead>
      <tr>
        <th></th>
        <th>Player</th>
        <th style="text-align:center">Zip</th>
        <th style="text-align:center">Patches</th>
        <th class="r">Pts</th>
      </tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
  </table>
  <div class="footer">🏆 {winner_label}</div>
</div>
</body>
</html>"""


def _render_png(html: str, out_path: str) -> None:
    async def _run() -> None:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 476, "height": 800})
            await page.set_content(html, wait_until="load")
            card = page.locator(".card")
            await card.screenshot(path=out_path)
            await browser.close()

    asyncio.run(_run())


def _copy_image_to_clipboard(image_path: str) -> None:
    swift_code = f"""
import AppKit
if let image = NSImage(contentsOfFile: "{image_path}") {{
    let pb = NSPasteboard.general
    pb.clearContents()
    pb.writeObjects([image])
}}
"""
    swift_file = f"/tmp/set_clipboard_{os.getpid()}.swift"
    with open(swift_file, "w") as f:
        f.write(swift_code)
    try:
        subprocess.run(["swift", swift_file], check=True, capture_output=True)
    finally:
        try:
            os.unlink(swift_file)
        except OSError:
            pass


def _write_zip_patches_leaderboard(
    game_results: dict[str, dict[str, object]],
    players: list[str],
) -> None:
    subset = {g: game_results[g] for g in ZIP_PATCHES_GAMES if g in game_results}
    if not subset:
        return

    sub_pts, sub_totals = compute_standings(subset, GAME_SCORE_DIRECTIONS, players)
    sorted_players = sorted(players, key=lambda p: -sub_totals[p])

    today = date.today()
    out_path = Path(__file__).parent / f"zip_patches_{today}.png"

    html = _build_leaderboard_html(game_results, players, sub_totals, sorted_players)
    _render_png(html, str(out_path))
    console.print(f"Zip+Patches leaderboard -> {out_path}")

    try:
        _copy_image_to_clipboard(str(out_path))
        console.print("Image copied to clipboard.")
    except Exception as exc:
        console.print(f"Clipboard copy failed: {exc}")

    script = '''
tell application "Messages"
    activate
    set theChat to first chat whose name is "Touse"
    open theChat
end tell
'''
    subprocess.run(["osascript", "-e", script], capture_output=True)
    console.print('Messages opened on "Touse" — paste with Cmd+V and send.')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="LinkedIn Games Daily Winner Calculator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                        # scrape LinkedIn (default)\n"
            "  python main.py --debug                # scrape + save raw HTML to /tmp/\n"
            "  python main.py --manual               # use MANUAL_RESULTS from config.py\n"
            "  python main.py --players 'Kevin Liu' 'Daniel Suh'\n"
        ),
    )
    p.add_argument("--manual", action="store_true",
                   help="Use MANUAL_RESULTS from config.py instead of scraping")
    p.add_argument("--debug",  action="store_true",
                   help="Save raw HTML for each game to /tmp/linkedin_debug_<game>.html")
    p.add_argument("--players", nargs="+", metavar="NAME",
                   help="Limit to specific players (quote names with spaces)")
    return p


def main() -> None:
    args = build_parser().parse_args()

    players = args.players or PLAYER_NAMES
    unknown = [p for p in players if p not in PLAYER_NAMES]
    if unknown:
        console.print(f"Unknown player(s): {unknown}\nValid: {PLAYER_NAMES}")
        sys.exit(1)

    today = date.today().strftime("%A, %B %d %Y")
    mode_label = "manual" if args.manual else "scrape"
    console.print(Panel(
        f"LinkedIn Games Daily\n{today}  -  {mode_label} mode  -  {len(players)} players",
    ))

    if args.manual:
        game_results = _load_manual(players)
    else:
        try:
            game_results = _load_scraped(players, debug=args.debug)
        except Exception as exc:
            console.print(f"\nScraping failed: {exc}")
            console.print("Tip: run with --manual and paste scores into MANUAL_RESULTS in config.py")
            sys.exit(1)

    if not game_results:
        console.print("No game data. Try --manual and fill in MANUAL_RESULTS in config.py.")
        sys.exit(1)

    games = [g for g in GAME_URLS_ORDER if g in game_results]
    per_game_pts, totals = compute_standings(game_results, GAME_SCORE_DIRECTIONS, players)

    _render_table(game_results, per_game_pts, totals, players, games)
    _render_winner(totals, players)

    _save_daily_results(game_results, per_game_pts, totals, players, games, date.today())
    _write_zip_patches_leaderboard(game_results, players)


if __name__ == "__main__":
    main()
