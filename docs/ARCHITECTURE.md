# FOREX AI Trading Bot - System Architecture

## System Overview

The FOREX AI Trading Bot is a sophisticated paper trading system that combines local machine learning models with strategic analysis from ChatGPT to generate and execute trading signals on the OANDA platform.

### Architecture Diagram

```
External APIs (OANDA, OpenAI, Telegram)
    ↓
AWS Infrastructure (EC2, RDS, S3)
    ↓
┌─────────────────────────────────────────────────────┐
│ Application Layer (ECS/EC2)                        │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ Data         │  │ Strategy     │  │ API +    │ │
│  │ Ingestion    │→ │ Engine       │→ │ WebSocket│ │
│  │ Service      │  │ (ML + LLM)   │  │ Service  │ │
│  └──────────────┘  └──────────────┘  └──────────┘ │
│         ↓                  ↓                ↓      │
│  ┌──────────────────────────────────────────────┐ │
│  │         Redis (Pub/Sub + Cache)              │ │
│  └──────────────────────────────────────────────┘ │
│         ↓                  ↓                ↓      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │Execution │  │ Telegram │  │ ML Training      ││
│  │ Service  │  │ Bot      │  │ (Celery Workers) ││
│  └──────────┘  └──────────┘  └──────────────────┘│
└─────────────────────────────────────────────────────┘
         ↓                                      ↓
┌─────────────────┐                    ┌─────────────┐
│ RDS PostgreSQL  │                    │ S3 Buckets  │
│ + TimescaleDB   │                    │ (Models)    │
└─────────────────┘                    └─────────────┘
         ↓
┌─────────────────────────────────────────────────────┐
│ Client Layer: Web Dashboard + Telegram Bot Client  │
└─────────────────────────────────────────────────────┘
```

---

## Architecture Principles

### 1. Three-Tier Hybrid Intelligence

The system employs a unique three-layer decision-making architecture:

**Tier 1: Local ML (Fast Layer)**
- **Purpose**: Real-time signal generation every 5 minutes
- **Technology**: Random Forest Classifier (scikit-learn)
- **Characteristics**: Fast (<100ms), deterministic, fully backtestable
- **Output**: BUY/SELL/HOLD signals with confidence scores

**Tier 2: ChatGPT (Smart Layer)**
- **Purpose**: Strategic market analysis 1-3 times per day
- **Technology**: OpenAI GPT-4o-mini API
- **Characteristics**: Natural language reasoning, regime detection
- **Output**: Market regime classification, risk adjustments, performance insights

**Tier 3: Human (Safety Layer)**
- **Purpose**: Final oversight and manual intervention
- **Interface**: Telegram bot, web dashboard
- **Characteristics**: Approve/reject trades, override bot during unusual conditions

### 2. Event-Driven Design

- Market data events trigger feature calculation pipelines
- Signals published via Redis pub/sub for real-time distribution
- WebSocket connections for live dashboard updates
- Celery Beat for scheduled tasks (signal generation, LLM analysis)

### 3. Separation of Concerns

Clear boundaries between system components:
- Data ingestion isolated from strategy logic
- Strategy engine independent of execution
- API layer separate from business logic
- Each service can scale independently

### 4. Cost-First Optimization

Designed to operate within AWS Free Tier constraints:
- Hybrid ML approach: 99% cost reduction vs pure LLM ($0.15-9/month vs $864/month)
- Single EC2 instance for development/validation
- Efficient data storage with TimescaleDB compression
- Strategic ChatGPT usage (10 calls/day limit)

---

## Component Architecture

### Data Ingestion Layer

**Responsibility**: Stream market data from OANDA and persist to database

**Key Files**:
- `backend/data_ingestion/oanda_client.py` - OANDA v20 API wrapper
- `backend/data_ingestion/main.py` - Main ingestion service
- `backend/data_ingestion/normalizer.py` - Data normalization
- `backend/data_ingestion/storage.py` - TimescaleDB persistence

**Technologies**:
- **OANDA v20 API**: Real-time FOREX data streaming
- **PostgreSQL + TimescaleDB**: Time-series optimized storage
- **Redis**: Real-time data broadcasting via pub/sub

**Data Flow**:
1. Connect to OANDA WebSocket stream for selected pairs (EUR/USD, GBP/USD, USD/JPY)
2. Receive OHLCV data in 1-minute intervals
3. Normalize to standard format
4. Store in TimescaleDB hypertables
5. Publish to Redis pub/sub channel for real-time consumers
6. Cache latest prices in Redis for quick access

