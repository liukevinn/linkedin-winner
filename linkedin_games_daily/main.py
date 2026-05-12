#!/usr/bin/env python3
"""LinkedIn Games Daily Winner Calculator."""

from __future__ import annotations
import argparse
import sys
from datetime import date

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from config import PLAYER_NAMES, GAME_SCORE_DIRECTIONS, MANUAL_RESULTS
from scoring import compute_standings, parse_score, _fmt_pts

console = Console()

_MEDALS = {1: "[bold gold1]1st ★[/]", 2: "[bold white]2nd[/]", 3: "[bold #cd7f32]3rd[/]"}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_scraped(players: list[str], debug: bool) -> dict[str, dict[str, object]]:
    from scraper import scrape_games
    console.print("[cyan]Scraping LinkedIn Games leaderboards…[/]")
    scraped = scrape_games(players, debug=debug)

    # For any game where scraping returned all None, fall back to MANUAL_RESULTS
    merged: dict[str, dict[str, object]] = {}
    for game in GAME_URLS_ORDER:
        live = scraped.get(game, {})
        has_data = any(v is not None for v in live.values())
        if has_data:
            merged[game] = live
        elif game in MANUAL_RESULTS:
            console.print(f"  [yellow]{game}: no scraped scores — using MANUAL_RESULTS fallback[/]")
            merged[game] = {p: MANUAL_RESULTS[game].get(p) for p in players}
        else:
            merged[game] = {p: None for p in players}
    return merged


def _load_manual(players: list[str]) -> dict[str, dict[str, object]]:
    return {
        game: {p: MANUAL_RESULTS.get(game, {}).get(p) for p in players}
        for game in MANUAL_RESULTS
    }


# Keep game ordering stable
from config import GAME_URLS
GAME_URLS_ORDER = list(GAME_URLS.keys())


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _rank_label(rank: int) -> str:
    return _MEDALS.get(rank, str(rank))


def _render_per_game(
    game_results: dict[str, dict[str, object]],
    per_game_pts: dict[str, dict[str, float]],
    players: list[str],
) -> None:
    console.print()
    console.rule("[bold cyan]Per-Game Rankings[/]")

    for game, raw_scores in game_results.items():
        gpts = per_game_pts[game]

        table = Table(
            title=f"[bold]{game.replace('_', ' ').upper()}[/]",
            box=box.ROUNDED,
            header_style="bold cyan",
            show_lines=True,
            min_width=50,
        )
        table.add_column("Rank",   justify="center", width=7)
        table.add_column("Player", min_width=14)
        table.add_column("Score",  justify="right",  min_width=10)
        table.add_column("Pts",    justify="right",  min_width=6)

        def sort_key(p: str):
            pts = gpts[p]
            played = 0 if raw_scores.get(p) is None else 1
            return (-played, -pts)

        sorted_players = sorted(players, key=sort_key)

        prev_pts: float | None = None
        visual_rank = 0
        display_pos = 0
        for player in sorted_players:
            display_pos += 1
            raw = raw_scores.get(player)
            pts = gpts[player]

            if pts != prev_pts:
                visual_rank = display_pos
            prev_pts = pts

            if raw is None:
                table.add_row("[dim]—[/]", f"[dim]{player}[/]", "[dim]DNS[/]", "[dim]0[/]")
            else:
                table.add_row(_rank_label(visual_rank), player, str(raw), _fmt_pts(pts))

        console.print(table)
        console.print()


def _render_standings(
    per_game_pts: dict[str, dict[str, float]],
    totals: dict[str, float],
    players: list[str],
    games: list[str],
) -> None:
    console.rule("[bold cyan]Overall Standings[/]")

    table = Table(box=box.ROUNDED, header_style="bold magenta", show_lines=True)
    table.add_column("Rank",   justify="center", width=7)
    table.add_column("Player", min_width=14)
    for game in games:
        table.add_column(game.replace("_", " ").title(), justify="right", min_width=9)
    table.add_column("TOTAL", justify="right", min_width=7, style="bold")

    sorted_players = sorted(players, key=lambda p: -totals[p])

    prev_total: float | None = None
    visual_rank = 0
    display_pos = 0
    for player in sorted_players:
        display_pos += 1
        total = totals[player]
        if total != prev_total:
            visual_rank = display_pos
        prev_total = total

        row: list[str] = [_rank_label(visual_rank), player]
        for game in games:
            pts = per_game_pts[game].get(player, 0.0)
            row.append("[dim]0[/]" if pts == 0 else _fmt_pts(pts))
        row.append(_fmt_pts(total))
        table.add_row(*row)

    console.print(table)
    console.print()


def _render_winner(totals: dict[str, float], players: list[str]) -> None:
    top = max(totals[p] for p in players)
    winners = [p for p in players if totals[p] == top]
    pts_label = _fmt_pts(top)

    if len(winners) == 1:
        msg = Text(f"★  {winners[0]}  ★", style="bold gold1", justify="center")
        panel = Panel(msg, title="[bold]Today's Winner[/]", subtitle=f"{pts_label} pts",
                      border_style="gold1", padding=(1, 6))
    else:
        msg = Text(f"⭐  {'  &  '.join(winners)}  ⭐", style="bold gold1", justify="center")
        panel = Panel(msg, title="[bold]It's a Tie![/]", subtitle=f"Tied at {pts_label} pts",
                      border_style="gold1", padding=(1, 4))

    console.print(panel)


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
        console.print(f"[red]Unknown player(s): {unknown}\nValid: {PLAYER_NAMES}[/]")
        sys.exit(1)

    today = date.today().strftime("%A, %B %d %Y")
    mode_label = "manual" if args.manual else "scrape"
    console.print(Panel(
        f"[bold cyan]LinkedIn Games Daily[/]\n"
        f"[dim]{today}  ·  {mode_label} mode  ·  {len(players)} players[/]",
        border_style="cyan",
    ))

    if args.manual:
        game_results = _load_manual(players)
    else:
        try:
            game_results = _load_scraped(players, debug=args.debug)
        except Exception as exc:
            console.print(f"\n[red]Scraping failed: {exc}[/]")
            console.print("[yellow]Tip: run with --manual and paste scores into MANUAL_RESULTS in config.py[/]")
            sys.exit(1)

    if not game_results:
        console.print("[red]No game data. Try --manual and fill in MANUAL_RESULTS in config.py.[/]")
        sys.exit(1)

    games = [g for g in GAME_URLS_ORDER if g in game_results]
    per_game_pts, totals = compute_standings(game_results, GAME_SCORE_DIRECTIONS, players)

    _render_per_game(game_results, per_game_pts, players)
    _render_standings(per_game_pts, totals, players, games)
    _render_winner(totals, players)


if __name__ == "__main__":
    main()
