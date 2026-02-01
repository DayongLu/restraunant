from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RestaurantCreate(BaseModel):
    name: str
    city: str = ""
    cuisine_hint: str = ""


class RestaurantRead(BaseModel):
    id: int
    name: str
    city: str
    cuisine_hint: str


class MenuItemCreate(BaseModel):
    name: str
    description: str = ""
    price: float = Field(ge=0)
    currency: str = "USD"
    is_signature: bool = False
    region_tags: list[str] = Field(default_factory=list)
    flavor_tags: list[str] = Field(default_factory=list)


class MenuItemRead(BaseModel):
    id: int
    restaurant_id: int
    name: str
    description: str
    price: float
    currency: str
    is_signature: bool
    region_tags: list[str]
    flavor_tags: list[str]


class RecommendationResponse(BaseModel):
    items: list[MenuItemRead]
    note: str = ""


class HealthResponse(BaseModel):
    ok: bool
    db: str