**Key Design Decisions**:
- 1-minute granularity balances data quality with storage costs
- TimescaleDB automatic compression after 7 days
- Continuous aggregates for 5m, 15m, 1h timeframes
- Data retention: 3 months for 1-min, unlimited for aggregates

---

### Strategy Engine Layer

**Responsibility**: Generate trading signals using hybrid ML approach

**Key Files**:
- `backend/strategy_engine/features/technical_indicators.py` - TA-Lib wrapper
- `backend/strategy_engine/models/direction_classifier.py` - Random Forest model
- `backend/strategy_engine/llm/llm_analyzer.py` - ChatGPT integration
- `backend/strategy_engine/signals/signal_generator.py` - Signal logic
- `backend/strategy_engine/signals/regime_filter.py` - LLM-informed filtering
- `backend/strategy_engine/risk_management.py` - Position sizing, risk checks

**Technologies**:
- **scikit-learn**: Random Forest for direction prediction
- **TA-Lib**: Technical indicator calculations (RSI, MACD, Bollinger, ATR, etc.)
- **OpenAI API**: GPT-4o-mini for strategic analysis
- **Celery**: Scheduled task execution
- **Redis**: Task queue and result backend

**Subsystems**:

#### Feature Engineering
- **Technical Indicators**: 80-100 features from TA-Lib
  - Trend: SMA(20,50,200), EMA(12,26), MACD, ADX
  - Momentum: RSI(14), Stochastic, Williams %R, ROC
  - Volatility: Bollinger Bands, ATR, Standard Deviation
  - Volume: OBV, Volume Rate of Change
- **Price Patterns**: Candlestick patterns, support/resistance
- **Time Features**: Hour, day, forex session (London/NY/Tokyo)
- **Multi-Timeframe**: Aggregated features from 1m, 5m, 15m, 1h

#### Local ML Models
1. **Direction Classifier** (Random Forest)
   - Input: 80-100 engineered features
   - Output: BUY/SELL/HOLD + confidence (0.0-1.0)
   - Training: 6-12 months historical data
   - Retraining: Weekly
   - Validation: Rolling window cross-validation

2. **Volatility Predictor** (Random Forest Regressor)
   - Input: Same feature set
   - Output: Expected volatility for next N periods
   - Purpose: Dynamic position sizing and stop loss placement

3. **LSTM Price Predictor** (Optional, Phase 3+)
   - Input: Sequence of OHLCV + indicators (60-120 timesteps)
   - Output: Price movement magnitude
   - Purpose: Target price and take profit levels

#### LLM Integration
**ChatGPT Strategic Analysis** (1-10 calls/day):

1. **Daily Market Regime Analysis** (8 AM):
   ```python
   # Aggregate 24h data
   summary = {
       "EUR/USD": {"change": +0.35%, "RSI": 62, "MACD": "bullish", "ATR": 0.0012},
       "GBP/USD": {...},
       "USD/JPY": {...}
   }

   # Query ChatGPT
   response = chatgpt.analyze_regime(summary)
   # Output: "EUR/USD trending, GBP/USD ranging, USD/JPY weak trend"

   # Update strategy config
   strategy_config["EUR/USD"]["mode"] = "trend_following"
   strategy_config["EUR/USD"]["confidence_threshold"] = 0.65
   ```

2. **News Sentiment Analysis** (on major events):
   - Scrape economic calendar
   - Send news headlines + current positions to ChatGPT
   - Receive risk assessment → adjust position sizes or pause trading

3. **Performance Review** (8 PM):
   - Send daily trade summary to ChatGPT
   - Identify patterns in winning/losing trades
   - Flag potential issues for human review

4. **Weekly Correlation Analysis** (Sunday):
   - Calculate correlation matrix of trading pairs
   - Check for over-exposure to specific currencies
   - Receive diversification recommendations

**Rate Limiting**: Hard 10 calls/day limit with alerting if exceeded

---

### Execution Layer

**Responsibility**: Execute trades on OANDA practice account

**Key Files**:
- `backend/execution/order_manager.py` - Order creation and submission
- `backend/execution/position_manager.py` - Position tracking and P&L calculation

**Technologies**:
- **OANDA v20 API**: Paper trading execution
- **PostgreSQL**: Order and position persistence
- **Redis**: Real-time position state

**Execution Flow**:
1. Receive signal from strategy engine
2. Apply risk management rules:
   - Check daily loss limit (circuit breaker at 3%)
   - Verify max position count (3 concurrent)
   - Calculate position size (1% risk per trade)
   - Validate stop loss and take profit levels
