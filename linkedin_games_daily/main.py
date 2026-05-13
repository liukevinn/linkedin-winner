#!/usr/bin/env python3
"""LinkedIn Games Daily Winner Calculator."""

from __future__ import annotations
import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from config import PLAYER_NAMES, GAME_URLS, GAME_SCORE_DIRECTIONS, MANUAL_RESULTS
from scoring import compute_standings, parse_score, _fmt_pts

console = Console(record=True, no_color=True, highlight=False, width=160)

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

def _render_table(
    game_results: dict[str, dict[str, object]],
    per_game_pts: dict[str, dict[str, float]],
    totals: dict[str, float],
    players: list[str],
    games: list[str],
) -> None:
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

    console.print()
    console.print(table)


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


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------

def _export_pdf(output_path: str) -> None:
    html = console.export_html(inline_styles=True)

    style_patch = """
    <style>
      @page { size: A4 landscape; margin: 1.5cm; }
      body  { margin: 0; padding: 0; background: #ffffff; color: #000000; }
      pre   { white-space: pre; font-size: 13px; line-height: 1.5;
              font-family: "Courier New", Courier, monospace;
              color: #000000; background: #ffffff; }
    </style>
    """
    html = html.replace("</head>", f"{style_patch}</head>")

    async def _run() -> None:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1400, "height": 900})
            await page.set_content(html, wait_until="load")
            await page.pdf(
                path=output_path,
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            await browser.close()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Zip + Patches leaderboard file
# ---------------------------------------------------------------------------

ZIP_PATCHES_GAMES = ("zip", "patches")

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
    out_path = Path(__file__).parent / f"zip_patches_{today}.txt"

    lines = [
        f"ZIP + PATCHES LEADERBOARD  -  {today.strftime('%A, %B %d %Y')}",
        "=" * 50,
        f"{'Rank':<6}{'Player':<16}{'Zip':>8}{'Patches':>10}{'Pts':>8}",
        "-" * 50,
    ]

    prev_total: float | None = None
    visual_rank = 0
    display_pos = 0
    for player in sorted_players:
        display_pos += 1
        total = sub_totals[player]
        if total != prev_total:
            visual_rank = display_pos
        prev_total = total

        rank_label = _PLACE.get(visual_rank, str(visual_rank))
        zip_raw     = game_results.get("zip",     {}).get(player) or "-"
        patches_raw = game_results.get("patches", {}).get(player) or "-"
        lines.append(
            f"{rank_label:<6}{player:<16}{str(zip_raw):>8}{str(patches_raw):>10}{_fmt_pts(total):>8}"
        )

    lines.append("=" * 50)

    out_path.write_text("\n".join(lines) + "\n")
    console.print(f"Zip+Patches leaderboard -> {out_path}")


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

    pdf_path = Path(__file__).parent / f"linkedin_games_{date.today()}.pdf"
    try:
        _export_pdf(str(pdf_path))
        console.print(f"\nPDF saved -> {pdf_path}")
    except Exception as exc:
        console.print(f"\nPDF export failed: {exc}")

    _write_zip_patches_leaderboard(game_results, players)


if __name__ == "__main__":
    main()
