# LinkedIn Games Daily

Determines the best overall LinkedIn Games player for a single day.
Run it once, get a winner, done — no database, no history.

## Setup

```bash
cd linkedin_games_daily
pip install rich                   # minimum requirement
# pip install playwright && playwright install chromium   # only for --scrape
```

## Quick start

1. **Edit `config.py`** — add your players and today's scores (see below).
2. **Run:**

```bash
python main.py               # manual mode (default)
python main.py --manual      # same as above
python main.py --scrape      # attempt Playwright scraping
python main.py --players Kevin Alex   # head-to-head subset
```

---

## Editing player names

Open `config.py` and change the list:

```python
PLAYER_NAMES = ["Kevin", "Alex", "Ryan", "Sam"]
```

Names are case-sensitive and must match exactly when using `--players`.

---

## Pasting manual results

Before each daily run, fill in `MANUAL_RESULTS` in `config.py`:

```python
MANUAL_RESULTS = {
    "pinpoint": {
        "Kevin": "1:23",   # 1 min 23 sec
        "Alex":  "1:41",
        "Ryan":  None,     # did not play → 0 points
    },
    "queens": {
        "Kevin": 48,       # raw seconds
        "Alex":  55,
        "Ryan":  44,
    },
    ...
}
```

**Accepted score formats:**

| Input | Interpreted as |
|-------|---------------|
| `"1:23"` | 1 min 23 sec (83 s) |
| `"1:23:45"` | 1 hr 23 min 45 sec |
| `"2m 14s"` | 2 min 14 sec (134 s) |
| `"45 sec"` | 45 seconds |
| `45` | 45 (treated as seconds) |
| `None` | Did not play — earns 0 pts |

---

## How scoring works

### Points per game

Each game is scored independently using rank-based points:

| Finish | Points (N players) |
|--------|-------------------|
| 1st    | N                 |
| 2nd    | N − 1             |
| 3rd    | N − 2             |
| …      | …                 |
| Last   | 1                 |
| DNS    | 0 (did not play)  |

Only players with a recorded score are ranked. DNS players always earn 0 and do not affect other players' point totals.

### Tie-breaking

Tied players share the **average** of the points they would have earned individually.

Example — 5 players, Zip game:

```
Kaden  0:03  → sole 1st place          → 5 pts
Kevin  0:04  ┐
Daniel 0:04  ├ 4-way tie for 2nd–5th   → avg(4+3+2+1)/4 = 2.5 pts each
Aiden  0:04  │
Eric   0:04  ┘
```

The next distinct rank after a tie group picks up where the group left off. In the example above, no one is ranked 3rd, 4th, or 5th individually — the tie consumed all four of those slots.

### Overall winner

Each player's points are summed across all games. The highest total wins.

Worked example (5-player run):

```
              Pinpoint  Queens  Climb  Tango  Zip   Sudoku  Patches  Total
Kevin Liu       3.5       5       3      5     2.5    4       4.5     27.5
Eric Guan        0        4       0      4     2.5    5       2.5      18
Kaden Chien     3.5       0       4      0     5      0       4.5      17
Daniel Suh      3.5       0       5      0     2.5    0       2.5      13.5
Aiden Tauro     3.5       0       0      0     2.5    0       1         7
```

- Pinpoint: Kevin/Daniel/Aiden/Kaden tied 1st (4-way) → avg(5+4+3+2)/4 = 3.5 each; Eric DNS → 0
- Queens: Kevin 1st → 5, Eric 2nd → 4; rest DNS → 0
- Climb: Daniel 1st → 5, Kaden 2nd → 4, Kevin 3rd → 3; rest DNS → 0
- Patches: Kevin/Kaden tied 1st → avg(5+4)/2 = 4.5 each; Daniel/Eric tied 3rd → avg(3+2)/2 = 2.5 each; Aiden 5th → 1

---

## Scraping (optional)

```bash
python main.py --scrape
```

- Requires `playwright` and a Chromium install.
- Opens a visible browser window so you can log in to LinkedIn if your session has expired. Your session is saved to `~/.linkedin_games_session` for future runs.
- Selectors are best-effort — LinkedIn's DOM changes without notice.
- Any game where scraping returns no scores automatically falls back to `MANUAL_RESULTS`.
- Does **not** bypass login, captchas, or rate limits.

---

## Score directions

All games default to `lower_is_better` (faster = better).
If a future game rewards a higher score, update `GAME_SCORE_DIRECTIONS` in `config.py`:

```python
GAME_SCORE_DIRECTIONS = {
    "some_future_game": "higher_is_better",
    ...
}
```
