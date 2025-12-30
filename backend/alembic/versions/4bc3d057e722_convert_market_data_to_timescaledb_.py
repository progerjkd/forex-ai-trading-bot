"""Convert market_data to TimescaleDB hypertable

Revision ID: 4bc3d057e722
Revises: 33fe8dda15a8
Create Date: 2025-12-29 04:49:05.116140

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4bc3d057e722'
down_revision: Union[str, Sequence[str], None] = '0bc7e5559506'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert market_data table to TimescaleDB hypertable."""
    # Convert market_data to hypertable with timestamp as the time column
    # chunk_time_interval: 7 days
    op.execute("""
        SELECT create_hypertable(
            'trading.market_data',
            'timestamp',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    """)

    # Create compression policy: compress chunks older than 7 days
    op.execute("""
        ALTER TABLE trading.market_data SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'instrument,timeframe',
            timescaledb.compress_orderby = 'timestamp DESC'
        );
    """)

    op.execute("""
        SELECT add_compression_policy(
            'trading.market_data',
            compress_after => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    """)

    # Create retention policy: keep data for 3 months
    op.execute("""
        SELECT add_retention_policy(
            'trading.market_data',
            drop_after => INTERVAL '3 months',
            if_not_exists => TRUE
        );
    """)

    # Create continuous aggregates for 5-minute, 15-minute, and 1-hour timeframes
    # 5-minute aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS trading.market_data_5m
        WITH (timescaledb.continuous) AS
        SELECT
            instrument,
            'M5' as timeframe,
            time_bucket('5 minutes', timestamp) AS timestamp,
            first(open, timestamp) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, timestamp) AS close,
            sum(volume) AS volume
        FROM trading.market_data
        WHERE timeframe = 'M1'
        GROUP BY instrument, time_bucket('5 minutes', timestamp);
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy(
            'trading.market_data_5m',
            start_offset => INTERVAL '1 hour',
            end_offset => INTERVAL '5 minutes',
            schedule_interval => INTERVAL '5 minutes',
            if_not_exists => TRUE
        );
    """)

    # 15-minute aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS trading.market_data_15m
        WITH (timescaledb.continuous) AS
        SELECT
            instrument,
            'M15' as timeframe,
            time_bucket('15 minutes', timestamp) AS timestamp,
            first(open, timestamp) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, timestamp) AS close,
            sum(volume) AS volume
        FROM trading.market_data
        WHERE timeframe = 'M1'
        GROUP BY instrument, time_bucket('15 minutes', timestamp);
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy(
            'trading.market_data_15m',
            start_offset => INTERVAL '1 hour',
            end_offset => INTERVAL '15 minutes',
            schedule_interval => INTERVAL '15 minutes',
            if_not_exists => TRUE
        );
    """)

    # 1-hour aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS trading.market_data_1h
        WITH (timescaledb.continuous) AS
        SELECT
            instrument,
            'H1' as timeframe,
            time_bucket('1 hour', timestamp) AS timestamp,
            first(open, timestamp) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, timestamp) AS close,
            sum(volume) AS volume
        FROM trading.market_data
        WHERE timeframe = 'M1'
        GROUP BY instrument, time_bucket('1 hour', timestamp);
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy(
            'trading.market_data_1h',
            start_offset => INTERVAL '2 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE
        );
    """)


def downgrade() -> None:
    """Remove TimescaleDB hypertable configuration."""
    # Drop continuous aggregates
    op.execute("DROP MATERIALIZED VIEW IF EXISTS trading.market_data_1h;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS trading.market_data_15m;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS trading.market_data_5m;")

    # Note: Cannot easily revert hypertable to regular table
    # This is generally a one-way migration in production