3. Build OANDA order (market order with SL/TP)
4. Submit to OANDA practice account
5. Track order status (pending → filled)
6. Update position database
7. Broadcast to WebSocket clients
8. Send Telegram notification

**Position Monitoring**:
- Real-time P&L calculation (mark-to-market)
- Stop loss / take profit trigger monitoring
- Trailing stop logic
- Automatic position closure on triggers

---

### API Layer

**Responsibility**: Provide REST API and WebSocket server for frontend

**Key Files**:
- `backend/api/main.py` - FastAPI application
- `backend/api/routers/*.py` - Endpoint handlers
- `backend/api/websocket/server.py` - Socket.io server

**Technologies**:
- **FastAPI**: Async REST API framework
- **Socket.io**: WebSocket server for real-time updates
- **JWT**: Authentication tokens
- **Pydantic**: Request/response validation

**Endpoints**:
- `GET /api/v1/market-data/{pair}` - OHLCV data
- `GET /api/v1/signals` - Trading signals
- `GET /api/v1/positions` - Current positions
- `GET /api/v1/trades` - Trade history
- `GET /api/v1/performance` - P&L metrics
- `POST /api/v1/bot/start` - Start bot
- `POST /api/v1/bot/stop` - Stop bot
- `POST /api/v1/backtest` - Run backtest

**WebSocket Events**:
- `market_data_update` - New OHLCV data
- `signal_generated` - New trading signal
- `order_executed` - Trade executed
- `position_update` - Position state change
- `pnl_update` - Real-time P&L change

---

### Telegram Bot

**Responsibility**: Mobile notifications and quick commands

**Key Files**:
- `backend/telegram_bot/main.py` - Bot entry point
- `backend/telegram_bot/handlers/*.py` - Command handlers
- `backend/telegram_bot/notifications.py` - Alert system

**Commands**:
- `/status` - Bot status (running/stopped, active pairs)
- `/positions` - Current positions with P&L
- `/signals` - Recent signals (last 10)
- `/pnl` - Quick P&L summary (today, week, all-time)
- `/approve <signal_id>` - Approve pending signal (manual mode)
- `/reject <signal_id>` - Reject pending signal

**Notifications**:
- New signal generated (with inline approve/reject buttons)
- Trade executed (entry price, SL, TP)
- Position closed (P&L, duration, exit reason)
- Daily P&L summary
- Circuit breaker triggered
- System errors/warnings

---

### Backtesting Engine

**Responsibility**: Validate trading strategies on historical data

**Key Files**:
- `backend/backtesting/engine.py` - Backtest simulation
- `backend/backtesting/data_loader.py` - Historical data retrieval
- `backend/backtesting/simulator.py` - Order execution simulation
- `backend/backtesting/metrics.py` - Performance calculation
- `backend/backtesting/reports.py` - HTML/PDF report generation

**Technologies**:
- **vectorbt**: High-performance backtesting library
- **pandas/numpy**: Data manipulation
- **matplotlib/plotly**: Chart generation

**Workflow**:
1. Load historical OHLCV data from TimescaleDB
2. Generate features for each timestep
3. Run ML model inference (historical mode)
4. Generate signals based on strategy rules
5. Simulate order execution (slippage, spread modeling)
6. Track positions and calculate P&L
7. Calculate performance metrics
8. Generate visual report

**Metrics Calculated**:
- Total return, annualized return
- Sharpe ratio, Sortino ratio
- Maximum drawdown, max drawdown duration
- Win rate, profit factor
- Average win/loss, largest win/loss
- Trade frequency, average holding time

---

## Data Flow

### Real-Time Trading Flow

