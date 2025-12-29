# FOREX AI Trading Bot - Implementation Plan

## Executive Summary

**Goal**: Build a paper trading FOREX bot with AI-powered signal generation, web dashboard, and Telegram notifications.

**Target Timeline**: 3-5 months (part-time, 10-15 hours/week)
**Budget**: $0-5/month (AWS Free Tier Year 1) + ChatGPT Plus ($20/month) → $35-50/month (Cost-Optimized AWS)
**Primary Tech Stack**: Python, FastAPI, React, PostgreSQL + TimescaleDB, Redis, AWS, OpenAI API (GPT-4o)

---

## Technology Stack

### Backend
- **Language**: Python 3.11+ (optimal for ML ecosystem and your intermediate ML experience)
- **API Framework**: FastAPI (async support, WebSocket capabilities)
- **Task Queue**: Celery + Redis (scheduled signal generation)
- **ML Framework**: scikit-learn (Random Forest), optional PyTorch (LSTM)
- **Trading Libraries**: oandapyV20 (broker API), TA-Lib (technical indicators)
- **Backtesting**: vectorbt + custom engine

### Frontend
- **Dashboard**: React + TypeScript + Vite
- **Charts**: TradingView Lightweight Charts
- **State Management**: React Query + Zustand
- **WebSocket**: Socket.io-client

### Data Layer
- **Database**: RDS PostgreSQL with TimescaleDB extension (time-series optimized)
- **Cache**: ElastiCache Redis (pub/sub for real-time updates)
- **Object Storage**: S3 (ML model weights, backtest reports)

### Infrastructure (AWS)
- **Compute**: EC2 t2.micro/t3.micro (Free Tier) → ECS Fargate (later)
- **Monitoring**: CloudWatch + CloudWatch Logs Insights
- **Secrets**: AWS Secrets Manager
- **IaC**: Terraform
- **Networking**: VPC, Security Groups

### Data Sources
- **Primary**: OANDA (FREE practice account with real market data)
- **Optional**: Polygon.io ($99/month, only for historical data bulk download)

---

## System Architecture

```
External APIs (OANDA, Telegram)
    ↓
AWS Load Balancer
    ↓
┌─────────────────────────────────────────────────────┐
│ AWS EC2 (Free Tier Year 1)                          │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ Data         │  │ Strategy     │  │ API +    │ │
│  │ Ingestion    │→ │ Engine       │→ │ WebSocket│ │
│  │ Service      │  │ (ML + Celery)│  │ Service  │ │
│  └──────────────┘  └──────────────┘  └──────────┘ │
│         ↓                  ↓                ↓      │
│  ┌──────────────────────────────────────────────┐ │
│  │         Redis (Docker Container)             │ │
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
│ (Free Tier)     │                    │ (Free Tier) │
└─────────────────┘                    └─────────────┘
         ↓
┌─────────────────────────────────────────────────────┐
│ Client Layer: Web Dashboard + Telegram Bot Client  │
└─────────────────────────────────────────────────────┘
```

---

## ML Strategy: Three-Tier Hybrid Approach

**Decision**: Use local ML for real-time trading + selective ChatGPT for strategic analysis

### Why This Hybrid Approach?

**Local ML (Random Forest) for Real-Time Trading**:
- ✅ Fast inference (<100ms)
- ✅ No per-request costs
- ✅ Deterministic and backtestable
- ✅ Handles high-frequency signals (every 5 minutes)

**ChatGPT for Strategic Analysis**:
- ✅ Market regime detection (trending vs ranging)
- ✅ News sentiment analysis (daily/weekly)
- ✅ Multi-pair correlation insights
- ✅ Strategy performance review
- ✅ Cost-controlled (1-10 API calls per day vs 288+ for real-time)

### Cost Analysis: Hybrid vs Full LLM

**Full LLM Approach** (EXPENSIVE):
- 10 pairs × 12 signals/hour × 24 hours × 30 days = 86,400 API calls/month
- At $0.01 per call (GPT-4) = $864/month
- **Not feasible for budget**

**Hybrid Approach** (AFFORDABLE):
- Real-time signals: Local Random Forest (FREE)
- Strategic analysis: 5-10 ChatGPT calls/day = 150-300 calls/month
- At $0.01-0.03 per call = **$1.50-$9/month**
- **Fits within budget!**

### Three-Tier ML Pipeline

