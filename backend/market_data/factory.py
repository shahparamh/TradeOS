from market_data.market_config import normalize_market
from market_data.india_provider import IndiaMarketDataProvider
from market_data.alpaca_provider import AlpacaMarketDataProvider

_PROVIDERS = {
    "IN": IndiaMarketDataProvider,
    "US": AlpacaMarketDataProvider,
}

_instances = {}


def get_provider(market: str):
    """Returns the singleton MarketDataProvider for a market. This is the ONLY place that
    should know which concrete provider class backs a given market — agents, the technical
    engine, and API routes should call market_data_factory.get_provider(market) rather than
    importing yfinance/Alpaca code directly."""
    m = normalize_market(market)
    if m not in _instances:
        _instances[m] = _PROVIDERS[m]()
    return _instances[m]