```
1. OANDA WebSocket Stream
   ↓
2. Data Ingestion Service
   - Normalize OHLCV data
   - Store to TimescaleDB (1-min bars)
   - Publish to Redis pub/sub
   - Update Redis cache (latest price)
   ↓
3. Celery Beat Scheduler (every 5 minutes)
   ↓
4. Strategy Engine - Feature Engineering
   - Fetch recent data from TimescaleDB
   - Calculate technical indicators (RSI, MACD, etc.)
   - Create multi-timeframe aggregates
   ↓
5. Strategy Engine - ML Inference
   - Load Random Forest model from memory
   - Predict direction (BUY/SELL/HOLD) + confidence
   ↓
6. Strategy Engine - Regime Filter
   - Read current regime from ChatGPT analysis cache
   - Adjust confidence threshold based on regime
   - Apply signal filters (trend alignment, volume, etc.)
   ↓
7. Signal Generator
   - If confidence > threshold AND filters pass:
     → Generate signal (direction, entry, SL, TP)
     → Store in PostgreSQL
     → Publish to Redis
     → Send to Telegram
   ↓
8. Execution Service - Risk Management
   - Check daily loss limit
   - Verify max position count
   - Calculate position size (1% risk)
   ↓
9. Execution Service - Order Execution
   - Build OANDA order (market with SL/TP)
   - Submit to OANDA practice account
   - Track order status
   ↓
10. Position Manager
    - Update position in PostgreSQL
    - Calculate unrealized P&L
    - Monitor SL/TP triggers
    - Broadcast updates via WebSocket
```

### LLM Strategic Analysis Flow

```
Daily 8 AM - Market Regime Analysis:
   1. Aggregate last 24h data (prices, indicators, volatility)
   2. Format prompt with market summary
   3. Call ChatGPT API (GPT-4o-mini)
   4. Parse response (trending/ranging classification per pair)
   5. Update strategy config in Redis cache
   6. Store analysis in PostgreSQL
   7. Log API call count

Daily 8 PM - Performance Review:
   1. Aggregate day's trades (wins, losses, P&L, signals)
   2. Format prompt with performance summary
   3. Call ChatGPT API
   4. Parse insights (patterns, issues flagged)
   5. Store review in PostgreSQL
   6. Send summary to Telegram if anomalies detected

On Major News Event:
   1. Economic calendar trigger
   2. Fetch news headlines
   3. Format prompt with news + current positions
   4. Call ChatGPT API
   5. Parse risk assessment
   6. Adjust position size multipliers
   7. Optionally pause trading if extreme risk

Weekly Sunday - Correlation Analysis:
   1. Calculate 1-week correlation matrix
   2. Get current portfolio composition
   3. Format prompt with correlations + exposure
   4. Call ChatGPT API
   5. Parse diversification recommendations
   6. Flag for human review
```

---

## Infrastructure

### Local Development

**Docker Compose Setup**:
- **PostgreSQL + TimescaleDB**: `timescale/timescaledb:latest-pg16`
  - Port: 5432
  - Volume: Persistent storage for historical data
  - Init script: Enable TimescaleDB extension
- **Redis**: `redis:7-alpine`
  - Port: 6379
  - Persistence: AOF (append-only file)
- **PgAdmin** (optional): Web UI for database management
  - Port: 5050

**Python Environment**:
- Poetry for dependency management
- Python 3.11+ virtual environment
- Hot reload for development (uvicorn --reload)

**Services**:
- API server: `uvicorn backend.api.main:app --reload`
- Celery worker: `celery -A backend.strategy_engine.celery_app worker`
- Celery beat: `celery -A backend.strategy_engine.celery_app beat`
- Telegram bot: `python backend/telegram_bot/main.py`

---

### AWS Production (Free Tier - Year 1)

**Compute**:
- **EC2 t2.micro/t3.micro** (750 hours/month FREE)
  - 1 vCPU, 1GB RAM
  - Runs all services via Docker Compose
  - Elastic IP attached (FREE when attached)
  - Security group: Restrict ports to necessary only

**Database**:
- **RDS db.t2.micro** (750 hours/month FREE)
  - PostgreSQL 16 with TimescaleDB
  - 20GB SSD storage (FREE)
  - Single-AZ (high availability not needed for paper trading)
  - Automated backups (7-day retention)

**Storage**:
- **S3 buckets** (5GB FREE):
  - `forex-bot-models`: ML model weights (.pkl, .pt files)
  - `forex-bot-backtest`: Backtest reports (HTML, JSON)
  - Versioning enabled for models

**Caching**:
- **ElastiCache Redis** (for production scaling) OR
- **Self-managed Redis** on EC2 (for Free Tier optimization)

**Monitoring**:
- **CloudWatch Logs**: Structured JSON logs from all services
- **CloudWatch Metrics**: Custom trading metrics (10 FREE)
  - `signals_per_hour`
  - `trades_executed`
  - `daily_pnl`
  - `position_count`
  - `ml_confidence_avg`
  - `llm_api_calls`
  - `error_rate`
- **CloudWatch Alarms** (10 FREE):
  - Error rate > 5%
  - Daily loss > 3%
  - LLM API calls > 10/day
  - OANDA API failures