#### Tier 1: Local Real-Time Inference (Fast Layer)

**Purpose**: Generate trading signals every 5 minutes

1. **Feature Engineering** (Local)
   - Technical Indicators: RSI, MACD, Bollinger Bands, ATR, ADX, etc. (TA-Lib)
   - Price Patterns: Candlestick patterns, support/resistance levels
   - Time Features: Hour, day, forex session (London/NY/Tokyo)
   - Multi-timeframe: Aggregate 1m → 5m → 15m → 1h trends

2. **Local ML Models**
   - **Model 1**: Random Forest Classifier (BUY/SELL/HOLD prediction with confidence)
   - **Model 2**: Random Forest Regressor (volatility prediction for position sizing)
   - **Model 3** (Optional Phase 3): LSTM for price movement magnitude

3. **Local Signal Generation**
   - Combine technical indicator filters with ML predictions
   - Only trade when ML confidence > 0.65
   - Apply risk checks (trend alignment, volume confirmation)

#### Tier 2: ChatGPT Strategic Analysis (Smart Layer)

**Purpose**: Higher-level market analysis 1-3 times per day

**When to Call ChatGPT**:
1. **Daily Market Regime Analysis** (1x per day, morning)
   - Send: 24-hour price action summary for all pairs
   - Send: Technical indicator states (RSI levels, MACD crossovers, volatility)
   - Ask: "Is the market trending or ranging? Which pairs show strongest trends?"
   - Use response to: Adjust strategy parameters (use trend-following vs mean reversion)

2. **News Sentiment Analysis** (1-2x per day, when major events occur)
   - Send: Recent news headlines (scraped from free sources)
   - Send: Current positions and exposure
   - Ask: "How might these events affect EUR/USD, GBP/USD, USD/JPY?"
   - Use response to: Reduce position sizes or pause trading during high uncertainty

3. **Performance Review** (1x per day, evening)
   - Send: Daily trade summary (wins, losses, P&L, signals generated)
   - Send: Current strategy parameters
   - Ask: "Analyze today's performance. Are there patterns in winning vs losing trades?"
   - Use response to: Flag issues for manual review, identify strategy drift

4. **Multi-Pair Correlation Analysis** (1x per week)
   - Send: Weekly correlation matrix of all trading pairs
   - Send: Current portfolio composition
   - Ask: "Are we over-exposed to USD? Should we diversify?"
   - Use response to: Adjust pair selection for next week

5. **Strategy Validation** (On-demand, when confidence drops)
   - Send: Recent underperforming signals (low confidence or losses)
   - Send: Market conditions during those signals
   - Ask: "Why might the model be struggling? Has market regime changed?"
   - Use response to: Decide if retraining is needed

#### Tier 3: Human Oversight (Safety Layer)

**Purpose**: Manual approval for high-risk scenarios

- Review ChatGPT strategic insights
- Approve/reject trades in manual mode (via Telegram)
- Override bot during unusual market conditions

### Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     REAL-TIME TRADING LOOP                      │
│                        (Every 5 minutes)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Market Data → Feature Engineering → Random Forest → Signal    │
│     (Fast, Local, FREE)                                         │
│                                                                 │
│  IF signal.confidence > threshold AND regime_filter_passes:     │
│      Execute Trade                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  STRATEGIC ANALYSIS (Daily)                     │
│                    ChatGPT API Integration                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Daily Job (8 AM):                                              │
│    1. Aggregate 24h price action + indicators                  │
│    2. Send to ChatGPT: "Analyze market regime"                 │
│    3. Parse response → Update regime_filter (trending/ranging)  │
│    4. Store analysis in database                               │
│                                                                 │
│  News Event Trigger:                                            │
│    1. Detect major news (economic calendar API - free)          │
│    2. Send to ChatGPT: "Sentiment analysis"                    │
│    3. Parse response → Adjust position_size_multiplier          │
│                                                                 │
│  Evening Review (8 PM):                                         │
│    1. Send daily trade summary to ChatGPT                       │
│    2. Get performance insights                                 │
│    3. Flag anomalies for human review                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Concrete Example: How They Work Together

