# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FOREX AI Trading Bot with three-tier hybrid intelligence:
1. **Local ML (Fast)**: Random Forest classifier for real-time BUY/SELL/HOLD signals every 5 minutes
2. **ChatGPT (Smart)**: GPT-4o-mini for daily strategic analysis (market regime, sentiment, performance)
3. **Human (Safety)**: Telegram bot for manual approval, paper trading only

## Project Status

**Early Development**: Directory structure is established, but most implementation files are not yet created. Currently implemented:
- Configuration management (`backend/shared/config.py`)
- Docker infrastructure (`infrastructure/docker/docker-compose.yml`)
- Comprehensive planning and architecture documentation

## Development Commands

```bash
# Setup
cd backend && poetry install && poetry shell

# Start infrastructure
cd infrastructure/docker && docker-compose up -d

# Start with PgAdmin (optional database GUI at http://localhost:5050)
cd infrastructure/docker && docker-compose --profile tools up -d
# PgAdmin credentials: admin@forex-bot.local / admin

# Database migrations (once alembic is initialized)
alembic init alembic  # first-time setup
alembic upgrade head
alembic revision --autogenerate -m "description"

# Run API server
uvicorn backend.api.main:app --reload

# Run Celery worker
celery -A backend.strategy_engine.celery_app worker --loglevel=info

# Run Celery scheduler
celery -A backend.strategy_engine.celery_app beat --loglevel=info

# Run Telegram bot
python backend/telegram_bot/main.py

# Testing
pytest
pytest --cov=backend tests/
pytest tests/test_file.py::test_function  # single test

# Linting
trunk check                    # Run all configured linters (bandit, ruff, checkov, trivy, trufflehog)
trunk fmt                      # Auto-format code (black, isort, prettier)
black backend/                 # Format code (also via trunk fmt)
isort backend/                 # Sort imports (also via trunk fmt)
ruff check backend/            # Fast Python linter (replaces flake8)
mypy backend/                  # Type checking (when implemented)
```

## Architecture

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Data Ingestion | `backend/data_ingestion/` | OANDA WebSocket stream, TimescaleDB storage, Redis pub/sub |
| Strategy Engine | `backend/strategy_engine/` | Feature engineering (`features/`), ML models (`models/`), LLM integration (`llm/`), signal generation (`signals/`) |
| Execution | `backend/execution/` | Order execution, position management, risk controls |
| API Layer | `backend/api/` | FastAPI REST endpoints, WebSocket for real-time updates |
| Telegram Bot | `backend/telegram_bot/` | Notifications, commands, trade approval |
| Backtesting | `backend/backtesting/` | Historical simulation, performance metrics |
| Shared | `backend/shared/` | Config, database, logging utilities |

### Data Flow

OANDA → Data Ingestion → TimescaleDB + Redis → Strategy Engine → Signal Generator → Execution → Position Manager → WebSocket/Telegram

### Key Technologies

- **Python 3.11+** with Poetry
- **FastAPI** + SQLAlchemy + Alembic
- **PostgreSQL + TimescaleDB** (time-series optimized)
- **Redis** (caching, pub/sub)
- **Celery** (async tasks, scheduling)
- **OANDA v20 API** (broker)
- **OpenAI API** (GPT-4o-mini)

## Code Style

- Black formatter (line-length: 100)
- isort with black profile
- Trunk configured with: bandit, ruff, checkov, trivy, trufflehog

## Trading Parameters

From `.env`:
- `PAPER_TRADING=true` (always for safety)
- Risk: 1% per trade, max 3 positions, 3% daily loss limit
- ML confidence threshold: 0.65
- ChatGPT calls: max 10/day

## Documentation

- `docs/ARCHITECTURE.md`: Detailed system design and component architecture
- `docs/DECISIONS.md`: Architecture Decision Records (ADRs 001-010)
- `PLAN.md`: 15-week implementation roadmap
