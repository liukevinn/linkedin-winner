# CLAUDE.md — linkedin-winner

## Project overview

A daily LinkedIn Games leaderboard calculator for a fixed friend group. Scrapes LinkedIn via Playwright, computes rank-based points across games, renders a styled PNG card, copies it to the macOS clipboard, and opens the "Touse" iMessage groupchat so the user can paste and send manually.

## Repo layout

```
linkedin_games_daily/
  config.py      # player names, active game URLs, score directions, manual fallback scores
  main.py        # CLI entry point, table rendering, PNG generation, clipboard + Messages
  scraper.py     # Playwright async scraper for LinkedIn leaderboards
  scoring.py     # parse_score(), rank_players(), compute_standings()
  requirements.txt
  README.md
```

Generated output files (`zip_patches_YYYY-MM-DD.png`) are gitignored.

## Running

```bash
cd linkedin_games_daily
python main.py              # scrape LinkedIn (default)
python main.py --manual     # use MANUAL_RESULTS from config.py
python main.py --debug      # scrape + save raw HTML to /tmp/
python main.py --players 'Kevin Liu' 'Daniel Suh'
```

LinkedIn credentials go in `linkedin_games_daily/.env`:
```
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=yourpassword
```

Session is persisted to `~/.linkedin_games_session` so login only happens once.

## Active games

Currently only `zip` and `patches` are active in `config.py`. Other games (pinpoint, queens, crossclimb, tango, mini_sudoku) are commented out. To re-enable, uncomment in `GAME_URLS` and `GAME_SCORE_DIRECTIONS`.

## Scoring

- Rank-based points: 1st earns N pts, 2nd earns N-1, …, last earns 1, DNS earns 0 (N = total players).
- Ties share the average of the tied ranks' point slots.
- `compute_standings()` in `scoring.py` returns `(per_game_pts, totals)`.
- All active games use `lower_is_better` (faster time = better).

## Players

```python
PLAYER_NAMES = ["Kevin Liu", "Daniel Suh", "Aiden Tauro", "Eric Guan", "Kaden Chien", "Evan Zhong", "Matthew Lu"]
```

Names are case-sensitive. `--players` CLI arg must match exactly.

## Scraper notes

LinkedIn has a lazy-rendering bug: after clicking "See full leaderboard" or "See more", only the visible rows are actually populated in the DOM. Fix: `_sweep_top_to_bottom()` scrolls the leaderboard container 250 px at a time with 120 ms delays, forcing all intersection observers to fire before reading rows. This sweep runs after the initial open and after every "See more" click (up to 100 iterations).

The logged-in user appears as "You" in the leaderboard — resolved to real name via the profile image `alt` attribute in the same container.

## PNG card

`_build_leaderboard_html()` generates a styled HTML card (440 px wide, LinkedIn blue `#0a66c2` header, medal emoji ranks, `#fffbeb` highlight for 1st place, winner footer). `_render_png()` screenshots the `.card` element via Playwright at `476×800` viewport. Output: `zip_patches_YYYY-MM-DD.png`.

## Clipboard + Messages

After PNG is saved, `_copy_image_to_clipboard()` compiles and runs a Swift snippet using `NSPasteboard.writeObjects([NSImage])` — this puts the image in the clipboard in the same multi-format way a manual Cmd+C would. Then AppleScript opens Messages and navigates directly to the "Touse" groupchat via `open theChat`. The user pastes (Cmd+V) and sends manually.

Do not automate the actual send — previous attempts caused the image to load indefinitely in Messages without sending. Manual paste works reliably.

## Key constraints

- Do not automate sending the iMessage — only open the chat and copy to clipboard.
- Do not add PDF or txt leaderboard generation — PNG only.
- Console must use `no_color=True, highlight=False, width=160` to keep output plain and untruncated.
- Do not add `record=True` to Console unless PDF export is re-introduced.
