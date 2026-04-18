# Slickdeals Tracker

Monitor [Slickdeals.net](https://slickdeals.net) for specific deal categories (TVs, laptops, gaming, etc.) using RSS feeds. Tracks seen deals in a local SQLite database and displays new ones in a rich terminal UI.

## Features

- Keyword + category filtering (e.g. only OLED TVs, no monitors)
- Minimum vote/score threshold to filter low-quality deals
- Deduplication via SQLite — never see the same deal twice
- Rich terminal table output with score, price, store, and age
- One-shot or continuous `--watch` mode with configurable polling interval
- Fully configurable via `config.yaml`

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Run once using default config.yaml
python main.py run

# Watch continuously, polling every 30 minutes (or per config)
python main.py run --watch

# Override poll interval to 15 minutes
python main.py run --watch --interval 15

# Use a custom config file
python main.py run --config my_config.yaml

# Show recent deals from the database
python main.py history

# Generate a fresh default config.yaml
python main.py init
```

## Configuration

Edit `config.yaml` to define your searches:

```yaml
poll_interval_minutes: 30
db_path: deals.db
max_deals_display: 20
show_seen: false

searches:
  - name: TVs
    query: TV                        # Slickdeals search query
    keywords:                        # Must match at least one keyword in title/summary
      - oled
      - qled
      - 4k
    exclude:                         # Skip deals containing these words
      - monitor
    min_score: 10                    # Minimum community vote score
```

### Fields

| Field | Description |
|---|---|
| `query` | Search term sent to Slickdeals |
| `keywords` | At least one must appear in title/summary |
| `exclude` | Any match skips the deal |
| `min_score` | Minimum upvote count (0 = all deals) |

## How it works

1. Fetches Slickdeals frontpage, popular, and search-specific RSS feeds
2. Filters entries by your keywords/exclusions and vote threshold
3. Saves new deals to `deals.db` (SQLite)
4. Displays unseen deals in a sorted table (highest score first)
