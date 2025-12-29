---
name: FOREX AI Trading Bot
overview: Build a comprehensive FOREX trading bot with AI-powered analysis, real-time pair monitoring, multiple interaction interfaces (web dashboard, Telegram bot), and paper trading support using Interactive Brokers API and OpenAI.
todos:
  - id: setup-project-structure
    content: Create project structure with backend, frontend, telegram_bot, and infrastructure directories
    status: pending
  - id: setup-backend-foundation
    content: Set up FastAPI backend with database models, configuration, and basic API routes
    status: pending
    dependencies:
      - setup-project-structure
  - id: integrate-interactive-brokers
    content: Implement Interactive Brokers API integration for market data and paper trading
    status: pending
    dependencies:
      - setup-backend-foundation
  - id: implement-market-data-collection
    content: Build real-time and historical market data collection service with TimescaleDB storage
    status: pending
    dependencies:
      - integrate-interactive-brokers
  - id: build-technical-indicators
    content: Implement technical analysis library with common indicators (RSI, MACD, Moving Averages, etc.)
    status: pending
    dependencies:
      - implement-market-data-collection
  - id: integrate-openai-analysis
    content: Create AI analysis service that combines technical indicators with OpenAI for contextual recommendations
    status: pending
    dependencies:
      - build-technical-indicators
  - id: implement-paper-trading-engine
    content: Build paper trading engine with simulated execution, order management, and position tracking
    status: pending
    dependencies:
      - integrate-openai-analysis
  - id: create-strategy-framework
    content: Implement strategy manager with multiple trading strategies (trend, mean reversion, breakout, AI-driven)
    status: pending
    dependencies:
      - implement-paper-trading-engine
  - id: build-realtime-monitoring
    content: Create Celery workers for real-time pair monitoring, opportunity detection, and trade proposals
    status: pending
    dependencies:
      - create-strategy-framework
  - id: develop-web-dashboard
    content: Build React dashboard with charts, trade management, strategy configuration, and real-time updates
    status: pending
    dependencies:
      - build-realtime-monitoring
  - id: create-telegram-bot
    content: Implement Telegram bot for alerts, notifications, and quick trade commands
    status: pending
    dependencies:
      - build-realtime-monitoring
  - id: setup-aws-infrastructure
    content: Deploy infrastructure on AWS using Terraform (EC2/ECS, RDS, ElastiCache, S3, CloudWatch)
    status: pending
    dependencies:
      - develop-web-dashboard
      - create-telegram-bot
---

# FOREX AI Trading Bot - Implementation Plan

## Architecture Overview

The bot will follow a microservices architecture with clear separation of concerns:

```
┌─────────────────┐
│  User Interface │
│  (Dashboard/    │
│   Telegram)     │
└────────┬────────┘
         │
┌────────▼─────────────────────────┐
│      API Gateway (FastAPI)       │
└────────┬─────────────────────────┘
         │
    ┌────┴────┬──────────────┬─────────────┐
    │         │              │             │
┌───▼───┐ ┌──▼────┐  ┌──────▼──────┐ ┌───▼────┐
│Trading│ │Market │  │   AI        │ │Strategy│
│Engine │ │Data   │  │  Analysis   │ │Manager │
└───┬───┘ └───┬───┘  └──────┬──────┘ └───┬────┘
    │         │              │            │
    └─────────┴──────────────┴────────────┘
              │
    ┌─────────▼─────────┐
    │  Interactive      │
    │  Brokers API      │
    └───────────────────┘
```

## Technology Stack

### Backend

- **Python 3.11+** - Primary language (excellent libraries for trading, data analysis, AI)
- **FastAPI** - REST API framework (async, auto-docs, high performance)
- **Celery** - Background task processing (real-time monitoring, scheduled analysis)
- **Redis** - Caching and message broker for Celery
- **PostgreSQL** - Primary database (trades, strategies, user data)
- **TimescaleDB** - Time-series data extension for PostgreSQL (price history, indicators)

### AI & Analysis

