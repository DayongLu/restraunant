from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Restaurant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    city: str = ""
    cuisine_hint: str = ""  # free-text
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MenuItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    restaurant_id: int = Field(index=True, foreign_key="restaurant.id")

    name: str
    description: str = ""

    # Store as cents to avoid float issues
    price_cents: int = 0
    currency: str = "USD"

    is_signature: bool = False

    # Comma-separated tags for simplicity.
    # (If we later need many-to-many, we can normalize.)
    region_tags: str = ""  # e.g. "Sichuan,Cantonese"
    flavor_tags: str = ""  # e.g. "spicy,numbing,garlicky"

    created_at: datetime = Field(default_factory=datetime.utcnow)

    def regions(self) -> set[str]:
        return {t.strip() for t in self.region_tags.split(",") if t.strip()}

    def flavors(self) -> set[str]:
        return {t.strip() for t in self.flavor_tags.split(",") if t.strip()}
