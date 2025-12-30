"""
FastAPI application for FOREX trading bot.

Provides REST API endpoints and WebSocket connections for real-time
data streaming to frontend dashboards.
"""

import logging
import uuid
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.websocket_broadcaster import broadcaster
from api.websocket_manager import manager
from shared.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FOREX AI Trading Bot API",
    description="Real-time market data and trading signals via REST and WebSocket",
    version="1.0.0",
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on app startup."""
    logger.info("=" * 70)
    logger.info("FOREX AI TRADING BOT API")
    logger.info("=" * 70)
    logger.info(f"Environment: {'PAPER' if settings.paper_trading else 'LIVE'}")
    logger.info(f"Trading Pairs: {settings.trading_pairs}")
    logger.info("")

    # Start WebSocket broadcaster for Redis -> WebSocket forwarding
    await broadcaster.start()
    logger.info("WebSocket broadcaster started")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on app shutdown."""
    logger.info("Shutting down API server...")

    # Stop WebSocket broadcaster
    await broadcaster.stop()
    logger.info("WebSocket broadcaster stopped")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "service": "FOREX AI Trading Bot API",
        "version": "1.0.0",
        "websocket_endpoint": "/ws/{client_id}",
    }


@app.get("/health")
async def health():
    """
    Health check with service status.

    Returns:
        Service health information
    """
    return {
        "status": "healthy",
        "websocket": {
            "active_connections": len(manager.active_connections),
            "total_connections": manager.total_connections,
        },
    }


@app.get("/stats")
async def stats():
    """
    Get WebSocket connection statistics.

    Returns:
        Connection manager stats
    """
    return manager.get_stats()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = None):
    """
    WebSocket endpoint for real-time data streaming.

    Clients connect to this endpoint to receive live market data updates.
    The connection supports bidirectional communication for subscriptions.

    Args:
        websocket: WebSocket connection
        client_id: Optional client identifier (auto-generated if not provided)

    Message Types (Client -> Server):
        {
            "type": "subscribe",
            "instrument": "EUR_USD",
            "timeframe": "M1"  # optional
        }
        {
            "type": "unsubscribe",
            "instrument": "EUR_USD"
        }
        {
            "type": "ping"
        }

    Message Types (Server -> Client):
        {
            "type": "connection",
            "status": "connected",
            "client_id": "abc-123"
        }
        {
            "type": "tick",
            "instrument": "EUR_USD",
            "timestamp": "2024-01-15T10:30:00Z",
            "bid": 1.0850,
            "ask": 1.0852,
            "mid": 1.0851,
            "spread": 0.0002
        }
        {
            "type": "candle",
            "instrument": "EUR_USD",
            "timeframe": "M1",
            "timestamp": "2024-01-15T10:30:00Z",
            "open": 1.0850,
            "high": 1.0855,
            "low": 1.0848,
            "close": 1.0852,
            "volume": 150
        }
        {
            "type": "pong"
        }
    """
    # Generate client ID if not provided
    if not client_id:
        client_id = str(uuid.uuid4())

    # Connect client
    await manager.connect(websocket, client_id)

    try:
        # Listen for client messages
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            message_type = data.get("type")

            if message_type == "subscribe":
                # Subscribe to instrument updates
                instrument = data.get("instrument")
                if instrument:
                    manager.subscribe(client_id, instrument)
                    await manager.send_personal_message(
                        {
                            "type": "subscribed",
                            "instrument": instrument,
                            "message": f"Subscribed to {instrument} updates",
                        },
                        websocket,
                    )
                else:
                    await manager.send_personal_message(
                        {
                            "type": "error",
                            "message": "Missing instrument in subscribe request",
                        },
                        websocket,
                    )

            elif message_type == "unsubscribe":
                # Unsubscribe from instrument updates
                instrument = data.get("instrument")
                if instrument:
                    manager.unsubscribe(client_id, instrument)
                    await manager.send_personal_message(
                        {
                            "type": "unsubscribed",
                            "instrument": instrument,
                            "message": f"Unsubscribed from {instrument} updates",
                        },
                        websocket,
                    )

            elif message_type == "ping":
                # Respond to ping
                await manager.send_personal_message(
                    {"type": "pong", "timestamp": data.get("timestamp")},
                    websocket,
                )

            else:
                # Unknown message type
                await manager.send_personal_message(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {message_type}",
                    },
                    websocket,
                )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
