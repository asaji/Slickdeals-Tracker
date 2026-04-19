# Slickdeals Tracker — Usage Guide

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [CLI Commands](#cli-commands)
4. [Configuration Reference](#configuration-reference)
5. [Hot Deals](#hot-deals)
6. [Category System](#category-system)
7. [Pushover Notifications](#pushover-notifications)
8. [Running Perpetually](#running-perpetually)
9. [Docker & UnRAID](#docker--unraid)
10. [Tips & Tricks](#tips--tricks)

---

## Installation

**Requirements:** Python 3.10+

```bash
git clone https://github.com/asaji/Slickdeals-Tracker.git
cd Slickdeals-Tracker
pip install -r requirements.txt
```

Dependencies installed: `requests`, `rich`, `click`, `pyyaml`

---

## Quick Start

```bash
# 1. Generate a config file
python main.py init

# 2. Edit config.yaml to match your interests
nano config.yaml

# 3. Run a one-shot check
python main.py run

# 4. Analyze deals for review scores and value verdicts
python main.py analyze

# 5. See today's hottest frontpage deals across all categories
python main.py hot

# 6. Watch continuously (polls on your configured interval)
python main.py run --watch
```

To preview the UI without a network connection, use the built-in demo data:

```bash
python main.py run --demo
python main.py analyze --demo
```

---

## CLI Commands

### `run` — Fetch and display new deals

```
python main.py run [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `config.yaml` | Path to a custom config file |
| `--watch`, `-w` | off | Keep running, polling on the configured interval |
| `--interval`, `-i` | from config | Override poll interval in minutes |
| `--demo` | off | Show sample deals without any network calls |

**Examples:**

```bash
# One-shot check with default config
python main.py run

# Poll every 15 minutes using a custom config
python main.py run --watch --interval 15 --config my_deals.yaml

# Preview the terminal UI offline
python main.py run --demo
```

---

### `analyze` — Fetch deals and score them

Runs every matching deal through the review analyzer: looks up the product
on its category's review authority (RTINGS, Tom's Hardware, NotebookCheck,
etc.), scores sentiment, factors in the discount depth, and issues a verdict.

```
python main.py analyze [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `config.yaml` | Path to a custom config file |
| `--demo` | off | Analyze sample TV deals offline |

**Verdicts:**

| Label | Meaning |
|-------|---------|
| `GREAT DEAL` | Score ≥ 8.0 **and** discount ≥ 25% |
| `GOOD DEAL` | Score ≥ 7.0 **and** discount ≥ 15% |
| `FAIR DEAL` | Score ≥ 6.0 **or** discount ≥ 20% |
| `SKIP` | Low sentiment or minimal discount |

> **Note on Apple / premium brands:** Apple products rarely exceed 20% off.
> If you track MacBooks or iPhones, lower `min_verdict_discount` in your
> config or set a search-specific `min_score: 0` to avoid everything
> being flagged SKIP.

---

### `hot` — Frontpage hot deals across all categories

```
python main.py hot [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `config.yaml` | Path to config file |
| `--watch`, `-w` | off | Keep polling on the configured interval |
| `--interval`, `-i` | from config | Override poll interval in minutes |
| `--demo` | off | Show sample hot deals offline |

```bash
python main.py hot                     # one-shot
python main.py hot --watch             # continuous
python main.py hot --watch --interval 20
python main.py hot --demo              # preview with sample data
```

---

### `history` — Browse past deals

Shows deals already saved in the local database, sorted by date.

```
python main.py history [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config`, `-c` | `config.yaml` | Path to config (used for `db_path`) |
| `--limit`, `-n` | `20` | How many recent deals to show |

```bash
python main.py history --limit 50
```

---

### `init` — Generate a fresh config

```
python main.py init [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | `config.yaml` | Where to write the config file |

```bash
python main.py init --output tvs_only.yaml
```

---

## Configuration Reference

The default config file is `config.yaml` in the project root.

```yaml
# How often to poll when running with --watch (minutes)
poll_interval_minutes: 30

# SQLite database path (relative to working directory, or absolute)
db_path: deals.db

# Max deals shown per search section in the table
max_deals_display: 20

# Set to true to also show previously-seen deals in the table
show_seen: false

# Pushover push notifications (optional — see Pushover section)
pushover:
  enabled: false
  api_token: ""          # your Pushover application token
  user_key: ""           # your Pushover user/group key
  min_verdict: "GOOD DEAL"   # only notify for this verdict or better
                             # choices: "GREAT DEAL", "GOOD DEAL", "FAIR DEAL"
  notify_on_run: false   # send notifications during `run` (without full analysis)
  max_per_check: 5       # cap notifications per poll cycle to avoid spam

searches:
  - name: TVs               # Display name — shown in headers and notifications
    category: TVs           # Maps to a built-in category profile (see below)
    query: TV               # Search term sent to Slickdeals
    keywords:               # At least one must match in title or summary
      - oled
      - qled
      - 4k
    exclude:                # Skip any deal containing these words
      - monitor
      - projector
    min_score: 10           # Minimum Slickdeals community vote count
```

### `searches` field reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable label used in output and notifications |
| `query` | Yes | Search term submitted to Slickdeals RSS |
| `category` | No | Category profile key (auto-detected from title if blank) |
| `keywords` | No | Whitelist — deal must match at least one |
| `exclude` | No | Blacklist — deal is dropped if any match |
| `min_score` | No | Minimum community upvote count (0 = all deals) |

---

## Hot Deals

The `hot` command monitors the Slickdeals **frontpage** and **popular** RSS feeds
with **no keyword filter**. Any deal the community has voted onto the front page
is eligible — TVs, laptops, vacuums, kitchen gadgets, SSDs, whatever. Being on
the frontpage is itself a quality signal: Slickdeals only promotes deals after
the community has heavily upvoted them.

### Quick start

```bash
# One-shot: show today's hottest deals with full review analysis
python main.py hot

# Preview with sample data (no network needed)
python main.py hot --demo

# Watch continuously, checking every 30 minutes
python main.py hot --watch

# Watch with a custom interval
python main.py hot --watch --interval 15
```

### Always-on hot deals inside `run --watch`

Enable `hot_deals` in your config to automatically include a hot deals pass
in every `run` or `run --watch` cycle — no separate command needed:

```yaml
hot_deals:
  enabled: true
  min_score: 0        # 0 = trust frontpage curation; raise to filter further
  max_display: 10
  run_analysis: true  # full RTINGS/Tom's Hardware/etc. lookup per deal
  notify: true        # push Pushover notifications for hot deals
  exclude:
    - "credit card"
    - "gift card"
```

Then just run the tracker as normal:

```bash
python main.py run --watch
# → checks your configured category searches, then appends a hot deals pass
```

### Configuration reference

| Field | Default | Description |
|-------|---------|-------------|
| `enabled` | `false` | Include hot deals in every `run`/`run --watch` cycle |
| `min_score` | `0` | Extra vote threshold on top of frontpage curation. `0` = accept all frontpage items. Set `50`–`100` for only truly viral deals |
| `max_display` | `10` | Max hot deals shown per check |
| `run_analysis` | `true` | Run full review analyzer on each hot deal (category auto-detected from title) |
| `notify` | `true` | Push Pushover notifications for hot deals (uses the main `pushover` credentials) |
| `exclude` | `[]` | Skip hot deals whose title/summary contains any of these strings |

### How it differs from regular searches

| | Regular `searches` | Hot Deals |
|---|---|---|
| **Keyword filter** | Required — deals must match at least one keyword | None — catches everything |
| **Category** | Explicit per-search | Auto-detected from deal title |
| **Source** | Search RSS + frontpage | Frontpage + popular RSS only |
| **Use case** | "I want TVs and SSDs" | "Show me anything the community loves right now" |
| **Score threshold** | Tunable per search | Single global `min_score` |

### Recommended exclude list

To cut down on noise from financial offers and gift cards:

```yaml
hot_deals:
  exclude:
    - "credit card"
    - "store card"
    - "gift card"
    - "amazon card"
    - "cash back offer"
    - "reward"
```

---

## Category System

Each search can declare a `category` that selects a profile controlling:

- **Brand patterns** used for model name extraction
- **Review authority** (RTINGS, Tom's Hardware, NotebookCheck, etc.)
- **Sentiment vocabulary** tuned to what matters for that product type
- **Spec extractor** that parses relevant fields from deal titles

### Available categories

| Category | Review Authority | Extracted Specs |
|----------|-----------------|-----------------|
| `TVs` | RTINGS | Size, Panel, Resolution, Refresh rate |
| `Monitors` | RTINGS | Size, Panel, Resolution, Refresh rate |
| `Laptops` | NotebookCheck | Screen size, RAM, Storage, CPU brand |
| `Headphones` | RTINGS | Type, ANC, Wireless |
| `Smartphones` | GSMArena | Storage, Network (5G/LTE) |
| `Tablets` | NotebookCheck | Screen size, Storage, Connectivity, Stylus |
| `GPUs` | Tom's Hardware | Chip model, VRAM |
| `CPUs` | Tom's Hardware | Series, Core count |
| `SSDs` | Tom's Hardware | Capacity, Interface, Form factor |
| `Cameras` | DPReview | Resolution (MP), Type, Sensor size |
| `Gaming` | Metacritic / IGN | Platform, Type |
| `Gaming Peripherals` | Tom's Hardware / PCMag | Device type, Wireless |
| `Smart Home` | The Verge / PCMag | Device type, Platform |
| `Appliances` | Wirecutter / Consumer Reports | Appliance type, Capacity |
| `Routers` | Tom's Hardware / SmallNetBuilder | WiFi standard, Type |
| `General` | Google / PCMag | (fallback for anything else) |

If `category` is omitted, the tracker auto-detects by matching deal title keywords
against each profile's keyword list. The profile with the most matches wins.

### Adding a custom search

```yaml
searches:
  - name: Standing Desks
    category: General        # no specific profile — uses fallback
    query: standing desk
    keywords:
      - standing desk
      - sit stand
      - adjustable desk
      - motorized desk
    exclude:
      - mat
      - accessory
      - monitor arm
    min_score: 15
```

---

## Pushover Notifications

[Pushover](https://pushover.net) delivers push notifications to iOS and Android.
A one-time $5 app purchase covers lifetime use. No subscription.

### Setup

1. Create a free account at [pushover.net](https://pushover.net)
2. Note your **User Key** on the dashboard
3. Create a new **Application** (call it "Slickdeals Tracker") and note the **API Token**
4. Install the Pushover app on your phone

### Configure the tracker

Add or update the `pushover` block in `config.yaml`:

```yaml
pushover:
  enabled: true
  api_token: "azGDORePK8gMaC0QOYAMyEEuzJnyUi"   # your app token
  user_key:  "uQiRzpo4DXghDmr9QzzfQu"            # your user key
  min_verdict: "GOOD DEAL"   # notify for GOOD DEAL and GREAT DEAL
  notify_on_run: false       # false = only notify when using `analyze`
  max_per_check: 5           # max notifications per poll cycle
```

### What a notification looks like

```
Title:   🔥 GREAT DEAL — TVs
Body:    LG 65" C3 OLED 4K Smart TV
         $1,199 (was $1,799) · 33% off · Best Buy
         Panel: OLED · Size: 65" · +312 votes
         Value: 8.4/10
Link:    [View on Slickdeals] → deal URL
```

### Notification priority mapping

| Verdict | Pushover Priority | Behavior |
|---------|-------------------|----------|
| `GREAT DEAL` | High (1) | Bypasses quiet hours |
| `GOOD DEAL` | Normal (0) | Standard notification |
| `FAIR DEAL` | Low (-1) | No sound/vibration |

### Testing notifications

```bash
python main.py notify-test
```

Sends a test notification to confirm your token and user key are valid.

---

## Running Perpetually

### Option A — systemd service (recommended for servers / always-on machines)

Create `/etc/systemd/system/slickdeals.service`:

```ini
[Unit]
Description=Slickdeals Deal Tracker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/Slickdeals-Tracker
ExecStart=/usr/bin/python3 main.py run --watch
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable slickdeals
sudo systemctl start slickdeals

# View live logs
journalctl -u slickdeals -f
```

**To also run analysis + notifications**, change `ExecStart` to:

```ini
ExecStart=/bin/bash -c 'while true; do python3 main.py analyze; sleep 1800; done'
```

### Option B — systemd user service (no sudo required)

```bash
mkdir -p ~/.config/systemd/user
```

Create `~/.config/systemd/user/slickdeals.service` with the same content above
(omit the `User=` line). Then:

```bash
systemctl --user daemon-reload
systemctl --user enable slickdeals
systemctl --user start slickdeals
loginctl enable-linger $USER   # keep running after logout
```

### Option C — cron (simplest)

```bash
crontab -e
```

Add one of these lines:

```cron
# Check every 30 minutes, log output
*/30 * * * * cd /path/to/Slickdeals-Tracker && python3 main.py run >> /var/log/slickdeals.log 2>&1

# Run analysis + notify every hour
0 * * * * cd /path/to/Slickdeals-Tracker && python3 main.py analyze >> /var/log/slickdeals.log 2>&1
```

### Option D — screen / tmux (personal machines)

```bash
# Start a detached screen session
screen -dmS slickdeals python3 main.py run --watch

# Reattach to check output
screen -r slickdeals

# Or with tmux
tmux new -d -s slickdeals 'python3 main.py run --watch'
tmux attach -t slickdeals
```

---

## Tips & Tricks

### Tune `min_score` per category

Community votes are a strong signal. Suggested starting points:

| Category | Suggested `min_score` |
|----------|-----------------------|
| TVs / Monitors | 10–20 |
| Laptops | 10–15 |
| SSDs / Peripherals | 5–10 |
| Gaming consoles | 15–25 |
| Appliances | 10–15 |
| General / Misc | 5 |

### Suppress deal fatigue with `exclude`

Use `exclude` aggressively. For TVs:

```yaml
exclude:
  - monitor
  - projector
  - streaming stick
  - fire stick
  - wall mount
  - universal remote
```

### Multiple config files for different use cases

```bash
# Morning quick check — only hot deals
python main.py run --config hot_only.yaml

# Evening deep dive with analysis
python main.py analyze --config all_categories.yaml
```

### Reset the "seen" database

The SQLite database remembers every deal it has shown you. To start fresh:

```bash
rm deals.db
```

Or to reset just one category, open the DB directly:

```bash
sqlite3 deals.db "DELETE FROM deals WHERE matched_keywords LIKE '%tv%';"
```

### Check what's in the database

```bash
python main.py history --limit 100
sqlite3 deals.db "SELECT title, price, score FROM deals ORDER BY score DESC LIMIT 20;"
```

---

## Docker & UnRAID

### Quick start with Docker Compose

```bash
git clone https://github.com/asaji/Slickdeals-Tracker.git
cd Slickdeals-Tracker

# Build the image
docker compose build

# Start the tracker + web dashboard
docker compose up -d

# Open the dashboard
open http://localhost:7001
```

Your `config.yaml` and `deals.db` are stored in `./data/` (bind-mounted to `/config` inside the container).

### Environment variables

All key settings can be passed as Docker environment variables, which override values in `config.yaml`:

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/New_York` | Container timezone |
| `CONFIG_PATH` | `/config/config.yaml` | Path to config file |
| `DB_PATH` | `/config/deals.db` | Path to SQLite database |
| `POLL_INTERVAL` | `30` | Poll interval in minutes |
| `PUSHOVER_TOKEN` | _(empty)_ | Pushover API token |
| `PUSHOVER_USER_KEY` | _(empty)_ | Pushover user key |
| `PUSHOVER_ENABLED` | `false` | Set `true` to enable notifications |
| `HOT_DEALS_ENABLED` | `false` | Set `true` to monitor frontpage hot deals |
| `HOT_DEALS_MIN_SCORE` | `0` | Minimum vote score for hot deals |
| `PUID` | `99` | User ID the container runs as (UnRAID: 99) |
| `PGID` | `100` | Group ID the container runs as (UnRAID: 100) |

### First-run config

On first run, if no `config.yaml` exists at `CONFIG_PATH`, the tracker generates a default one. To start with your own:

```bash
mkdir -p ./data
cp config.yaml ./data/config.yaml
# Edit ./data/config.yaml to add your searches
docker compose up -d
```

### Web dashboard

The dashboard runs on port `7001` and auto-refreshes every 5 minutes.

| URL | Description |
|---|---|
| `http://host:7001/` | Deal dashboard |
| `http://host:7001/api/deals` | JSON deal list |
| `http://host:7001/api/stats` | Summary statistics |
| `http://host:7001/health` | Health check endpoint |

### UnRAID installation

**Option A — Community Applications (CA) store** (once the template is listed):

1. In UnRAID, go to **Apps** → search **Slickdeals Tracker** → **Install**
2. Fill in your Pushover credentials and enable hot deals if desired
3. Click **Apply** — the container starts and the dashboard is available at `http://tower:7001`

**Option B — Manual template import**:

1. Go to **Docker** tab → **Add Container** → click the template URL field
2. Paste the template URL:
   ```
   https://raw.githubusercontent.com/asaji/Slickdeals-Tracker/main/unraid/slickdeals-tracker.xml
   ```
3. Fill in the form fields and click **Apply**

**Option C — docker compose on UnRAID**:

```bash
# SSH into UnRAID
ssh root@tower

cd /mnt/user/appdata
git clone https://github.com/asaji/Slickdeals-Tracker.git
cd Slickdeals-Tracker

# Edit docker-compose.yml if needed, then:
docker compose up -d
```

### Updating

```bash
# Pull latest image
docker compose pull
docker compose up -d

# Or rebuild from source
docker compose build --no-cache
docker compose up -d
```

Your `./data/` volume (config + database) is preserved across updates.

### Logs

```bash
# All logs
docker compose logs -f

# Just the tracker
docker compose logs -f slickdeals-tracker
```
