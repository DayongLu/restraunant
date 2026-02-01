from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlmodel import Session

from .db import DB_PATH, get_session, init_db
from .models import MenuItem, Restaurant
from .schemas import (
    HealthResponse,
    MenuItemCreate,
    MenuItemRead,
    RecommendationResponse,
    RestaurantCreate,
    RestaurantRead,
)
from .service import list_items, list_restaurants, recommend_items

app = FastAPI(title="Menu Agent", version="0.1.0")


@app.on_event("startup")
def _startup():
    init_db()


def _item_to_read(it: MenuItem) -> MenuItemRead:
    return MenuItemRead(
        id=it.id,
        restaurant_id=it.restaurant_id,
        name=it.name,
        description=it.description,
        price=round(it.price_cents / 100.0, 2),
        currency=it.currency,
        is_signature=it.is_signature,
        region_tags=sorted(list(it.regions())),
        flavor_tags=sorted(list(it.flavors())),
    )


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(ok=True, db=str(DB_PATH))


@app.get("/restaurants", response_model=list[RestaurantRead])
def get_restaurants(session: Session = Depends(get_session)):
    rs = list_restaurants(session)
    return [RestaurantRead(id=r.id, name=r.name, city=r.city, cuisine_hint=r.cuisine_hint) for r in rs]


@app.post("/restaurants", response_model=RestaurantRead)
def create_restaurant(payload: RestaurantCreate, session: Session = Depends(get_session)):
    r = Restaurant(name=payload.name, city=payload.city, cuisine_hint=payload.cuisine_hint)
    session.add(r)
    session.commit()
    session.refresh(r)
    return RestaurantRead(id=r.id, name=r.name, city=r.city, cuisine_hint=r.cuisine_hint)


@app.post("/restaurants/{restaurant_id}/items", response_model=MenuItemRead)
def create_item(
    restaurant_id: int,
    payload: MenuItemCreate,
    session: Session = Depends(get_session),
):
    r = session.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    it = MenuItem(
        restaurant_id=restaurant_id,
        name=payload.name,
        description=payload.description,
        price_cents=int(round(payload.price * 100)),
        currency=payload.currency,
        is_signature=payload.is_signature,
        region_tags=",".join([t.strip() for t in payload.region_tags if t.strip()]),
        flavor_tags=",".join([t.strip() for t in payload.flavor_tags if t.strip()]),
    )
    session.add(it)
    session.commit()
    session.refresh(it)
    return _item_to_read(it)


@app.get("/items", response_model=list[MenuItemRead])
def get_items(
    restaurant_id: int | None = None,
    q: str | None = None,
    region: str | None = None,
    flavor: str | None = None,
    is_signature: bool | None = None,
    max_price: float | None = Query(default=None, ge=0),
    session: Session = Depends(get_session),
):
    max_price_cents = None if max_price is None else int(round(max_price * 100))
    items = list_items(
        session,
        restaurant_id=restaurant_id,
        q=q,
        region=region,
        flavor=flavor,
        is_signature=is_signature,
        max_price_cents=max_price_cents,
    )
    return [_item_to_read(it) for it in items]


@app.get("/recommendations", response_model=RecommendationResponse)
def get_recommendations(
    restaurant_id: int | None = None,
    region: str | None = None,
    flavor: str | None = None,
    max_price: float | None = Query(default=None, ge=0),
    limit: int = Query(default=3, ge=1, le=10),
    prefer_signature: bool = True,
    session: Session = Depends(get_session),
):
    max_price_cents = None if max_price is None else int(round(max_price * 100))
    items = recommend_items(
        session,
        restaurant_id=restaurant_id,
        region=region,
        flavor=flavor,
        max_price_cents=max_price_cents,
        limit=limit,
        prefer_signature=prefer_signature,
    )

    note = ""
    if not items:
        note = "No matching items. Try removing filters (region/flavor/max_price)."

    return RecommendationResponse(items=[_item_to_read(it) for it in items], note=note)


@app.delete("/danger/reset")
def reset_all_data(confirm: bool = False, session: Session = Depends(get_session)):
    """Dangerous: wipe all data. Requires confirm=true."""
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass confirm=true")

    # order matters (FK)
    session.exec(text("DELETE FROM menuitem"))
    session.exec(text("DELETE FROM restaurant"))
    session.commit()
    return {"ok": True}
