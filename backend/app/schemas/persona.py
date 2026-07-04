from pydantic import BaseModel, Field
from typing import Optional


CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "INR": "₹",
    "JPY": "¥",
    "AUD": "A$",
    "CAD": "C$",
    "SGD": "S$",
    "AED": "د.إ",
    "THB": "฿",
    "IDR": "Rp",
    "MXN": "MX$",
    "BRL": "R$",
    "KRW": "₩",
}

CURRENCY_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "INR": 83.5,
    "JPY": 149.5,
    "AUD": 1.53,
    "CAD": 1.36,
    "SGD": 1.34,
    "AED": 3.67,
    "THB": 35.8,
    "IDR": 15700,
    "MXN": 17.15,
    "BRL": 4.97,
    "KRW": 1320,
}


class Persona(BaseModel):
    travel_style: str = "comfort"
    budget_range: str = "mid"
    group_type: str = "solo"
    pace_preference: str = "moderate"
    currency: str = "USD"

    @property
    def budget_multiplier(self) -> float:
        return {"low": 0.6, "mid": 1.0, "high": 1.8}.get(self.budget_range, 1.0)

    @property
    def accommodation_type(self) -> str:
        return {"low": "budget", "mid": "mid_range", "high": "luxury"}.get(
            self.budget_range, "mid_range"
        )

    @property
    def daily_food_style(self) -> str:
        return {"low": "street_food", "mid": "mix", "high": "restaurants"}.get(
            self.budget_range, "mix"
        )


def convert_currency(amount_usd: float, target_currency: str) -> float:
    rate = CURRENCY_RATES.get(target_currency, 1.0)
    return round(amount_usd * rate, 2)


def get_currency_symbol(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency, currency)
