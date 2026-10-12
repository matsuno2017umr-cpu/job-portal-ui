# TinDog Auto-Swipe Bot

[Selenium](https://www.selenium.dev/) script for the **TinDog** practice app on [100 Days of Python](https://app.100daysofpython.dev/). It signs into the platform, opens your **personal TinDog URL**, and clicks **Like** until there are no more profiles or `MAX_LIKES` is reached.

> For learning purposes only. Use responsibly on your own account.

## Requirements

- Python 3.10+
- Google Chrome (ChromeDriver is installed automatically via `webdriver-manager`)

## Setup

```bash
cd tindog-bot
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your platform email and password
```

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TINDOG_PLATFORM_EMAIL` | Yes | Login email for app.100daysofpython.dev |
| `TINDOG_PLATFORM_PASSWORD` | Yes | Login password |
| `TINDOG_URL` | No | Personal TinDog URL; if omitted, read from admin profile page |
| `FACEBARK_EMAIL` | No | Mock Facebark email (default `bot@example.com`) |
| `FACEBARK_PASSWORD` | No | Mock Facebark password (default `anything`) |
| `HEADLESS` | No | Default `1`. Set `0` to show the browser |
| `MAX_LIKES` | No | Default `50` |
| `PAUSE_SECONDS` | No | Default `0.8` between likes |

Never commit `.env` or real passwords.

## Run

```bash
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)   # or use python-dotenv (loaded automatically)
python tindog_bot.py
```

## How it works

1. Sign in to the platform (`input#email`, `input#password`, `button[type='submit']`).
2. Read your personal URL from `input#tindog-url` on the admin page (or set `TINDOG_URL`) and open it once to bind the session.
3. Complete the **mock Facebark** form at `/services/tindog/fb-login` (`input#email`, `input#pass` — any values work).
4. Dismiss teaching popups (location, notifications, …) via their form buttons.
5. Click **`button.btn-like`** (injected after ~0.6–1.2s) until `MAX_LIKES` or no profiles remain.

## Selectors (reference)

| Step | Selector |
|------|----------|
| Platform email | `input#email` (login page) |
| Platform password | `input#password` |
| Sign in | `button[type='submit']` |
| Personal URL | `input#tindog-url` |
| Facebark email / pass | `input#email`, `input#pass` on `/services/tindog/fb-login` |
| Teaching popups | `.popup-overlay` → `button[type='submit']` or `.btn-primary` |
| Like | `button.btn-like` (`aria-label="Like"`) |
| Nope (not used) | `button.btn-nope` |

## Caveats

- **Personal URL + platform login** are both required; the token URL alone redirects to the marketing landing page until the platform session exists.
- **Facebark** must be completed once per browser session (Selenium uses the same-window `/fb-login` route instead of the popup).
- **Popups** (location, notifications, optional match overlay) block the Like button until dismissed.
- Like buttons appear **after a short JS delay**; the script waits up to 20s.
- Reset swipes from **Manage Tindog → Reset Tindog** when re-testing.
- Smoke-tested headless on Linux with Chrome 154; use `HEADLESS=0` locally if debugging.

## Smoke test (this repo)

From the project root after configuring `.env`:

```bash
cd tindog-bot && pip install -r requirements.txt && python tindog_bot.py
```

Check the printed like count and any “Stopping” reason in the log.