- **OpenAI API** (GPT-4) - Market analysis, trade recommendations
- **LangChain** - AI orchestration and prompt management
- **Pandas/NumPy** - Technical indicator calculations
- **TA-Lib** - Professional technical analysis library

### Trading Integration

- **ib_insync** - Interactive Brokers Python API wrapper
- **ccxt** - Multi-exchange library (for future expansion)

### Frontend

- **React + TypeScript** - Web dashboard
- **Chart.js / TradingView Lightweight Charts** - Price charts
- **WebSocket** - Real-time updates

### Mobile/Telegram

- **Telegram Bot API** - Telegram interface
- **React Native** (optional future) - Mobile app

### Infrastructure (AWS)

- **EC2/ECS** - Application hosting
- **RDS PostgreSQL** - Database
- **ElastiCache Redis** - Caching
- **S3** - Logs, backups, model artifacts
- **CloudWatch** - Monitoring and alerts
- **Lambda** - Scheduled tasks (optional)
- **API Gateway** - API management (optional)

## Core Functionalities

### 1. Market Data Collection

- Real-time price feeds from Interactive Brokers
- Historical data storage in TimescaleDB
- Support for major currency pairs (EUR/USD, GBP/USD, USD/JPY, etc.)
- Multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d)

### 2. Technical Analysis Engine

- **Coded Indicators** (fast, reliable):
  - Moving Averages (SMA, EMA, WMA)
  - RSI, MACD, Bollinger Bands
  - Support/Resistance levels
  - Volume indicators
  - Candlestick patterns
- **AI Analysis** (contextual, adaptive):
  - Market sentiment analysis
  - News impact assessment
  - Pattern recognition beyond traditional indicators
  - Risk assessment
  - Trade recommendation reasoning

### 3. AI-Powered Analysis Pipeline

```
Market Data → Technical Indicators → AI Context Builder → OpenAI API → Trade Recommendation
```

**Hybrid Approach:**

- Calculate technical indicators locally (fast, deterministic)
- Send indicator data + market context + news to OpenAI for:
  - Interpretation of indicator combinations
  - Market sentiment analysis
  - Risk assessment
  - Entry/exit recommendations with reasoning

### 4. Real-Time Pair Monitoring

- Background worker (Celery) monitors all configured pairs
- Detects trading opportunities based on:
  - Technical indicator signals
  - AI-generated alerts
  - Custom strategy rules
- Sends notifications via Telegram/Dashboard
- Proposes trades with confidence scores

### 5. Strategy Management

- Multiple strategy support:
  - **Trend Following** - Moving average crossovers, momentum
  - **Mean Reversion** - RSI, Bollinger Bands
  - **Breakout** - Support/Resistance breaks
  - **AI-Driven** - Pure AI recommendations
  - **Hybrid** - Combine technical + AI signals
- Backtesting framework
- Strategy performance tracking

### 6. Risk Management

- Position sizing (fixed, percentage-based, Kelly Criterion)
- Stop-loss and take-profit automation
- Maximum drawdown limits
- Daily loss limits
- Correlation checks (avoid overexposure)

### 7. Paper Trading Engine

- Simulated execution with realistic slippage
- Order book simulation
- Performance tracking vs live market
- Easy switch to live trading

## Interaction Options

### 1. Web Dashboard (Primary)

**Tech:** React + TypeScript + FastAPI

**Features:**

- Real-time price charts with indicators
- Active positions and P&L
- Trade history and analytics
- Strategy configuration
- AI recommendation feed
- Performance metrics and backtesting results

### 2. Telegram Bot (Secondary)

**Tech:** python-telegram-bot

**Features:**

- Trade alerts and notifications
- Quick trade execution commands
- Account status queries
- AI recommendation summaries
- Emergency stop commands

### 3. Mobile App (Future)

**Tech:** React Native

**Features:**

- Simplified dashboard view
- Push notifications
- Quick actions

## Trading Strategies

### Recommended Starting Strategies

