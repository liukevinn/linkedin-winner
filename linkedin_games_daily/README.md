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

For each game:

1. Only players with a valid score are ranked.
2. Best player earns **N** points, where N = total players in today's run.
3. Each subsequent rank earns one fewer point (2nd → N−1, last → 1).
4. Players who did not play earn **0 points**.
5. **Ties** share the points equally:
   - Two players tied for 1st with N=4: they split 4+3 = **3.5 pts each**.
   - The next distinct rank continues below them (3rd in this case).

The overall winner is the player with the highest total across all games.

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
