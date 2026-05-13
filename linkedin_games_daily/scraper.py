"""
Playwright scraper for LinkedIn Games leaderboards.

Credentials are read from .env (LINKEDIN_EMAIL / LINKEDIN_PASSWORD).
A persistent browser session is saved to SCRAPER_SESSION_DIR so login only
happens once (or whenever LinkedIn expires the session).

Flow per game:
  1. Navigate directly to /games/<game>/results  (skips "See results" entirely).
  2. Click "See full leaderboard"  (aria-label or text, works across all games).
  3. Click "See more" until all entries are loaded.
  4. Read every leaderboard row:
       name  →  .pr-connections-leaderboard-player__name
       score →  .pr-connections-leaderboard-player__score
  5. Match to PLAYER_NAMES.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
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
# Credentials
# ---------------------------------------------------------------------------

def _load_credentials() -> tuple[str, str]:
    """Load LINKEDIN_EMAIL and LINKEDIN_PASSWORD from .env."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

    email    = os.environ.get("LINKEDIN_EMAIL", "")
    password = os.environ.get("LINKEDIN_PASSWORD", "")

    if not email or not password or email == "your_email@example.com":
        raise RuntimeError(
            "LinkedIn credentials not set.\n"
            "Edit .env and fill in LINKEDIN_EMAIL and LINKEDIN_PASSWORD."
        )
    return email, password


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def _login(page, email: str, password: str) -> None:
    """Fill in the LinkedIn login form and wait for the feed."""
    print("[scraper] Logging in to LinkedIn…", flush=True)
    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30_000)
    await page.wait_for_timeout(1_500)

    await page.fill('input[name="session_key"]', email)
    await page.fill('input[name="session_password"]', password)
    await page.click('button[type="submit"]')

    # Wait up to 60 s — covers normal login AND any 2FA / CAPTCHA the user
    # needs to complete in the visible browser window.
    for _ in range(60):
        if "/feed" in page.url or "/games" in page.url:
            print("[scraper] Logged in.\n", flush=True)
            return
        if any(x in page.url for x in ("checkpoint", "challenge", "verification")):
            print(
                "[scraper] LinkedIn is asking for verification.\n"
                "          Complete it in the browser window — script will continue automatically.",
                flush=True,
            )
        await asyncio.sleep(1)

    raise RuntimeError("Login timed out. Check your credentials in .env.")


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

        # URLs already point to /results — no "See results" click needed.
        # Wait for the leaderboard or the "See full leaderboard" button to appear.
        try:
            await page.wait_for_function(
                '() => !!document.querySelector(".pr-connections-leaderboard-player__name") || '
                '!!document.querySelector("[aria-label=\'See full leaderboard\']") || '
                '[...document.querySelectorAll("button")].some('
                '  el => el.offsetParent !== null && el.textContent.trim() === "See full leaderboard"'
                ')',
                timeout=12_000,
            )
        except Exception:
            pass

        # Step 1 — "See full leaderboard"
        for full_lb_sel in [
            FULL_LEADERBOARD_BTN,
            'button:has-text("See full leaderboard")',
        ]:
            try:
                full_btn = page.locator(full_lb_sel).first
                await full_btn.scroll_into_view_if_needed(timeout=3_000)
                if await full_btn.is_visible(timeout=2_000):
                    await full_btn.click()
                    await page.wait_for_timeout(1_500)
                    break
            except Exception:
                continue

        # Step 3 — scroll through the full leaderboard, clicking "See more" until
        # all entries are loaded or all target players have been found.
        # LinkedIn's leaderboard lives in its own scrollable container, so we
        # must scroll that container (not just the window) to expose the button.
        LEADERBOARD_SCROLL_SELS = [
            '[class*="pr-connections-leaderboard__list"]',
            '[class*="leaderboard__list"]',
            '[class*="leaderboard-list"]',
        ]

        for _ in range(100):
            # Scroll the window and every candidate leaderboard container to
            # the bottom so the "See more" button becomes reachable.
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            for sel in LEADERBOARD_SCROLL_SELS:
                await page.evaluate(
                    f"(() => {{ const el = document.querySelector({repr(sel)}); "
                    f"if (el) el.scrollTo(0, el.scrollHeight); }})()"
                )
            await page.wait_for_timeout(400)

            try:
                more_btn = page.locator('button:has-text("See more")').first
                await more_btn.scroll_into_view_if_needed(timeout=2_000)
                if await more_btn.is_visible(timeout=1_500):
                    await more_btn.click()
                    await page.wait_for_timeout(900)
                else:
                    break
            except Exception:
                break

        # Step 4 — read every player row
        containers = await page.query_selector_all(PLAYER_CONTAINER)
        scraped: dict[str, str] = {}
        for container in containers:
            name_el  = await container.query_selector(PLAYER_NAME)
            score_el = await container.query_selector(PLAYER_SCORE)
            if not name_el:
                continue
            name  = (await name_el.inner_text()).strip()
            score = (await score_el.inner_text()).strip() if score_el else None

            # LinkedIn shows the logged-in user as "You" — resolve to real name
            # via the profile image's alt attribute in the same container.
            if name == "You":
                img = await container.query_selector(
                    ".pr-connections-leaderboard-player__image-container img"
                )
                if img:
                    alt = await img.get_attribute("alt")
                    if alt:
                        name = alt

            if name and score:
                scraped[name] = score

        # Step 5 — match to PLAYER_NAMES (exact, then first-name fallback)
        for player in players:
            if player in scraped:
                results[player] = scraped[player]
            else:
                first = player.split()[0].lower()
                for scraped_name, score in scraped.items():
                    if scraped_name.lower().startswith(first):
                        results[player] = score
                        break

        # Always save HTML when no scores found so we can inspect what LinkedIn showed
        found_count = sum(v is not None for v in results.values())
        if debug or found_count == 0:
            path = f"/tmp/linkedin_debug_{game}.html"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(await page.content())
            if found_count == 0:
                print(f"    [debug] 0 scores — page saved to {path}")

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
# Browser / session management
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

    email, password = _load_credentials()
    session_dir = os.path.expanduser(SCRAPER_SESSION_DIR)
    all_results: dict[str, dict[str, Optional[str]]] = {}

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            session_dir,
            headless=False,
            args=["--no-sandbox"],
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        # Check if already logged in
        await page.goto("https://www.linkedin.com/feed/", timeout=30_000)
        await page.wait_for_timeout(2_000)

        if any(x in page.url for x in ("login", "authwall", "signup", "checkpoint")):
            await _login(page, email, password)

        for game, url in GAME_URLS.items():
            print(f"\n  [{game}]")
            all_results[game] = await _scrape_game(page, game, url, players, debug)

        await ctx.close()

    return all_results


def scrape_games(
    players: list[str] | None = None,
    debug: bool = False,
) -> dict[str, dict[str, Optional[str]]]:
    """Synchronous entry point called by main.py."""
    return asyncio.run(_run(players or PLAYER_NAMES, debug))
