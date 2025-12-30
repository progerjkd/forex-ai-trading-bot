"""
OANDA API client wrapper for FOREX data ingestion.
Provides methods for fetching market data and account information.
"""

import logging
from datetime import datetime
from typing import Dict, Iterator, List, Optional

import oandapyV20
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.pricing as pricing
from oandapyV20.exceptions import V20Error

from shared.config import settings

logger = logging.getLogger(__name__)


class OANDAClient:
    """
    OANDA API client for fetching market data and managing connections.

    Supports both practice and live environments based on configuration.
    """

    def __init__(self):
        """Initialize OANDA client with credentials from settings."""
        self.api_key = settings.oanda_api_key
        self.account_id = settings.oanda_account_id
        self.base_url = settings.oanda_base_url

        # Initialize OANDA API client
        self.client = oandapyV20.API(
            access_token=self.api_key,
            environment=settings.oanda_environment
        )

        logger.info(
            f"Initialized OANDA client for {settings.oanda_environment} environment"
        )

    def test_connection(self) -> Dict:
        """
        Test OANDA API connection by fetching account details.

        Returns:
            Dict containing account information

        Raises:
            V20Error: If connection fails
        """
        try:
            # Fetch account summary
            endpoint = accounts.AccountSummary(accountID=self.account_id)
            response = self.client.request(endpoint)

            account = response.get("account", {})
            logger.info(f"Successfully connected to OANDA account: {self.account_id}")
            logger.info(f"Account balance: {account.get('balance')} {account.get('currency')}")

            return {
                "status": "success",
                "account_id": account.get("id"),
                "balance": float(account.get("balance", 0)),
                "currency": account.get("currency"),
                "unrealized_pl": float(account.get("unrealizedPL", 0)),
                "open_positions": int(account.get("openPositionCount", 0)),
                "open_trades": int(account.get("openTradeCount", 0)),
            }

        except V20Error as e:
            logger.error(f"Failed to connect to OANDA: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during connection test: {e}")
            raise

    def get_current_price(self, instrument: str = "EUR_USD") -> Dict:
        """
        Get current bid/ask price for an instrument.

        Args:
            instrument: Trading pair in OANDA format (e.g., "EUR_USD")

        Returns:
            Dict containing current pricing information
        """
        try:
            # Fetch current pricing
            params = {"instruments": instrument}
            endpoint = pricing.PricingInfo(accountID=self.account_id, params=params)
            response = self.client.request(endpoint)

            prices = response.get("prices", [])
            if not prices:
                raise ValueError(f"No pricing data returned for {instrument}")

            price_data = prices[0]

            result = {
                "instrument": price_data.get("instrument"),
                "time": price_data.get("time"),
                "bid": float(price_data.get("bids", [{}])[0].get("price", 0)),
                "ask": float(price_data.get("asks", [{}])[0].get("price", 0)),
                "status": price_data.get("status"),
            }

            # Calculate mid price and spread
            result["mid"] = (result["bid"] + result["ask"]) / 2
            result["spread"] = result["ask"] - result["bid"]

            logger.info(
                f"{instrument}: Bid={result['bid']}, Ask={result['ask']}, "
                f"Spread={result['spread']:.5f}"
            )

            return result

        except V20Error as e:
            logger.error(f"Failed to fetch price for {instrument}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching price: {e}")
            raise

    def get_candles(
        self,
        instrument: str = "EUR_USD",
        granularity: str = "M5",
        count: int = 100
    ) -> List[Dict]:
        """
        Fetch historical candlestick data.

        Args:
            instrument: Trading pair in OANDA format (e.g., "EUR_USD")
            granularity: Candle size (M1, M5, M15, H1, H4, D)
            count: Number of candles to fetch (max 5000)

        Returns:
            List of candle dictionaries with OHLCV data
        """
        try:
            params = {
                "granularity": granularity,
                "count": min(count, 5000)  # OANDA max limit
            }

            endpoint = instruments.InstrumentsCandles(
                instrument=instrument,
                params=params
            )
            response = self.client.request(endpoint)

            candles = response.get("candles", [])

            # Transform to our format
            result = []
            for candle in candles:
                if not candle.get("complete"):
                    continue  # Skip incomplete candles

                mid = candle.get("mid", {})
                result.append({
                    "time": candle.get("time"),
                    "volume": int(candle.get("volume", 0)),
                    "open": float(mid.get("o", 0)),
                    "high": float(mid.get("h", 0)),
                    "low": float(mid.get("l", 0)),
                    "close": float(mid.get("c", 0)),
                })

            logger.info(
                f"Fetched {len(result)} candles for {instrument} ({granularity})"
            )

            return result

        except V20Error as e:
            logger.error(f"Failed to fetch candles for {instrument}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching candles: {e}")
            raise

    def get_tradeable_instruments(self) -> List[str]:
        """
        Get list of tradeable instruments for the account.

        Returns:
            List of instrument names
        """
        try:
            endpoint = accounts.AccountInstruments(accountID=self.account_id)
            response = self.client.request(endpoint)

            instruments_list = response.get("instruments", [])
            tradeable = [
                inst.get("name")
                for inst in instruments_list
                if inst.get("type") == "CURRENCY"
            ]

            logger.info(f"Found {len(tradeable)} tradeable currency pairs")
            return tradeable

        except V20Error as e:
            logger.error(f"Failed to fetch tradeable instruments: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching instruments: {e}")
            raise

    def stream_pricing(self, instruments_list: List[str]) -> Iterator[Dict]:
        """
        Stream live price updates using HTTP streaming.

        This establishes a persistent HTTP connection that receives price updates
        as they occur (up to 250ms intervals). The connection will send HEARTBEAT
        messages every ~5 seconds when there are no price updates.

        Args:
            instruments_list: List of instruments to stream (e.g., ["EUR_USD", "GBP_USD"])

        Yields:
            Dict with either:
            - {"type": "PRICE", ...price_data...} - Price update
            - {"type": "HEARTBEAT", "time": timestamp} - Keep-alive heartbeat

        Example:
            for message in client.stream_pricing(["EUR_USD", "GBP_USD"]):
                if message["type"] == "PRICE":
                    print(f"Price update: {message}")
                elif message["type"] == "HEARTBEAT":
                    print(f"Heartbeat at {message['time']}")

        Raises:
            V20Error: If streaming connection fails
        """
        try:
            # Join instruments with comma separator
            instruments_str = ",".join(instruments_list)
            params = {"instruments": instruments_str}

            logger.info(f"Starting price stream for: {instruments_str}")

            # Create streaming endpoint
            endpoint = pricing.PricingStream(
                accountID=self.account_id,
                params=params
            )

            # Stream responses - this is a blocking iterator
            for response in self.client.request(endpoint):
                # Yield each message (PRICE or HEARTBEAT)
                if "type" in response:
                    yield response

        except V20Error as e:
            logger.error(f"Streaming connection error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in price stream: {e}")
            raise
