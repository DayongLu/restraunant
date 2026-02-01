# restraunant

Multi-restaurant menu management + recommendation backend (local-first) intended to be queried by an agent (e.g., via WhatsApp).

> Note: repo name is `restraunant` (typo preserved). You can rename the repo later if you want.

## What’s inside

- `apps/menu_agent/` — FastAPI backend + SQLite DB
  - Manage **restaurants** and **menu items**
  - Track **price**, **signature dishes**, **region tags**, and **flavor tags**
  - Query + filter items
  - Get simple **recommendations** (optionally prefer signature dishes)

## Requirements

- macOS/Linux
- Python 3.11+ (your machine currently has 3.14, which works)

## Quick start

```bash
cd apps/menu_agent
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

# Seed sample data
python -m app.seed

# Run the API
uvicorn app.main:app --reload --host 127.0.0.1 --port 8040
```

Open the interactive API docs:
- http://127.0.0.1:8040/docs

Health check:
- http://127.0.0.1:8040/health

## Core endpoints

- `GET /restaurants` — list restaurants
- `POST /restaurants` — create a restaurant
- `POST /restaurants/{restaurant_id}/items` — add a menu item
- `GET /items` — list/filter menu items
  - query params: `restaurant_id`, `q`, `region`, `flavor`, `is_signature`, `max_price`
- `GET /recommendations` — get recommended items
  - query params: `restaurant_id`, `region`, `flavor`, `max_price`, `limit`, `prefer_signature`

Example:
```bash
curl "http://127.0.0.1:8040/recommendations?region=Sichuan&flavor=spicy&limit=3"
```

## Tag conventions

Tags are stored as strings and matched case-insensitively.

- Region examples: `Sichuan`, `Cantonese`, `Italian`, `Texas`
- Flavor examples: `spicy`, `numbing`, `sweet`, `smoky`, `garlicky`

## WhatsApp / agent integration (planned)

Goal: allow chat commands like:
- “推荐 3 个辣的川菜”
- “给我看某某餐厅的特色菜”
- “预算 $20 以内推荐 5 个菜”

Implementation approach (next step):
- Add a small message handler that parses WhatsApp text → calls local API → formats reply.

## Development notes

- DB path: `apps/menu_agent/data/menu_agent.sqlite3`
- Seed data is **for simulation only**.
