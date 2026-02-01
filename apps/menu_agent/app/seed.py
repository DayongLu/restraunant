from __future__ import annotations

"""Seed sample restaurants + menu items.

This is simulation data only.

Run:
  python -m app.seed
"""

from sqlmodel import Session, select

from .db import engine, init_db
from .models import MenuItem, Restaurant


def _cents(x: float) -> int:
    return int(round(x * 100))


def main() -> None:
    init_db()

    with Session(engine) as session:
        existing = session.exec(select(Restaurant)).first()
        if existing:
            print("DB already has data; skipping seed.")
            return

        restaurants = [
            Restaurant(name="Sichuan House", city="New York", cuisine_hint="Sichuan / spicy"),
            Restaurant(name="Canton Garden", city="San Francisco", cuisine_hint="Cantonese / dim sum"),
            Restaurant(name="Trattoria Roma", city="Chicago", cuisine_hint="Italian"),
            Restaurant(name="Burger & Smoke", city="Austin", cuisine_hint="American / BBQ"),
        ]
        for r in restaurants:
            session.add(r)
        session.commit()
        for r in restaurants:
            session.refresh(r)

        items = [
            # Sichuan
            MenuItem(
                restaurant_id=restaurants[0].id,
                name="Mapo Tofu",
                description="Soft tofu in spicy chili-bean sauce with minced meat and Sichuan pepper.",
                price_cents=_cents(14.5),
                currency="USD",
                is_signature=True,
                region_tags="Sichuan",
                flavor_tags="spicy,numbing,savory",
            ),
            MenuItem(
                restaurant_id=restaurants[0].id,
                name="Dan Dan Noodles",
                description="Wheat noodles with sesame-chili sauce, minced pork, and pickled greens.",
                price_cents=_cents(12.0),
                currency="USD",
                is_signature=True,
                region_tags="Sichuan",
                flavor_tags="spicy,savory,nutty",
            ),
            MenuItem(
                restaurant_id=restaurants[0].id,
                name="Kung Pao Chicken",
                description="Stir-fried chicken with peanuts, dried chili, and a tangy-sweet sauce.",
                price_cents=_cents(16.0),
                currency="USD",
                is_signature=False,
                region_tags="Sichuan",
                flavor_tags="spicy,sweet,sour,nutty",
            ),
            # Cantonese
            MenuItem(
                restaurant_id=restaurants[1].id,
                name="Har Gow (Shrimp Dumplings)",
                description="Steamed shrimp dumplings with translucent wrapper.",
                price_cents=_cents(8.5),
                currency="USD",
                is_signature=True,
                region_tags="Cantonese",
                flavor_tags="savory,delicate",
            ),
            MenuItem(
                restaurant_id=restaurants[1].id,
                name="Siomai (Pork & Shrimp)",
                description="Open-faced steamed dumplings with pork and shrimp.",
                price_cents=_cents(8.0),
                currency="USD",
                is_signature=False,
                region_tags="Cantonese",
                flavor_tags="savory",
            ),
            MenuItem(
                restaurant_id=restaurants[1].id,
                name="Roast Duck",
                description="Crisp-skinned duck served with a light savory sauce.",
                price_cents=_cents(24.0),
                currency="USD",
                is_signature=True,
                region_tags="Cantonese",
                flavor_tags="savory,roasted",
            ),
            # Italian
            MenuItem(
                restaurant_id=restaurants[2].id,
                name="Spaghetti Carbonara",
                description="Spaghetti with egg, pecorino, guanciale, and black pepper.",
                price_cents=_cents(18.0),
                currency="USD",
                is_signature=True,
                region_tags="Italian,Roman",
                flavor_tags="savory,creamy,peppery",
            ),
            MenuItem(
                restaurant_id=restaurants[2].id,
                name="Margherita Pizza",
                description="Tomato, mozzarella, basil, olive oil.",
                price_cents=_cents(17.0),
                currency="USD",
                is_signature=False,
                region_tags="Italian,Neapolitan",
                flavor_tags="savory,herby",
            ),
            MenuItem(
                restaurant_id=restaurants[2].id,
                name="Tiramisu",
                description="Coffee-soaked ladyfingers with mascarpone cream and cocoa.",
                price_cents=_cents(9.0),
                currency="USD",
                is_signature=True,
                region_tags="Italian",
                flavor_tags="sweet,coffee,creamy",
            ),
            # American / BBQ
            MenuItem(
                restaurant_id=restaurants[3].id,
                name="Smoked Brisket Plate",
                description="Slow-smoked beef brisket with house BBQ sauce and sides.",
                price_cents=_cents(22.0),
                currency="USD",
                is_signature=True,
                region_tags="American,BBQ,Texas",
                flavor_tags="smoky,savory",
            ),
            MenuItem(
                restaurant_id=restaurants[3].id,
                name="Cheeseburger",
                description="Griddled beef patty, cheddar, lettuce, tomato, pickles.",
                price_cents=_cents(13.0),
                currency="USD",
                is_signature=False,
                region_tags="American",
                flavor_tags="savory",
            ),
            MenuItem(
                restaurant_id=restaurants[3].id,
                name="Spicy Fried Chicken Sandwich",
                description="Crispy chicken, spicy mayo, slaw, pickles.",
                price_cents=_cents(14.0),
                currency="USD",
                is_signature=False,
                region_tags="American,Southern",
                flavor_tags="spicy,savory",
            ),
        ]

        for it in items:
            session.add(it)
        session.commit()

        print(f"Seeded {len(restaurants)} restaurants and {len(items)} items.")


if __name__ == "__main__":
    main()
