"""
Playwright scraper for LinkedIn Games leaderboards.

Uses your real Chrome profile so no LinkedIn login is needed.
If Chrome is open, the script asks you to quit it (Cmd+Q), scrapes all games,
then reopens Chrome automatically.

Flow per game:
  1. Navigate to the game URL.
  2. Click "See results"              (button.games-share-footer__share-btn)
  3. Click "See full leaderboard"     (button[aria-label="See full leaderboard"])
  4. Read every leaderboard row:
       name  →  .pr-connections-leaderboard-player__name
       score →  .pr-connections-leaderboard-player__score
  5. Match to PLAYER_NAMES.
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import time
from typing import Optional

from config import GAME_URLS, PLAYER_NAMES, SCRAPER_SESSION_DIR

# ---------------------------------------------------------------------------
# Selectors (confirmed from live LinkedIn Games HTML)
# ---------------------------------------------------------------------------
SEE_RESULTS_BTN      = "button.games-share-footer__share-btn"
FULL_LEADERBOARD_BTN = 'button[aria-label="See full leaderboard"]'
PLAYER_CONTAINER     = '[class*="pr-connections-leaderboard-player__container"]'
PLAYER_NAME          = ".pr-connections-leaderboard-player__name"
PLAYER_SCORE         = ".pr-connections-leaderboard-player__score"


# ---------------------------------------------------------------------------
# Chrome helpers
# ---------------------------------------------------------------------------

def _chrome_user_data_dir() -> Optional[str]:
    """Return Chrome's default profile directory, or None if not found."""
    sys = platform.system()
    if sys == "Darwin":
        path = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    elif sys == "Windows":
        path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    else:
        path = os.path.expanduser("~/.config/google-chrome")
    return path if os.path.isdir(path) else None


def _chrome_is_running() -> bool:
    try:
        if platform.system() == "Darwin":
            r = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True)
        else:
            r = subprocess.run(["pgrep", "-xi", "chrome"], capture_output=True)
        return r.returncode == 0
    except Exception:
        return False


def _reopen_chrome() -> None:
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", "-a", "Google Chrome"])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Per-game scrape
# ---------------------------------------------------------------------------

async def _scrape_game(
    page,
    game: str,
    url: str,
    players: list[str],
    debug: bool,
) -> dict[str, Optional[str]]:
    results: dict[str, Optional[str]] = {p: None for p in players}

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2_500)

        # Step 1 — "See results"
        btn = page.locator(SEE_RESULTS_BTN).first
        await btn.wait_for(state="visible", timeout=10_000)
        await btn.click()
        await page.wait_for_timeout(2_000)

        # Step 2 — "See full leaderboard"
        full_btn = page.locator(FULL_LEADERBOARD_BTN).first
        await full_btn.wait_for(state="visible", timeout=10_000)
        await full_btn.click()
        await page.wait_for_timeout(1_500)

        # Step 3 — read every player row
        containers = await page.query_selector_all(PLAYER_CONTAINER)
        scraped: dict[str, str] = {}
        for container in containers:
            name_el  = await container.query_selector(PLAYER_NAME)
            score_el = await container.query_selector(PLAYER_SCORE)
            if not name_el:
                continue
            name  = (await name_el.inner_text()).strip()
            score = (await score_el.inner_text()).strip() if score_el else None
            if name and score:
                scraped[name] = score

        # Step 4 — match to PLAYER_NAMES (exact, then first-name fallback)
        for player in players:
            if player in scraped:
                results[player] = scraped[player]
            else:
                first = player.split()[0].lower()
                for scraped_name, score in scraped.items():
                    if scraped_name.lower().startswith(first):
                        results[player] = score
                        break

        if debug:
            path = f"/tmp/linkedin_debug_{game}.html"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(await page.content())
            print(f"    [debug] HTML → {path}")

    except Exception as exc:
        print(f"    [error] {exc}")
        if debug:
            try:
                path = f"/tmp/linkedin_debug_{game}.html"
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(await page.content())
                print(f"    [debug] HTML → {path}")
            except Exception:
                pass

    found = sum(v is not None for v in results.values())
    hits  = ", ".join(f"{p.split()[0]}={v}" for p, v in results.items() if v)
    print(f"    {found}/{len(players)}" + (f"  ({hits})" if hits else "  — no scores found"))
    return results


# ---------------------------------------------------------------------------
# Browser launch  (prefer real Chrome profile, fall back to saved session)
# ---------------------------------------------------------------------------

async def _run(players: list[str], debug: bool) -> dict[str, dict[str, Optional[str]]]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise ImportError(
            "Playwright not installed.\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        ) from exc

    chrome_dir      = _chrome_user_data_dir()
    chrome_was_open = _chrome_is_running() if chrome_dir else False

    # If Chrome is open we need to close it so Playwright can use the profile
    if chrome_was_open:
        print(
            "\n[scraper] Scraper will use your existing Chrome/LinkedIn session.\n"
            "          Please quit Chrome now (Cmd+Q) — it will reopen automatically.\n",
            flush=True,
        )
        while _chrome_is_running():
            await asyncio.sleep(1)
        print("[scraper] Chrome closed. Starting scraper…\n")
        await asyncio.sleep(1)  # let Chrome fully release its profile lock

    all_results: dict[str, dict[str, Optional[str]]] = {}

    async with async_playwright() as pw:
        # Launch Chrome with the real user profile (cookies + LinkedIn session intact)
        if chrome_dir:
            try:
                ctx = await pw.chromium.launch_persistent_context(
                    chrome_dir,
                    channel="chrome",
                    headless=False,
                    args=[
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-session-crashed-bubble",
                    ],
                    viewport={"width": 1280, "height": 900},
                )
            except Exception as exc:
                print(f"[scraper] Could not launch with Chrome profile ({exc}), "
                      "falling back to saved session.")
                chrome_dir = None

        if not chrome_dir:
            session_dir = os.path.expanduser(SCRAPER_SESSION_DIR)
            ctx = await pw.chromium.launch_persistent_context(
                session_dir,
                headless=False,
                args=["--no-sandbox"],
                viewport={"width": 1280, "height": 900},
            )

        page = await ctx.new_page()

        # Sanity-check: make sure we're logged in
        await page.goto("https://www.linkedin.com/feed/", timeout=30_000)
        await page.wait_for_timeout(2_000)
        if any(x in page.url for x in ("login", "authwall", "signup", "checkpoint")):
            raise RuntimeError(
                "Not logged in to LinkedIn.\n"
                "Make sure you are logged in to LinkedIn in Chrome and try again."
            )

        for game, url in GAME_URLS.items():
            print(f"\n  [{game}]")
            all_results[game] = await _scrape_game(page, game, url, players, debug)

        await ctx.close()

    if chrome_was_open:
        print("\n[scraper] Reopening Chrome…")
        _reopen_chrome()

    return all_results


def scrape_games(
    players: list[str] | None = None,
    debug: bool = False,
) -> dict[str, dict[str, Optional[str]]]:
    """Synchronous entry point called by main.py."""
    return asyncio.run(_run(players or PLAYER_NAMES, debug))
