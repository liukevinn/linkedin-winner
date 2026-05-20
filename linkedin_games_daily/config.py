"""
PLAYER_NAMES  — edit once to match your friend group.
MANUAL_RESULTS — only needed if scraping fails (--manual mode).
                 Paste scores here as a fallback.
"""

PLAYER_NAMES = ["Kevin Liu", "Daniel Suh", "Aiden Tauro", "Eric Guan", "Kaden Chien", "Evan Zhong", "Matthew Lu"]

# Sentinel value stored in game_results when a player used hints (patches only).
# parse_score() treats this as None (0 pts); display layers check for it explicitly.
HINT_BAN_SENTINEL = "BANNED:hint"

GAME_URLS = {
    #"pinpoint":   "https://www.linkedin.com/games/pinpoint/results",
    #"queens":     "https://www.linkedin.com/games/queens/results",
    #"crossclimb": "https://www.linkedin.com/games/crossclimb/results",
    #"tango":      "https://www.linkedin.com/games/tango/results",
    "zip":        "https://www.linkedin.com/games/zip/results",
    #"mini_sudoku":"https://www.linkedin.com/games/mini-sudoku/results",
    "patches":    "https://www.linkedin.com/games/patches/results",
}

# All LinkedIn puzzle games reward speed, so lower completion time = better.
GAME_SCORE_DIRECTIONS = {
    #"pinpoint":   "lower_is_better",
    #"queens":     "lower_is_better",
    #"crossclimb": "lower_is_better",
    #"tango":      "lower_is_better",
    "zip":        "lower_is_better",
    #"mini_sudoku":"lower_is_better",
    "patches":    "lower_is_better",
}

# ---------------------------------------------------------------------------
# Paste today's scores here before running:  python main.py --manual
#
# Accepted score formats:
#   "1:23"    → 1 min 23 sec
#   "2m 14s"  → 2 min 14 sec
#   "45 sec"  → 45 sec
#   45        → 45 (treated as seconds or raw numeric)
#   None      → did not play (DNS) — earns 0 points
# ---------------------------------------------------------------------------
MANUAL_RESULTS = {
    # "pinpoint": {
    #     "Kevin Liu":   None,
    #     "Daniel Suh":  None,
    #     "Aiden Tauro": None,
    #     "Eric Guan":   None,
    #     "Kaden Chien": None,
    #     "Evan Zhong": None,
    #     "Matthew Lu": None,
    # },
    # "queens": {
    #     "Kevin Liu":   None,
    #     "Daniel Suh":  None,
    #     "Aiden Tauro": None,
    #     "Eric Guan":   None,
    #     "Kaden Chien": None,
    #     "Evan Zhong": None,
    #     "Matthew Lu": None,
    # },
    # "crossclimb": {
    #     "Kevin Liu":   None,
    #     "Daniel Suh":  None,
    #     "Aiden Tauro": None,
    #     "Eric Guan":   None,
    #     "Kaden Chien": None,
    #     "Evan Zhong": None,
    #     "Matthew Lu": None,
    # },
    # "tango": {
    #     "Kevin Liu":   None,
    #     "Daniel Suh":  None,
    #     "Aiden Tauro": None,
    #     "Eric Guan":   None,
    #     "Kaden Chien": None,
    #     "Evan Zhong": None,
    #     "Matthew Lu": None,
    # },
    "zip": {
        "Kevin Liu":   None,
        "Daniel Suh":  None,
        "Aiden Tauro": None,
        "Eric Guan":   None,
        "Kaden Chien": None,
        "Evan Zhong": None,
        "Matthew Lu": None,
        },
    # "mini_sudoku": {
    #     "Kevin Liu":   None,
    #     "Daniel Suh":  None,
    #     "Aiden Tauro": None,
    #     "Eric Guan":   None,
    #     "Kaden Chien": None,
    #     "Evan Zhong": None,
    #     "Matthew Lu": None,
    # },
    "patches": {
        "Kevin Liu":   None,
        "Daniel Suh":  None,
        "Aiden Tauro": None,
        "Eric Guan":   None,
        "Kaden Chien": None,
        "Evan Zhong": None,
        "Matthew Lu": None,
    },
}

# Path where Playwright saves your LinkedIn session between runs.
SCRAPER_SESSION_DIR = "~/.linkedin_games_session"
##TEST PR