1. **AI-Assisted Trend Following**

   - Use EMA crossovers for trend detection
   - AI validates trend strength and market conditions
   - Entry: AI confirms trend + technical signal
   - Exit: AI suggests based on risk/reward

2. **Mean Reversion with AI Filter**

   - RSI oversold/overbought signals
   - AI checks for news events that might break mean reversion
   - Only trade when AI confirms safe conditions

3. **Breakout Strategy**

   - Detect support/resistance levels
   - AI assesses breakout validity vs false breakouts
   - Volume confirmation

4. **Pure AI Strategy** (Experimental)

   - AI analyzes all available data
   - Makes recommendations based on learned patterns
   - Requires careful backtesting

## Project Structure

```
forex-ai-trading-bot/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routes
│   │   ├── core/             # Config, security
│   │   ├── models/           # Database models
│   │   ├── services/
│   │   │   ├── trading/      # Trading engine
│   │   │   ├── market_data/  # Data collection
│   │   │   ├── indicators/   # Technical analysis
│   │   │   ├── ai/           # AI integration
│   │   │   └── strategies/   # Strategy implementations
│   │   ├── workers/          # Celery tasks
│   │   └── utils/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/         # API clients
│   │   └── hooks/
│   └── package.json
├── telegram_bot/
│   └── bot.py
├── infrastructure/
│   ├── docker/
│   ├── terraform/            # AWS infrastructure
│   └── kubernetes/           # Optional K8s configs
├── scripts/
│   ├── setup_db.sh
│   └── deploy.sh
└── README.md
```

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

- Set up project structure
- Configure Interactive Brokers connection
- Implement basic market data collection
- Set up database schema
- Create FastAPI skeleton

### Phase 2: Core Trading (Week 3-4)

- Implement paper trading engine
- Basic order execution
- Risk management module
- Technical indicators library

### Phase 3: AI Integration (Week 5-6)

- OpenAI API integration
- AI analysis pipeline
- Hybrid indicator + AI system
- Recommendation engine

### Phase 4: Strategies (Week 7-8)

- Implement core strategies
- Strategy manager
- Backtesting framework
- Performance tracking

### Phase 5: Real-Time Monitoring (Week 9-10)

- Celery workers for pair monitoring
- Alert system
- Trade proposal generation
- Notification system

### Phase 6: Interfaces (Week 11-12)

- Web dashboard (React)
- Telegram bot
- WebSocket real-time updates
- User authentication

### Phase 7: AWS Deployment (Week 13-14)

- Infrastructure as Code (Terraform)
- CI/CD pipeline
- Monitoring and logging
- Security hardening

## Key Design Decisions

### Analysis Approach: Hybrid (Coded + AI)

**Rationale:**

- **Coded indicators** provide fast, reliable, deterministic signals
- **AI analysis** adds contextual understanding, sentiment, and adaptive reasoning
- Best of both worlds: speed + intelligence
- Cost-effective (fewer AI API calls by pre-filtering with indicators)

### Paper Trading First

- Safe learning environment
- Validate strategies before risking capital
- Test AI recommendations
- Build confidence in the system

### Interactive Brokers

- Professional-grade API
- Good paper trading support
- Wide range of instruments
- Reliable execution

### Python as Primary Language

- Excellent libraries (pandas, numpy, ta-lib)
- Strong AI/ML ecosystem
- Good async support (FastAPI, asyncio)
- Easy integration with trading APIs

## Security Considerations

- API keys stored in AWS Secrets Manager
- Environment-based configuration
- Rate limiting on API endpoints
- Input validation and sanitization
- Audit logging for all trades
- Two-factor authentication for live trading

## Monitoring & Observability

- CloudWatch metrics for:
  - API latency
  - Trade execution times
  - AI API costs
  - System health
- Structured logging (JSON)
- Error tracking (Sentry)
- Performance dashboards

## Next Steps

1. Confirm this architecture approach
2. Set up development environment
3. Create Interactive Brokers paper trading account
4. Obtain OpenAI API key
5. Begin Phase 1 implementation
