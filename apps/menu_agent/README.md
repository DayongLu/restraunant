# Menu Agent (local backend)

A small local backend to manage **multiple restaurants** and their **menu items** (price, signature dishes), with **flavor** and **region** classification, plus simple recommendations.

This is designed to be queried by *your Clawdbot assistant* so you can ask via WhatsApp:
- “查一下某某餐厅的菜单”
- “我想吃辣的川菜，推荐 3 个菜”

## Quick start

### 1) Create venv + install

```bash
cd /Users/dylu/clawd/apps/menu_agent
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### 2) Seed sample data

```bash
python -m app.seed
```

### 3) Run API

```bash
uvicorn app.main:app --reload --port 8040
```

Open docs:
- http://127.0.0.1:8040/docs

## Data model

- Restaurant
  - name, city, cuisine_hint
- MenuItem
  - restaurant_id, name, description
  - price (decimal)
  - is_signature (bool)
  - region_tags: e.g. `Sichuan`, `Cantonese`, `Italian`, `American`
  - flavor_tags: e.g. `spicy`, `numbing`, `sweet`, `savory`, `sour`, `garlicky`

## Main endpoints

- `GET /restaurants`
- `GET /items` (filters: `restaurant_id`, `q`, `region`, `flavor`, `is_signature`, `max_price`)
- `GET /recommendations` (filters + `limit`)

## Notes about sample data

The seed data is **for simulation only**. Names are inspired by common popular dishes; it is not intended to be an exact copy of any restaurant’s full menu.
