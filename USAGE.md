# Slickdeals Tracker — Usage Guide

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [CLI Commands](#cli-commands)
4. [Configuration Reference](#configuration-reference)
5. [Category System](#category-system)
6. [Pushover Notifications](#pushover-notifications)
7. [Running Perpetually](#running-perpetually)
8. [Tips & Tricks](#tips--tricks)

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

# 5. Watch continuously (polls on your configured interval)
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