**Morning (8 AM)**:
```python
# ChatGPT API Call
prompt = f"""
Analyze the following FOREX market data for {date}:

EUR/USD:
- 24h change: +0.35%
- RSI(14): 62 (neutral-bullish)
- MACD: Bullish crossover 2 hours ago
- ATR: 0.0012 (low volatility)

GBP/USD:
- 24h change: -0.18%
- RSI(14): 45 (neutral)
- MACD: Bearish, but histogram narrowing
- ATR: 0.0018 (moderate volatility)

USD/JPY:
- 24h change: +0.22%
- RSI(14): 58 (neutral-bullish)
- MACD: Neutral
- ATR: 0.0015 (moderate volatility)

Question: Is the market in a trending or ranging regime?
Which pairs are best suited for trend-following strategies today?
Keep response under 100 words.
"""

response = openai.chat.completions.create(
    model="gpt-4o-mini",  # Cheaper model, $0.150 per 1M input tokens
    messages=[{"role": "user", "content": prompt}]
)

# Example Response:
# "EUR/USD shows clear trending behavior with bullish MACD and rising RSI.
#  Suitable for trend-following. GBP/USD is ranging with indecisive MACD.
#  Better for mean reversion or avoid. USD/JPY is weakly trending.
#  Recommendation: Focus trend-following on EUR/USD, use tighter filters for USD/JPY."

# Parse and Update Strategy
if "trending" in response.lower() and "EUR/USD" in response:
    strategy_config["EUR/USD"]["mode"] = "trend_following"
    strategy_config["EUR/USD"]["confidence_threshold"] = 0.65
else:
    strategy_config["EUR/USD"]["mode"] = "ranging"
    strategy_config["EUR/USD"]["confidence_threshold"] = 0.75  # Higher bar
```

**Real-Time Trading (Every 5 min)**:
```python
# Local Random Forest generates signal
signal = random_forest.predict(features)  # BUY, confidence=0.72

# Check ChatGPT-informed regime filter
if strategy_config["EUR/USD"]["mode"] == "trend_following":
    if signal.confidence > 0.65:
        execute_trade(signal)  # EXECUTE
else:  # ranging mode
    if signal.confidence > 0.75:  # Higher threshold
        execute_trade(signal)
    # This signal (0.72) is below threshold for ranging, SKIP
```

### Data Sent to ChatGPT (Privacy & Size)

**What to Send**:
- ✅ Aggregated statistics (RSI values, MACD states, price changes)
- ✅ Trade summaries (win rate, P&L, not individual orders)
- ✅ News headlines (public information)
- ✅ Technical patterns (support/resistance levels)

**What NOT to Send**:
- ❌ Raw OHLCV data (too large, unnecessary)
- ❌ API keys or credentials
- ❌ Personal account details
- ❌ Proprietary model weights

**Typical Payload Size**:
- Market regime analysis: ~500 tokens input, ~150 tokens output
- Cost per call: ~$0.001-0.003 (GPT-4o-mini)
- Daily cost (5 calls): **$0.005-0.015**
- Monthly cost: **$0.15-0.45**

### Benefits of This Hybrid Approach

1. **Cost-Effective**: $0.15-9/month for LLM vs $864/month for full LLM
2. **Fast Real-Time Trading**: No latency from API calls on every signal
3. **Strategic Insights**: Leverage GPT-4's reasoning for complex analysis
4. **Backtestable Core**: Local ML is deterministic, can backtest thoroughly
5. **Adaptive**: ChatGPT helps detect regime changes that local model might miss
6. **Explainable**: Natural language insights help you understand market conditions

### Risks and Mitigations

**Risk 1**: ChatGPT hallucinations or bad advice
- **Mitigation**: Never execute trades directly from ChatGPT. Only use for parameter adjustments within safe bounds (e.g., confidence threshold 0.65-0.80)

**Risk 2**: API costs spiral out of control
- **Mitigation**: Hard limit of 10 API calls per day in code. Alert if limit exceeded.

**Risk 3**: Latency for time-sensitive decisions
- **Mitigation**: ChatGPT only for strategic (hourly/daily) analysis, never for per-trade decisions

**Risk 4**: Non-deterministic backtesting
- **Mitigation**: Log all ChatGPT responses in database. Replay logged responses during backtests for consistency.

---

## Trading Strategy (MVP)

### Strategy: Trend-Following with ML Confirmation

**Entry Rules (BUY Signal)**:
1. EMA(12) > EMA(26) [short-term uptrend]
2. Price > SMA(50) [medium-term uptrend]
3. RSI(14) between 40-70 [not overbought]
4. MACD histogram positive and increasing
5. ML Random Forest predicts BUY with confidence > 0.65
6. Volume > 20-period average [confirmation]

