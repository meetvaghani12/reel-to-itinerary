"""Live foreign-exchange rates (USD base), cached.

Costs are computed in USD; the frontend converts for display. Rates are fetched
from a free, no-key provider (open.er-api.com, ~160 currencies, updated daily)
and cached in Redis for 12h. A small static table is the last-resort fallback so
the endpoint never hard-fails.
"""
import logging
import httpx
from fastapi import APIRouter

from app.utils.cache import cache_get, cache_set

router = APIRouter()
logger = logging.getLogger(__name__)

CACHE_KEY = "fx:usd"
CACHE_TTL = 60 * 60 * 12  # 12 hours
PROVIDER = "https://open.er-api.com/v6/latest/USD"

# Last-resort fallback (only used if the provider and cache are both unavailable).
FALLBACK_RATES = {
    "USD": 1, "EUR": 0.92, "GBP": 0.79, "INR": 83.5, "JPY": 149.5, "AUD": 1.53,
    "CAD": 1.36, "SGD": 1.34, "AED": 3.67, "THB": 35.8, "CNY": 7.24, "IDR": 15700,
}


@router.get("/")
async def get_rates():
    cached = await cache_get(CACHE_KEY)
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(PROVIDER)
            resp.raise_for_status()
            data = resp.json()
        rates = data.get("rates") or {}
        if not rates:
            raise ValueError("provider returned no rates")
        out = {
            "base": "USD",
            "rates": rates,
            "updated": data.get("time_last_update_utc", ""),
            "source": "open.er-api.com",
        }
        await cache_set(CACHE_KEY, out, ttl=CACHE_TTL)
        logger.info("Fetched %d live FX rates", len(rates))
        return out
    except Exception as e:
        logger.warning("FX fetch failed (%s) — using fallback table", e)
        return {"base": "USD", "rates": FALLBACK_RATES, "updated": "", "source": "fallback"}
