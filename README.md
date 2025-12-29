# FOREX AI Trading Bot

An intelligent FOREX trading bot powered by machine learning and ChatGPT strategic analysis.

## Features

- 🤖 **Local ML Trading Signals**: Random Forest classifier for real-time BUY/SELL/HOLD predictions
- 🧠 **ChatGPT Strategic Analysis**: Daily market regime detection and performance insights
- 📊 **Real-time Dashboard**: Web interface with TradingView-style charts
- 📱 **Telegram Bot**: Mobile notifications and trade approvals
- 🔬 **Backtesting Engine**: Validate strategies on historical data
- 📈 **Paper Trading**: Safe testing with OANDA practice account
- ☁️ **AWS Deployment**: Scalable cloud infrastructure

## Architecture

**Three-Tier Hybrid Approach**:
1. **Local ML (Fast Layer)**: Random Forest for real-time signals (every 5 min)
2. **ChatGPT (Smart Layer)**: Strategic analysis 1-3x per day
3. **Human Oversight (Safety Layer)**: Manual approval via Telegram

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Celery, SQLAlchemy
- **ML/AI**: scikit-learn, TA-Lib, OpenAI API (GPT-4o)
- **Frontend**: React, TypeScript, TradingView Lightweight Charts
- **Database**: PostgreSQL + TimescaleDB (time-series optimized)
- **Cache**: Redis
- **Infrastructure**: AWS (EC2, RDS, S3), Terraform
- **Trading**: OANDA v20 API

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry (dependency management)
- Docker & Docker Compose
- OANDA practice account
- OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd forex-ai-trading-bot
```

2. Copy environment template:
```bash
cp .env.example .env
```

3. Edit `.env` and add your API keys:
- OANDA_API_KEY
- OPENAI_API_KEY
- TELEGRAM_BOT_TOKEN (optional)

4. Start local development environment:
```bash
cd infrastructure/docker
docker-compose up -d
```

5. Install Python dependencies:
```bash
cd backend
poetry install
poetry shell
```

6. Run database migrations:
```bash
alembic upgrade head
```

7. Download historical data:
```bash
python scripts/download_historical_data.py
```

8. Start the services:
```bash
# Terminal 1: API server
uvicorn backend.api.main:app --reload

# Terminal 2: Celery worker
celery -A backend.strategy_engine.celery_app worker --loglevel=info

# Terminal 3: Celery beat (scheduler)
celery -A backend.strategy_engine.celery_app beat --loglevel=info
```

## Project Structure

```
forex-ai-trading-bot/
├── backend/
│   ├── shared/              # Shared utilities (config, database, logger)
│   ├── data_ingestion/      # OANDA API client, data streaming
│   ├── strategy_engine/     # ML models, signals, LLM integration
│   ├── execution/           # Order execution, position management
│   ├── api/                 # FastAPI REST API and WebSocket
│   ├── telegram_bot/        # Telegram bot for notifications
│   └── backtesting/         # Backtesting engine
├── frontend/                # React dashboard
├── infrastructure/          # Docker, Terraform
├── scripts/                 # Utility scripts
└── notebooks/               # Jupyter notebooks for analysis
```

## Configuration

Key configuration in `.env`:
- `TRADING_PAIRS`: Comma-separated list (default: EUR/USD,GBP/USD,USD/JPY)
- `PAPER_TRADING`: Always `true` for safety
- `ML_CONFIDENCE_THRESHOLD`: Minimum confidence for trades (default: 0.65)
- `LLM_MAX_CALLS_PER_DAY`: ChatGPT API call limit (default: 10)

## Trading Strategy

**Trend-Following with ML Confirmation**:
- Entry when EMA(12) > EMA(26), RSI 40-70, MACD bullish, ML confidence > 0.65
- Exit: Stop Loss at 1.5×ATR, Take Profit at 2.5×ATR
- Risk: 1% per trade, max 3 concurrent positions

**ChatGPT Strategic Overlay**:
- Morning: Market regime analysis (trending vs ranging)
- Evening: Performance review
- On news events: Sentiment analysis
- Weekly: Correlation analysis

## Development

### Running Tests
```bash
pytest
pytest --cov=backend tests/
```

### Code Formatting
```bash
black backend/
isort backend/
flake8 backend/
```

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Deployment

See [PLAN.md](PLAN.md) for detailed deployment guide.

**AWS Free Tier (Year 1)**:
- EC2 t2.micro/t3.micro
- RDS db.t2.micro/t3.micro
- S3, CloudWatch (free tier)
- Cost: $0-5/month + $20 ChatGPT Plus

## Monitoring

- **CloudWatch**: System metrics, logs, alarms
- **Dashboard**: Real-time P&L, positions, signals
- **Telegram**: Trade notifications, daily summaries

## Safety Features

- Paper trading only (initially)
- Daily loss circuit breaker (3% of capital)
- Position limits (max 3 concurrent)
- ChatGPT never directly executes trades
- All trades logged and auditable

## Roadmap

- [x] Phase 1: Foundation (Data pipeline, API)
- [ ] Phase 2: ML & ChatGPT Integration
- [ ] Phase 3: Execution & Backtesting
- [ ] Phase 4: User Interfaces (Dashboard, Telegram)
- [ ] Phase 5: AWS Deployment
- [ ] Phase 6: Optimizations (LSTM, more strategies)

## License

MIT License - See [LICENSE](LICENSE) file

## Disclaimer

⚠️ **This is for educational and paper trading purposes only.** Trading financial instruments carries significant risk. Never trade with money you cannot afford to lose. Past performance does not guarantee future results.

## Support

For questions or issues, please open a GitHub issue or refer to [PLAN.md](PLAN.md) for detailed documentation.
