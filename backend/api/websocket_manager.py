"""
WebSocket connection manager for real-time data broadcasting.

Manages active WebSocket connections and provides utilities for
broadcasting messages to all connected clients.
"""

import json
import logging
from typing import Dict, List, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and message broadcasting.

    Maintains a registry of active connections and provides methods for
    connecting, disconnecting, and broadcasting messages to clients.
    """

    def __init__(self):
        """Initialize connection manager."""
        # Store active connections by connection ID
        self.active_connections: Dict[str, WebSocket] = {}

        # Track subscriptions: {instrument: {connection_id, ...}}
        self.subscriptions: Dict[str, Set[str]] = {}

        # Stats
        self.total_connections = 0
        self.total_messages_sent = 0

    async def connect(self, websocket: WebSocket, client_id: str):
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: WebSocket connection to accept
            client_id: Unique identifier for this connection
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.total_connections += 1

        logger.info(
            f"Client {client_id} connected | "
            f"Active: {len(self.active_connections)} | "
            f"Total: {self.total_connections}"
        )

        # Send welcome message
        await self.send_personal_message(
            {
                "type": "connection",
                "status": "connected",
                "client_id": client_id,
                "message": "Connected to FOREX trading bot WebSocket",
            },
            websocket,
        )

    def disconnect(self, client_id: str):
        """
        Remove a connection from active connections.

        Args:
            client_id: Connection ID to remove
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]

            # Remove from all subscriptions
            for instrument in self.subscriptions:
                self.subscriptions[instrument].discard(client_id)

            logger.info(
                f"Client {client_id} disconnected | "
                f"Active: {len(self.active_connections)}"
            )

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send message to specific connection.

        Args:
            message: Message dict to send
            websocket: Target WebSocket connection
        """
        try:
            await websocket.send_json(message)
            self.total_messages_sent += 1
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast(self, message: dict):
        """
        Broadcast message to all active connections.

        Args:
            message: Message dict to broadcast
        """
        if not self.active_connections:
            return

        disconnected = []

        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
                self.total_messages_sent += 1
            except WebSocketDisconnect:
                logger.warning(f"Client {client_id} disconnected during broadcast")
                disconnected.append(client_id)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            self.disconnect(client_id)

    async def broadcast_to_subscribers(self, instrument: str, message: dict):
        """
        Broadcast message to clients subscribed to specific instrument.

        Args:
            instrument: Instrument name (e.g., "EUR_USD")
            message: Message dict to broadcast
        """
        subscribers = self.subscriptions.get(instrument, set())

        if not subscribers:
            return

        disconnected = []

        for client_id in subscribers:
            connection = self.active_connections.get(client_id)
            if not connection:
                disconnected.append(client_id)
                continue

            try:
                await connection.send_json(message)
                self.total_messages_sent += 1
            except WebSocketDisconnect:
                logger.warning(f"Client {client_id} disconnected during broadcast")
                disconnected.append(client_id)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            self.disconnect(client_id)

    def subscribe(self, client_id: str, instrument: str):
        """
        Subscribe client to instrument updates.

        Args:
            client_id: Connection ID
            instrument: Instrument to subscribe to
        """
        if instrument not in self.subscriptions:
            self.subscriptions[instrument] = set()

        self.subscriptions[instrument].add(client_id)
        logger.info(f"Client {client_id} subscribed to {instrument}")

    def unsubscribe(self, client_id: str, instrument: str):
        """
        Unsubscribe client from instrument updates.

        Args:
            client_id: Connection ID
            instrument: Instrument to unsubscribe from
        """
        if instrument in self.subscriptions:
            self.subscriptions[instrument].discard(client_id)
            logger.info(f"Client {client_id} unsubscribed from {instrument}")

    def get_stats(self) -> dict:
        """
        Get connection manager statistics.

        Returns:
            Dict with connection stats
        """
        return {
            "active_connections": len(self.active_connections),
            "total_connections": self.total_connections,
            "total_messages_sent": self.total_messages_sent,
            "subscriptions": {
                instrument: len(subscribers)
                for instrument, subscribers in self.subscriptions.items()
            },
        }


# Global connection manager instance
manager = ConnectionManager()