**Exit Rules**:
- Stop Loss: 1.5 × ATR(14) from entry
- Take Profit: 2.5 × ATR(14) from entry (Risk:Reward = 1:1.67)
- Trailing Stop: Once profit > 1.5×ATR, trail SL at 1×ATR
- Time-based: Exit after 4 hours if no TP/SL hit

**Risk Management**:
- Risk 1% of account per trade
- Max 3 concurrent positions across all pairs
- Daily loss limit: 3% (circuit breaker)

**Trading Pairs (Start with 3)**:
- EUR/USD (most liquid, tight spreads)
- GBP/USD (high volatility, clear trends)
- USD/JPY (stable, good for mean reversion)

**Timeframe**: 5-minute bars

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-3) - 40-60 hours

**Week 1: Local Development Setup**
- Initialize project structure (monorepo: backend + frontend + infrastructure)
- Set up Poetry dependencies (pandas, scikit-learn, FastAPI, TA-Lib, etc.)
- Create Docker Compose (PostgreSQL + TimescaleDB + Redis)
- Set up OANDA practice account and test API connection
- Create database schema with TimescaleDB hypertables

**Week 2: Data Ingestion**
- Build OANDA client wrapper (streaming OHLCV data)
- Implement data ingestion service (normalize and store to TimescaleDB)
- Set up Redis pub/sub for real-time data broadcast
- Download 6-12 months historical data (EUR/USD, GBP/USD, USD/JPY)
- Write unit tests for data pipeline

**Week 3: Basic API**
- Build FastAPI service with core endpoints:
  - `GET /market-data/{pair}`
  - `GET /signals`
  - `GET /positions`
- Set up structured JSON logging
- Create initial Terraform configs (VPC, RDS, EC2)
- Test end-to-end: OANDA → PostgreSQL → API

**Deliverable**: Data flowing from OANDA to PostgreSQL, queryable via API

---

### Phase 2: Strategy & ML (Weeks 4-7) - 70-90 hours

**Week 4: Feature Engineering**
- Implement TA-Lib wrapper for technical indicators:
  - Trend: SMA(20,50,200), EMA(12,26), MACD, ADX
  - Momentum: RSI(14), Stochastic, Williams %R
  - Volatility: Bollinger Bands, ATR
- Build feature engineering pipeline
- Create multi-timeframe aggregation (1m → 5m → 15m → 1h)
- Create aggregation service for ChatGPT prompts (24h summaries)
- Exploratory analysis in Jupyter notebook

**Week 5: ML Model Training + ChatGPT Integration**
- **Local ML Models**:
  - Prepare training dataset (label: future price movement)
  - Train Random Forest direction classifier (BUY/SELL/HOLD)
  - Train volatility predictor (Random Forest Regressor)
  - Evaluate models (precision, recall, confusion matrix)
  - Save models to S3 with versioning
  - Implement model loading and inference

- **ChatGPT Integration** (NEW):
  - Set up OpenAI API client (use your ChatGPT Plus API key)
  - Create `llm_analyzer.py` service with rate limiting (10 calls/day max)
  - Implement prompt templates for:
    - Market regime analysis
    - News sentiment analysis
    - Performance review
  - Build response parser to extract structured data (trending/ranging, confidence adjustments)
  - Add database table for storing ChatGPT analysis history
  - Create Celery scheduled tasks for daily/weekly LLM analysis

**Week 6: Signal Generation with Regime Awareness**
- Build signal generator combining ML predictions
- Implement signal filters (trend alignment, volume confirmation)
- Add confidence scoring logic
- **Add regime-aware filtering** (NEW):
  - Read current market regime from ChatGPT analysis cache
  - Adjust confidence thresholds based on regime (0.65 for trending, 0.75 for ranging)
  - Skip pairs that ChatGPT flagged as "avoid"
- Set up Celery Beat for scheduled signal generation (every 5 minutes)
- Store signals in PostgreSQL and publish to Redis
- **Add Celery Beat jobs for ChatGPT analysis**:
  - Daily 8 AM: Market regime analysis
  - Daily 8 PM: Performance review
  - On major news events: Sentiment analysis
  - Weekly Sunday: Correlation analysis