**Networking**:
- VPC with public subnet (simplified for Free Tier)
- Security groups:
  - EC2: Allow 22 (SSH), 80 (HTTP), 443 (HTTPS), 5432 (from RDS)
  - RDS: Allow 5432 (from EC2 only)

**Deployment**:
- Infrastructure as Code: Terraform
- CI/CD: GitHub Actions (build Docker images → push to ECR → deploy to EC2)

---

### AWS Production (Post Free Tier - Optimized)

**Cost-Optimized Setup** ($35-50/month):
- **EC2 t3.small Reserved Instance** (1-year RI): $10-15/month
- **RDS db.t3.micro Single-AZ**: $15/month
- **Self-managed Redis** on EC2: FREE (included)
- **S3 + CloudWatch**: $5-10/month
- **No NAT Gateway**: Use EC2 with public IP (save $35/month)

**Scalable Setup** ($130-160/month) - If transitioning to live trading:
- **ECS Fargate**: Multiple services ($30-60/month)
- **RDS db.t3.small Multi-AZ**: $42/month
- **ElastiCache Redis**: $12/month
- **NAT Gateway**: $35/month (for private subnets)
- **ALB**: $16/month

---

## Security Architecture

### Secrets Management

**Local Development**:
- `.env` file (gitignored)
- Stored outside Google Drive via symlink: `~/.forex-secrets/forex-ai-trading-bot.env`
- Never committed to git

**Production**:
- AWS Secrets Manager for all sensitive data:
  - OANDA API key
  - OANDA account ID
  - OpenAI API key
  - Telegram bot token
  - Database credentials
- IAM roles for service access (no hardcoded credentials)
- Automatic secret rotation every 90 days

### Authentication & Authorization

**API**:
- JWT tokens for authenticated endpoints
- Token expiration: 1 hour (refresh tokens for web app)
- Rate limiting: 100 requests/minute per IP

**Telegram Bot**:
- User ID whitelist (only your Telegram user ID)
- No public access to bot commands

**OANDA**:
- Practice account only (initially)
- Separate API key from live account
- Rate limiting: 120 requests/second (OANDA limit)

### Data Security

**At Rest**:
- RDS encryption enabled
- S3 bucket encryption (AES-256)
- EBS volume encryption (EC2)

**In Transit**:
- HTTPS/TLS 1.2+ for all external communication
- SSL connections to RDS
- WebSocket over TLS (WSS)

### Network Security

**Firewall Rules**:
- EC2 security group: Minimal open ports
- RDS security group: Only EC2 can connect
- VPC flow logs for audit

**Secrets in Logs**:
- Structured logging with field redaction
- API keys automatically masked in logs
- No sensitive data in CloudWatch

---

## Scalability Considerations

### Current Constraints (Free Tier)

- **Single EC2 instance**: 1 vCPU, 1GB RAM
- **Trading pairs**: 3 (EUR/USD, GBP/USD, USD/JPY)
- **Signal interval**: 5 minutes
- **Expected throughput**: ~500 signals/day across 3 pairs
- **Database size**: ~500MB/month (1-min data, 3 pairs)

### Bottlenecks

1. **CPU**: ML inference if many features (mitigated by efficient Random Forest)
2. **Memory**: Loading large historical datasets for backtesting
3. **Network**: OANDA WebSocket if streaming many pairs
4. **Database**: Query performance on large time-series datasets

### Scaling Path (Future)

**Horizontal Scaling** (10+ pairs, 1-min signals):
- Migrate to ECS Fargate with multiple tasks
- Data ingestion: 1 task per 5 pairs
- Strategy engine: 3-5 Celery workers
- Execution service: 2 tasks for redundancy
- API service: Auto-scaling (2-5 tasks)

**Database Scaling**:
- RDS read replicas for analytics queries
- TimescaleDB distributed hypertables (if >100GB data)
- Redis cluster for high availability

**Caching Optimization**:
- Cache technical indicators (1-hour TTL)
- Cache ML model outputs (5-min TTL)
- Cache ChatGPT regime analysis (24-hour TTL)

---

## Monitoring & Observability

### Logging

**Structured JSON Logs**:
```json
{
  "timestamp": "2024-12-29T10:30:00Z",
  "level": "INFO",
  "service": "strategy_engine",
  "message": "Signal generated",
  "context": {
    "pair": "EUR/USD",
    "direction": "BUY",
    "confidence": 0.72,
    "signal_id": "sig_123456",
    "correlation_id": "req_abc123"
  }
}
```

