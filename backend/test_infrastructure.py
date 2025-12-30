#!/usr/bin/env python3
"""
Test script to verify infrastructure connectivity (PostgreSQL + TimescaleDB + Redis).
Run this to ensure your Docker infrastructure is working correctly.

Usage:
    python backend/test_infrastructure.py
"""

import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
import redis
from shared.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_postgresql():
    """Test PostgreSQL and TimescaleDB connectivity."""
    print("Test 1: PostgreSQL + TimescaleDB Connection")
    print("-" * 70)

    try:
        # Parse database URL
        # Format: postgresql://user:pass@host:port/database
        db_url = settings.database_url
        logger.info(f"Connecting to: {db_url}")

        # Connect to PostgreSQL
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Test 1: Basic connection
        cursor.execute("SELECT version();")
        pg_version = cursor.fetchone()[0]
        print(f"✓ Connected to PostgreSQL successfully")
        print(f"  PostgreSQL version: {pg_version.split(',')[0]}")

        # Test 2: Check database name
        cursor.execute("SELECT current_database();")
        db_name = cursor.fetchone()[0]
        print(f"  Current database: {db_name}")

        # Test 3: Check TimescaleDB extension
        cursor.execute("""
            SELECT extname, extversion
            FROM pg_extension
            WHERE extname = 'timescaledb';
        """)
        result = cursor.fetchone()
        if result:
            ext_name, ext_version = result
            print(f"✓ TimescaleDB extension installed")
            print(f"  TimescaleDB version: {ext_version}")
        else:
            print("✗ TimescaleDB extension NOT found")
            return False

        # Test 4: Check trading schema exists
        cursor.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name = 'trading';
        """)
        result = cursor.fetchone()
        if result:
            print(f"✓ Schema 'trading' exists")
        else:
            print("✗ Schema 'trading' NOT found")
            return False

        # Test 5: Check search path
        cursor.execute("SHOW search_path;")
        search_path = cursor.fetchone()[0]
        print(f"  Search path: {search_path}")

        # Test 6: Test write permissions in trading schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading.test_table (
                id SERIAL PRIMARY KEY,
                test_data TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        cursor.execute("INSERT INTO trading.test_table (test_data) VALUES ('test');")
        cursor.execute("SELECT COUNT(*) FROM trading.test_table;")
        count = cursor.fetchone()[0]
        cursor.execute("DROP TABLE trading.test_table;")
        conn.commit()
        print(f"✓ Write permissions verified (created and dropped test table)")

        # Test 7: Test TimescaleDB hypertable functionality
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading.test_hypertable (
                time TIMESTAMPTZ NOT NULL,
                value DOUBLE PRECISION
            );
        """)
        cursor.execute("""
            SELECT create_hypertable(
                'trading.test_hypertable',
                'time',
                if_not_exists => TRUE
            );
        """)
        cursor.execute("DROP TABLE trading.test_hypertable;")
        conn.commit()
        print(f"✓ TimescaleDB hypertable functionality verified")

        cursor.close()
        conn.close()
        print()
        return True

    except Exception as e:
        print(f"✗ PostgreSQL test failed: {e}")
        print()
        return False


def test_redis():
    """Test Redis connectivity."""
    print("Test 2: Redis Connection")
    print("-" * 70)

    try:
        # Connect to Redis
        redis_url = settings.redis_url
        logger.info(f"Connecting to: {redis_url}")

        r = redis.from_url(redis_url, decode_responses=True)

        # Test 1: Ping
        response = r.ping()
        if response:
            print(f"✓ Connected to Redis successfully")
            print(f"  Redis ping: PONG")
        else:
            print("✗ Redis ping failed")
            return False

        # Test 2: Get Redis info
        info = r.info("server")
        print(f"  Redis version: {info['redis_version']}")
        print(f"  Redis mode: {info['redis_mode']}")

        # Test 3: SET/GET test
        test_key = "test:infrastructure:key"
        test_value = "Infrastructure test successful"
        r.set(test_key, test_value, ex=10)  # Expire in 10 seconds
        retrieved_value = r.get(test_key)

        if retrieved_value == test_value:
            print(f"✓ SET/GET test passed")
        else:
            print(f"✗ SET/GET test failed")
            return False

        # Test 4: Delete test key
        r.delete(test_key)
        print(f"✓ DELETE test passed")

        # Test 5: Check persistence settings
        info = r.info("persistence")
        aof_enabled = info.get('aof_enabled', 0)
        print(f"  AOF (Append-Only File) enabled: {bool(aof_enabled)}")

        print()
        return True

    except Exception as e:
        print(f"✗ Redis test failed: {e}")
        print()
        return False


def main():
    """Run infrastructure tests."""
    print("=" * 70)
    print("INFRASTRUCTURE CONNECTIVITY TEST")
    print("=" * 70)
    print()

    # Display configuration
    print(f"Environment: {settings.environment}")
    print(f"Database URL: {settings.database_url}")
    print(f"Redis URL: {settings.redis_url}")
    print(f"TimescaleDB enabled: {settings.timescaledb_enabled}")
    print()

    # Run tests
    results = []
    results.append(("PostgreSQL + TimescaleDB", test_postgresql()))
    results.append(("Redis", test_redis()))

    # Summary
    print("=" * 70)
    all_passed = all(result for _, result in results)

    if all_passed:
        print("ALL TESTS PASSED! ✓")
        print("=" * 70)
        print()
        print("Your infrastructure is ready!")
        print("Next steps:")
        print("  1. Initialize Alembic: alembic init alembic")
        print("  2. Create database models for market data")
        print("  3. Create initial migration")
        print()
        return 0
    else:
        print("SOME TESTS FAILED! ✗")
        print("=" * 70)
        print()
        for name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {name}: {status}")
        print()
        print("Troubleshooting steps:")
        print("  1. Check that Docker services are running: docker-compose ps")
        print("  2. Check Docker logs: docker-compose logs postgres redis")
        print("  3. Verify .env file has correct connection strings")
        print("  4. Try restarting services: docker-compose restart")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