**Week 7: Risk Management with LLM Insights**
- Implement position sizing (based on volatility and account size)
- Calculate stop loss and take profit levels (ATR-based)
- Add risk checks: max positions, max exposure, daily loss limit
- **Integrate ChatGPT risk adjustments** (NEW):
  - Apply position size multipliers from news sentiment (0.5x during high uncertainty)
  - Implement emergency pause trigger from ChatGPT "extreme risk" signals
  - Add daily loss limit with ChatGPT trend analysis override (tighter limits in ranging markets)
- Build order builder (convert signal → OANDA order format)
- Unit tests for risk management
- **Test ChatGPT integration end-to-end**:
  - Simulate daily regime analysis → strategy adjustment → signal generation
  - Verify API rate limiting works (10 calls/day hard cap)
  - Test response logging for backtesting replay

**Deliverable**: Automated signal generation with local ML + ChatGPT strategic overlay

---

### Phase 3: Execution & Backtesting (Weeks 8-10) - 50-70 hours

**Week 8: Order Execution**
- Build execution service
- Implement OANDA order submission (market orders to practice account)
- Add order status tracking (pending → filled → closed)
- Build position manager (track open positions, calculate P&L)
- Implement SL/TP monitoring (close positions when triggered)
- Store all trades in PostgreSQL with audit logs

**Week 9: Backtesting Engine**
- Build backtesting engine:
  - Load historical data from TimescaleDB
  - Simulate signal generation with historical features
  - Simulate order execution (model slippage and spread)
  - Track positions and P&L over time
- Calculate performance metrics:
  - Total return, Sharpe ratio, max drawdown
  - Win rate, profit factor, avg win/loss
- Generate HTML backtest reports with charts

**Week 10: Strategy Validation**
- Run backtests on 6-12 months of data for major pairs
- Analyze results and identify issues
- Tune hyperparameters (confidence threshold, position size, SL/TP)
- Run walk-forward validation (train on N months, test on M months)
- Document strategy performance and expected metrics

**Deliverable**: Working paper trading bot + validated backtest results

---

### Phase 4: User Interfaces (Weeks 11-13) - 50-60 hours

**Week 11: Web Dashboard Backend**
- Expand FastAPI with all endpoints:
  - `GET /positions`, `GET /trades`, `GET /performance`
  - `POST /bot/start`, `POST /bot/stop`
  - `POST /backtest` (run backtest with parameters)
- Implement WebSocket server (Socket.io):
  - Real-time market data updates
  - Signal notifications
  - Position/trade updates
- Add JWT authentication

**Week 12: Web Dashboard Frontend**
- Set up React + TypeScript + Vite project
- Implement TradingView Lightweight Charts
- Build dashboard components:
  - Live price chart with indicators
  - Position list with real-time P&L
  - Trade history table
  - Signal feed (recent signals with confidence)
  - P&L summary (daily, weekly, all-time)
  - Bot controls (start/stop, strategy selection)
- Implement WebSocket client for real-time updates
- Responsive design (desktop + tablet)

**Week 13: Telegram Bot**
- Set up python-telegram-bot
- Implement commands:
  - `/status` - Bot status (running/stopped, active pairs)
  - `/positions` - Current positions with P&L
  - `/signals` - Recent signals (last 10)
  - `/pnl` - Quick P&L summary
  - `/approve <signal_id>` - Approve pending signal (manual mode)
- Implement notifications:
  - New signal generated (with approve/reject buttons)
  - Trade executed
  - Position closed (with P&L)
  - Daily P&L summary
- Add inline keyboards for interactive commands

**Deliverable**: Fully functional web dashboard + Telegram bot

---

### Phase 5: AWS Deployment (Weeks 14-15) - 30-40 hours

**Week 14: Infrastructure & Deployment**
- Finalize Terraform configs for AWS Free Tier resources:
  - VPC with public subnet
  - EC2 t2.micro/t3.micro (Free Tier)
  - RDS db.t2.micro/t3.micro (Free Tier)
  - S3 buckets (Free Tier)
  - Security Groups
- Build Docker images for all services
- Deploy to EC2 using Docker Compose
- Set up secrets in AWS Secrets Manager
- Deploy TimescaleDB schema to RDS
- Test end-to-end in AWS environment

