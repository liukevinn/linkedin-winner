
#Version A + B


from __future__ import annotations
import re
from typing import Optional


def parse_score(raw) -> Optional[float]:
    """
    Convert any score representation to a float (seconds or raw numeric).

    Handles: int, float, "1:23", "1:23:45", "2m 14s", "2m", "45 sec", "45", None.
    Returns None for missing / unparseable / DNS values.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)

    s = str(raw).strip().lower()
    if not s or s in ("-", "n/a", "none", "dns", "dnf", ""):
        return None
    if s.startswith("banned:"):
        return None

    # "1:23" or "1:23:45"
    m = re.fullmatch(r"(\d+):(\d{2})(?::(\d{2}))?", s)
    if m:
        h, mn, sec = m.group(1), m.group(2), m.group(3)
        if sec is not None:
            return int(h) * 3600 + int(mn) * 60 + int(sec)
        return int(h) * 60 + int(mn)

    # "2m 14s" or "2m14s"
    m = re.fullmatch(r"(\d+)\s*m\s*(\d+)\s*s?", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))

    # "45s" / "45 sec" / "45 seconds"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)", s)
    if m:
        return float(m.group(1))

    # "2m" / "2 min" / "2 minutes"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)", s)
    if m:
        return float(m.group(1)) * 60

    # Leading number with possible trailing noise ("45 clues", etc.)
    m = re.match(r"^(\d+(?:\.\d+)?)", s)
    if m:
        return float(m.group(1))

    return None


def _fmt_pts(pts: float) -> str:
    rounded = round(pts, 2)
    return str(int(rounded)) if rounded == int(rounded) else f"{rounded:g}"


def rank_players(
    scores: dict[str, Optional[float]],
    direction: str,
    n_total: int,
) -> dict[str, float]:
    """
    Assign rank-points to a single game.

    Points scale: 1st earns n_total, last earns 1, DNS earns 0.
    Ties receive the average of the tied ranks' points.

    Args:
        scores:    {player: parsed_score_or_None}
        direction: "lower_is_better" | "higher_is_better"
        n_total:   total number of players in the competition
    """
    valid = {p: s for p, s in scores.items() if s is not None}
    points: dict[str, float] = {p: 0.0 for p in scores}

    if not valid:
        return points

    reverse = direction == "higher_is_better"
    ordered = sorted(valid, key=lambda p: valid[p], reverse=reverse)

    i = 0
    while i < len(ordered):
        # Collect all players tied at this score
        tied_score = valid[ordered[i]]
        j = i
        while j < len(ordered) and valid[ordered[j]] == tied_score:
            j += 1

        # Ranks i+1 … j (1-indexed from top) earn points n-i … n-j+1
        tied_group = ordered[i:j]
        slot_points = [n_total - k for k in range(i, j)]
        avg = sum(slot_points) / len(slot_points)
        for p in tied_group:
            points[p] = avg

        i = j

    return points


def compute_standings(
    game_results: dict[str, dict[str, object]],
    game_directions: dict[str, str],
    players: list[str],
) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    """
    Return (per_game_points, totals).

    per_game_points: {game: {player: pts}}
    totals:          {player: total_pts}
    """
    n = len(players)
    per_game: dict[str, dict[str, float]] = {}
    totals: dict[str, float] = {p: 0.0 for p in players}

    for game, raw_scores in game_results.items():
        direction = game_directions.get(game, "lower_is_better")
        parsed = {p: parse_score(raw_scores.get(p)) for p in players}
        gpts = rank_players(parsed, direction, n)
        per_game[game] = gpts
        for p, pts in gpts.items():
            totals[p] += pts

    return per_game, totals

