from __future__ import annotations

import random
from typing import Iterable, Optional

from sqlmodel import Session, select

from .models import MenuItem, Restaurant


def _normalize_tag(s: str) -> str:
    return s.strip().lower().replace(" ", "_")


def _tags_match(item_tags: Iterable[str], required: str) -> bool:
    req = _normalize_tag(required)
    return any(_normalize_tag(t) == req for t in item_tags)


def list_restaurants(session: Session) -> list[Restaurant]:
    return list(session.exec(select(Restaurant).order_by(Restaurant.name)))


def list_items(
    session: Session,
    restaurant_id: Optional[int] = None,
    q: Optional[str] = None,
    region: Optional[str] = None,
    flavor: Optional[str] = None,
    is_signature: Optional[bool] = None,
    max_price_cents: Optional[int] = None,
) -> list[MenuItem]:
    stmt = select(MenuItem)
    if restaurant_id is not None:
        stmt = stmt.where(MenuItem.restaurant_id == restaurant_id)
    if is_signature is not None:
        stmt = stmt.where(MenuItem.is_signature == is_signature)
    if max_price_cents is not None:
        stmt = stmt.where(MenuItem.price_cents <= max_price_cents)

    items = list(session.exec(stmt.order_by(MenuItem.restaurant_id, MenuItem.name)))

    if q:
        ql = q.lower()
        items = [
            it
            for it in items
            if ql in it.name.lower() or (it.description and ql in it.description.lower())
        ]
    if region:
        items = [it for it in items if _tags_match(it.regions(), region)]
    if flavor:
        items = [it for it in items if _tags_match(it.flavors(), flavor)]
    return items


def recommend_items(
    session: Session,
    restaurant_id: Optional[int] = None,
    region: Optional[str] = None,
    flavor: Optional[str] = None,
    max_price_cents: Optional[int] = None,
    limit: int = 3,
    prefer_signature: bool = True,
) -> list[MenuItem]:
    candidates = list_items(
        session,
        restaurant_id=restaurant_id,
        region=region,
        flavor=flavor,
        max_price_cents=max_price_cents,
    )
    if not candidates:
        return []

    # Simple scoring: signature dishes get more weight.
    weights = []
    for it in candidates:
        w = 1.0
        if prefer_signature and it.is_signature:
            w *= 3.0
        # Slightly prefer mid-range prices (avoid always cheapest)
        if it.price_cents > 0:
            w *= 1.0 + min(it.price_cents / 5000.0, 1.0) * 0.2
        weights.append(w)

    chosen: list[MenuItem] = []
    pool = candidates[:]
    pool_weights = weights[:]
    for _ in range(min(limit, len(pool))):
        it = random.choices(pool, weights=pool_weights, k=1)[0]
        idx = pool.index(it)
        chosen.append(it)
        pool.pop(idx)
        pool_weights.pop(idx)
    return chosen