**Week 15: Monitoring & Production Readiness**
- Set up CloudWatch Logs for all services (structured JSON logging)
- Create CloudWatch dashboards:
  - Trading metrics (signals/hour, trades/day, P&L)
  - System metrics (CPU, memory, latency)
  - Error rates, API failures
- Configure CloudWatch Alarms:
  - Error rate > 5%
  - OANDA API failures
  - Daily loss > threshold
- Set up automated RDS backups
- Deploy frontend to S3 + CloudFront (Free Tier)
- Document deployment process
- **GO LIVE with paper trading!**

**Deliverable**: Production-ready bot running on AWS Free Tier

---

### Phase 6: Optimization & Enhancements (Weeks 16+)

**Optional Enhancements** (prioritize based on Phase 5 results):
- Add LSTM model for price prediction (if RF insufficient)
- Implement mean reversion strategy (Bollinger Bands)
- Multi-pair portfolio optimization
- Automated model retraining pipeline (weekly)
- A/B testing framework for strategies
- Advanced backtesting (Monte Carlo simulation)
- Algorithmic pair selection (real-time identification of high-potential pairs)
- Native mobile app (React Native)

---

## Project Directory Structure

```
forex-ai-trading-bot/
├── README.md
├── PLAN.md                    # This file
├── .gitignore
├── .env.example
│
├── backend/
│   ├── pyproject.toml         # Poetry dependencies
│   ├── poetry.lock
│   ├── pytest.ini
│   │
│   ├── shared/
│   │   ├── config.py          # Configuration management (CRITICAL)
│   │   ├── database.py        # SQLAlchemy models (CRITICAL)
│   │   ├── logger.py
│   │   └── redis_client.py
│   ├── data_ingestion/
│   │   ├── oanda_client.py    # OANDA API wrapper (CRITICAL)
│   │   └── main.py
│   ├── strategy_engine/
│   │   ├── features/
│   │   │   └── technical_indicators.py  # TA-Lib wrapper (CRITICAL)
│   │   ├── models/
│   │   │   └── direction_classifier.py  # Random Forest (CRITICAL)
│   │   ├── llm/                         # ChatGPT integration (NEW)
│   │   │   ├── __init__.py
│   │   │   ├── llm_analyzer.py          # OpenAI API client (CRITICAL)
│   │   │   ├── prompt_templates.py      # Prompt templates for different analyses
│   │   │   ├── response_parser.py       # Parse LLM responses to structured data
│   │   │   └── rate_limiter.py          # 10 calls/day hard limit
│   │   ├── signals/
│   │   │   ├── signal_generator.py
│   │   │   └── regime_filter.py         # Filter signals based on LLM regime analysis (NEW)
│   │   └── risk_management.py
│   ├── execution/
│   │   ├── order_manager.py
│   │   └── position_manager.py
│   ├── api/
│   │   ├── main.py           # FastAPI app (CRITICAL)
│   │   └── routers/
│   ├── telegram_bot/
│   │   └── main.py
│   ├── backtesting/
│   │   └── engine.py
│   └── ml_training/
│       └── train_classifier.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── components/
│       ├── pages/
│       └── services/
│
├── infrastructure/
│   ├── terraform/
│   │   └── main.tf           # Terraform entry (CRITICAL)
│   └── docker/
│       └── docker-compose.yml  # Local dev environment (CRITICAL)
│
├── scripts/
│   ├── download_historical_data.py
│   └── run_backtest.py
│
└── notebooks/
    └── exploratory_data_analysis.ipynb
```

---

## Budget: AWS Free Tier Strategy

### Option 6: AWS Free Tier Maximization - $20-25/month (First Year)

**Setup** (within AWS Free Tier limits):
- **EC2**: t2.micro or t3.micro (750 hours/month FREE for 12 months)
- **RDS**: db.t2.micro or db.t3.micro (750 hours/month FREE for 12 months)
- **S3**: 5GB storage FREE
- **CloudWatch**: 10 custom metrics FREE
- **Data Transfer**: 15GB outbound FREE

**Additional costs**:
- **ChatGPT Plus**: $20/month (includes API access with higher rate limits)
  - Note: OpenAI API is separate from ChatGPT Plus, but Plus subscription gives you $5 credit/month
  - Actual API cost: ~$0.15-2/month for 5-10 calls/day with GPT-4o-mini
  - Alternative: Use free tier ($5 credit on signup) for first 3 months