**Log Levels**:
- DEBUG: Development only
- INFO: Signal generation, trade execution, routine operations
- WARNING: High confidence but filtered signals, API rate limits approaching
- ERROR: Failed API calls, order rejections, database errors
- CRITICAL: Circuit breaker triggered, system failures

### Metrics

**Trading Metrics**:
- Signals generated per hour (by pair, by direction)
- Trades executed per day
- Win rate (rolling 7-day, 30-day)
- Daily P&L, weekly P&L, all-time P&L
- Average ML confidence per signal
- Position count (current)
- Circuit breaker triggers

**System Metrics**:
- API latency (p50, p95, p99)
- ML inference time
- Database query time
- WebSocket message latency
- Error rate by service
- LLM API call count (daily)

**Business Metrics**:
- Total return (%)
- Sharpe ratio (rolling 30-day)
- Maximum drawdown
- Profit factor
- Average holding time

### Alerting

**Critical Alerts** (SMS/Email):
- Daily loss limit exceeded (circuit breaker)
- System error rate > 10%
- OANDA API connection lost > 5 minutes
- Database connection failed

**Warning Alerts** (Telegram):
- Daily loss > 2%
- Error rate > 5%
- LLM API calls > 8/day
- Unusual trade frequency (>20 signals/hour)

---

## Technology Choices Rationale

### Python over Go/Node.js
**Decision**: Python 3.11+
- **Pro**: Best ML ecosystem (scikit-learn, TA-Lib, pandas)
- **Pro**: Faster development for data science tasks
- **Pro**: Aligns with intermediate ML experience
- **Con**: Slower than Go for high-frequency trading
- **Mitigation**: Good enough for 5-min signals, use asyncio for concurrency

### TimescaleDB over DynamoDB
**Decision**: PostgreSQL + TimescaleDB
- **Pro**: Purpose-built for time-series (automatic compression)
- **Pro**: SQL for complex analytics
- **Pro**: Strong consistency for financial data
- **Con**: More complex than DynamoDB
- **Mitigation**: RDS manages operational complexity

### Hybrid ML over Pure LLM
**Decision**: Local Random Forest + ChatGPT strategic analysis
- **Pro**: 99% cost reduction ($0.15-9 vs $864/month)
- **Pro**: Fast real-time decisions (<100ms)
- **Pro**: Deterministic backtesting
- **Con**: More complex architecture
- **Mitigation**: Clear separation of concerns, well-defined interfaces

### OANDA over Interactive Brokers
**Decision**: OANDA for paper trading
- **Pro**: Free unlimited practice account
- **Pro**: Excellent Python library (oandapyV20)
- **Pro**: Real-time streaming API
- **Con**: Limited to FOREX (but that's our focus)

### FastAPI over Flask/Django
**Decision**: FastAPI
- **Pro**: Native async/await support
- **Pro**: Built-in WebSocket support
- **Pro**: Automatic OpenAPI docs
- **Pro**: Pydantic validation
- **Con**: Newer framework (less mature than Flask)
- **Mitigation**: Well-documented, actively maintained

---

## Future Enhancements

### Phase 6+ Optimizations

1. **Advanced ML Models**:
   - LSTM for price prediction
   - Reinforcement learning for dynamic strategy selection
   - Ensemble methods (combine multiple models)

2. **Additional Strategies**:
   - Mean reversion (Bollinger Bands)
   - Breakout trading
   - Pairs trading (correlation-based)

3. **Multi-Asset Support**:
   - Expand to commodities (Gold, Oil)
   - Cryptocurrency pairs
   - Stock indices

4. **Enhanced LLM Integration**:
   - Sentiment analysis from Twitter/news
   - Macro-economic factor analysis
   - Automated strategy parameter tuning

5. **Mobile App**:
   - React Native app for iOS/Android
   - Push notifications
   - Real-time chart viewing

6. **Live Trading Preparation**:
   - Gradual capital allocation (start with $100)
   - A/B testing (paper vs small live account)
   - Enhanced risk management (Kelly criterion)

---

## Conclusion

This architecture provides a solid foundation for an AI-powered FOREX trading bot that:
- Operates within AWS Free Tier ($0-5/month Year 1)
- Combines local ML efficiency with ChatGPT strategic intelligence
- Maintains clear separation of concerns for scalability
- Prioritizes security and risk management
- Provides multiple interfaces (API, dashboard, Telegram)
- Enables thorough backtesting and validation

The system is designed to validate strategies in paper trading for 3-6 months before considering live trading, with a clear upgrade path for production deployment.