- **Elastic IP** (when attached to running instance): FREE
- **RDS storage**: 20GB SSD FREE
- **Domain name** (optional): $12/year

**Total Year 1**:
- With ChatGPT Plus: $20-25/month
- Without Plus (API only): $0.15-7/month

**After Year 1**: Transition to Cost-Optimized AWS ($35-50/month) + ChatGPT API (~$2-9/month)

---

## Top 10 MVP Functionalities (Prioritized)

1. **Real-time Market Data Streaming** [P0]
2. **ML-Based Signal Generation** [P0]
3. **Automated Order Execution (Paper Trading)** [P0]
4. **Position & P&L Tracking** [P0]
5. **Web Dashboard with Real-time Charts** [P1]
6. **Backtesting Engine** [P1]
7. **Telegram Bot for Alerts & Commands** [P1]
8. **Risk Management System** [P1]
9. **Strategy Configuration & Switching** [P2]
10. **Monitoring & Alerting** [P2]

---

## Success Metrics (Target for End of Phase 5)

### Backtest Performance
- Sharpe Ratio > 1.0 (risk-adjusted returns)
- Win Rate > 50% OR Profit Factor > 1.5
- Max Drawdown < 15%
- Annual Return > 15% (paper trading simulation)

### System Performance
- Signal generation latency < 2 seconds
- API response time < 500ms (p95)
- WebSocket message latency < 200ms
- System uptime > 99.5%

### Paper Trading (3-6 month validation before live)
- Consistent with backtest results (±10%)
- No circuit breaker triggers (daily loss limit)
- All trades properly logged and auditable

---

## Next Steps to Begin Implementation

1. **Set up OANDA practice account** (15 minutes)
   - Go to oanda.com, create practice account
   - Generate API token for v20 API

2. **Set up OpenAI API access** (10 minutes)
   - Go to platform.openai.com/api-keys
   - Create new API key (starts with `sk-proj-...`)
   - Note: ChatGPT Plus subscription is separate from API access
   - You'll need to add payment method for API usage (but actual cost is ~$0.15-2/month)
   - Store API key securely (will go in AWS Secrets Manager later)

3. **Initialize project repository** (30 minutes)
   - Create directory structure
   - Initialize git repository
   - Set up Poetry (`pyproject.toml`)
   - Add dependencies: `openai`, `pandas`, `scikit-learn`, `fastapi`, `oandapyV20`, `ta-lib`

4. **Create Docker Compose for local dev** (1 hour)
   - PostgreSQL with TimescaleDB extension
   - Redis
   - PgAdmin (optional, for database inspection)

5. **Download historical data** (2-4 hours)
   - Write script to pull 6-12 months OHLCV from OANDA
   - Store in TimescaleDB for model training

6. **Build first critical files** (Week 1)
   - `config.py`, `database.py`, `oanda_client.py`
   - Get data flowing end-to-end

7. **Test ChatGPT integration** (Week 5)
   - Create simple `llm_analyzer.py` script
   - Test API connection with sample prompt
   - Verify rate limiting works (10 calls/day)

---

## Recommended Resources

### Learning
- **TA-Lib Documentation**: Technical indicator calculations
- **OANDA v20 API Docs**: Streaming data, order execution
- **TimescaleDB Tutorials**: Time-series optimization
- **Backtest Analysis**: "Evidence-Based Technical Analysis" by David Aronson

### Communities
- r/algotrading - Strategy discussions
- QuantConnect Forums - Algorithmic trading
- OANDA Community - API support

---

## Summary

This plan provides a **realistic, phased approach** to building a production-ready FOREX AI trading bot:

✓ **Leverages your DevOps expertise** (AWS, Terraform, containerization)
✓ **Matches your ML experience** (Random Forest, feature engineering, scikit-learn)
✓ **FREE for Year 1** (AWS Free Tier: $0-5/month)
✓ **Paper trading first** (validate before risking capital)
✓ **Modern tech stack** (Python, FastAPI, React, TimescaleDB)
✓ **Cost-effective ML** (custom models, not expensive LLM APIs)
✓ **Real-time interfaces** (Web dashboard + Telegram bot)

**Estimated Total Time**: 3-5 months part-time (230-310 hours) to production-ready MVP

The architecture is designed to **scale** as you gain confidence - start with 3 pairs and 1 strategy, expand to 10+ pairs and multiple strategies in Phase 6+.
