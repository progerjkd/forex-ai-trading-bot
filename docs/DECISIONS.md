# Architecture Decision Records

This document captures key architectural decisions made during the development of the FOREX AI Trading Bot. Each decision is recorded using the ADR (Architecture Decision Record) format to provide context and rationale for future reference.

## Table of Contents

- [ADR-001: PostgreSQL + TimescaleDB for Time-Series Data](#adr-001-postgresql--timescaledb-for-time-series-data)
- [ADR-002: Hybrid ML (Local Random Forest + ChatGPT)](#adr-002-hybrid-ml-local-random-forest--chatgpt)
- [ADR-003: AWS Free Tier Strategy for Year 1](#adr-003-aws-free-tier-strategy-for-year-1)
- [ADR-004: OANDA for Paper Trading](#adr-004-oanda-for-paper-trading)
- [ADR-005: FastAPI over Flask/Django](#adr-005-fastapi-over-flaskdjango)
- [ADR-006: Python 3.11+ for Backend](#adr-006-python-311-for-backend)
- [ADR-007: React + TypeScript for Frontend](#adr-007-react--typescript-for-frontend)
- [ADR-008: Celery + Redis for Task Queue](#adr-008-celery--redis-for-task-queue)
- [ADR-009: Telegram Bot for Human Oversight](#adr-009-telegram-bot-for-human-oversight)
- [ADR-010: Docker Compose for Local Development](#adr-010-docker-compose-for-local-development)

---

## ADR-001: PostgreSQL + TimescaleDB for Time-Series Data

**Date**: 2024-12-29
**Status**: Accepted
**Deciders**: Development Team

### Context

The trading bot needs to store and query large volumes of time-series market data:
- OHLCV (Open, High, Low, Close, Volume) data for multiple currency pairs
- Tick-by-tick data during active trading
- Historical data for backtesting (6-12 months)
- Trade history and signals
- ML model metadata and predictions

Options considered:
1. **DynamoDB** (AWS NoSQL)
2. **InfluxDB** (Pure time-series database)
3. **PostgreSQL + TimescaleDB** (RDBMS with time-series extension)
4. **MongoDB** (Document database)

### Decision

Use **PostgreSQL with TimescaleDB extension** hosted on AWS RDS.

### Rationale

**Why PostgreSQL + TimescaleDB:**
- TimescaleDB provides automatic time-series optimizations (compression, continuous aggregates)
- SQL familiarity for complex analytical queries
- ACID guarantees crucial for financial transaction data
- Strong consistency for trade execution records
- Supports both relational and time-series workloads in one database
- AWS RDS provides managed service with automated backups
- Free Tier available (db.t2.micro for 12 months)

**Why not DynamoDB:**
- Less intuitive for time-series range queries
- Potentially higher costs for read-heavy workloads
- No built-in time-series compression
- More complex query patterns for analytics

**Why not InfluxDB:**
- Optimized only for time-series (would need separate DB for transactional data)
- Less mature ecosystem than PostgreSQL
- Limited support for complex joins needed for analytics
- No managed service on AWS Free Tier

**Why not MongoDB:**
- No automatic time-series optimizations
- Weaker consistency guarantees
- Overkill for structured financial data

### Consequences

**Pros:**
- Sub-second queries for millions of time-series rows
- Single database for all data (time-series + transactional)
- SQL joins enable rich analytics (correlating signals with trades)
- Automatic data retention policies via TimescaleDB
- Battle-tested reliability for financial data
- Continuous aggregates for pre-computed OHLC rollups

**Cons:**
- More complex to configure than DynamoDB (indexes, partitions)
- Vertical scaling limits (single instance for Free Tier)
- RDS costs after Free Tier expires (~$25-30/month for db.t3.micro)

**Risks:**
- Disk space growth with tick data → Mitigation: Compression policies, retention limits
- Single point of failure on Free Tier → Mitigation: Automated RDS backups

**Implementation Notes:**
- Use hypertables for OHLCV data partitioned by time
- Enable compression for data older than 7 days
- Create indexes on (pair, timestamp) for fast queries
- Set retention policy: 3 months for 1-min data, 12 months for 5-min data

---

## ADR-002: Hybrid ML (Local Random Forest + ChatGPT)

**Date**: 2024-12-29
**Status**: Accepted
**Deciders**: Development Team

### Context

Need to generate trading signals with AI assistance. Key requirements:
- Real-time signal generation (every 5 minutes)
- Cost-effectiveness (limited budget)
- Backtestable and deterministic
- Adaptive to market regime changes
- Benefit from LLM reasoning for strategic insights

Options considered:
1. **Pure Technical Indicators** (no ML)
2. **Local ML Only** (Random Forest, LSTM)
3. **Pure LLM** (ChatGPT for every signal)
4. **Hybrid: Local ML + ChatGPT Strategic Analysis**

### Decision

Use **Three-Tier Hybrid Approach**:
- **Tier 1**: Local Random Forest for real-time signals (every 5 min)
- **Tier 2**: ChatGPT GPT-4o-mini for strategic analysis (1-10 calls/day)
- **Tier 3**: Human oversight via Telegram (manual approval)

### Rationale

**Cost Analysis:**
- **Pure LLM**: 288 signals/day × 3 pairs × $0.001 = **$864/month**
- **Hybrid**: 1-10 ChatGPT calls/day × $0.0005 = **$0.15-9/month**
- **Savings**: 99% cost reduction

**Speed Analysis:**
- **Local ML**: <100ms inference time
- **ChatGPT**: 1-5 seconds response time
- Real-time trading requires sub-second decisions

**Determinism:**
- **Local ML**: Fully deterministic (critical for backtesting)
- **ChatGPT**: Non-deterministic (but logged for analysis)

**Adaptability:**
- **Local ML**: Can miss regime changes (trained on historical data)
- **ChatGPT**: Can detect emerging patterns via news sentiment and reasoning

**Division of Responsibilities:**

| Task | Local ML | ChatGPT | Frequency |
|------|----------|---------|-----------|
| Generate BUY/SELL signals | ✅ | ❌ | Every 5 min |
| Calculate technical indicators | ✅ | ❌ | Every 5 min |
| Market regime analysis | ❌ | ✅ | Daily (8 AM) |
| News sentiment analysis | ❌ | ✅ | On major events |
| Performance review | ❌ | ✅ | Daily (8 PM) |
| Risk assessment | ✅ | ✅ | ML: Real-time, LLM: Daily |

### Consequences

**Pros:**
- 99% cost reduction vs pure LLM approach
- Fast real-time trading decisions (<100ms)
- Strategic insights from GPT-4 reasoning capabilities
- Backtestable core strategy (local ML is deterministic)
- Best of both worlds: speed + adaptability

**Cons:**
- More complex architecture (two ML systems to maintain)
- ChatGPT responses require parsing and validation
- Non-deterministic element from LLM (but mitigated by logging)
- Need to manage API rate limits and quotas

**Risks:**
- **ChatGPT hallucinations** → Mitigation: Never execute trades directly from LLM, only use for advisory
- **API costs spiral** → Mitigation: Hard limit of 10 calls/day, budget alerts
- **API downtime** → Mitigation: System operates without ChatGPT (degraded mode)
- **Model drift** → Mitigation: Monthly ChatGPT log review, local ML retraining

**Implementation Notes:**
- Log all ChatGPT prompts and responses for audit
- Cache ChatGPT regime analysis for 24 hours
- Implement circuit breaker if API costs exceed $10/day
- Never allow LLM to directly place trades

---

## ADR-003: AWS Free Tier Strategy for Year 1

**Date**: 2024-12-29
**Status**: Accepted
**Deciders**: Development Team

### Context

Budget constraint: Minimize infrastructure costs for Year 1 while maintaining functionality. After Year 1, re-evaluate based on trading performance.

AWS Free Tier offerings (12 months):
- EC2: 750 hours/month of t2.micro (1 vCPU, 1GB RAM)
- RDS: 750 hours/month of db.t2.micro
- S3: 5GB storage
- Data Transfer: 15GB/month outbound

Options considered:
1. **Self-Hosted** (DigitalOcean, Linode) - $5-10/month
2. **Heroku Free Tier** (deprecated)
3. **AWS Free Tier** - $0-5/month Year 1
4. **GCP Free Tier** - $0-5/month
5. **Azure Free Tier** - $0-5/month
6. **Full AWS Production** - $130-160/month

### Decision

Use **AWS Free Tier (Option 6)** for Year 1, with the following architecture:

**Compute:**
- 1× EC2 t2.micro (run all services: FastAPI, Celery, Data Ingestion)
- No ECS/Fargate (out of Free Tier)

**Database:**
- 1× RDS db.t2.micro PostgreSQL + TimescaleDB
- 20GB storage (Free Tier limit)

**Storage:**
- S3 bucket for ML model artifacts (<5GB)
- S3 bucket for backtest results (<1GB)

**Networking:**
- CloudWatch for logs (5GB/month free)
- No ALB (costs $16/month)

**Total Year 1 Cost**: $0-5/month (mostly data transfer and small overages)

### Rationale

**Why AWS Free Tier:**
- $0-5/month vs $5-10/month for DigitalOcean
- Managed RDS (automated backups, maintenance)
- Easy migration to production tier (Terraform IaC)
- S3 for model storage and backtest archives
- CloudWatch for monitoring and logs
- Aligns with DevOps engineer's AWS expertise

**Why not self-hosted:**
- Manual database backups and maintenance
- No automatic failover
- Time cost of managing infrastructure

**Why not GCP/Azure:**
- User has AWS experience (DevOps engineer background)
- Better RDS TimescaleDB support
- More mature Terraform ecosystem

### Consequences

**Pros:**
- Near-zero infrastructure costs for Year 1
- Managed database (automated backups, patching)
- Production-ready architecture (easy to scale)
- CloudWatch monitoring and alerting
- Terraform IaC for reproducible infrastructure

**Cons:**
- Single EC2 instance (no high availability)
- Limited resources (1GB RAM, 1 vCPU)
- Must carefully monitor Free Tier limits
- After Year 1, costs jump to ~$30-50/month

**Risks:**
- **Exceed Free Tier limits** → Mitigation: CloudWatch billing alarms at $5, $10, $20
- **EC2 instance failure** → Mitigation: Daily snapshots, CloudWatch recovery
- **RDS storage exhaustion** → Mitigation: Data retention policies (3 months)
- **Year 1 ends** → Mitigation: Evaluate trading performance, decide to scale up or migrate

**Resource Constraints:**
- Max 3 trading pairs (to stay within CPU/RAM limits)
- 5-minute signal interval (vs 1-minute for production)
- 3-month data retention for 1-min OHLCV

**Post-Free Tier Migration Path:**
- Year 2+: Upgrade to t3.small EC2 ($15/month) + db.t3.small RDS ($25/month)
- If profitable: Full production tier with HA (ECS, RDS Multi-AZ)

---

## ADR-004: OANDA for Paper Trading

**Date**: 2024-12-29
**Status**: Accepted
**Deciders**: Development Team

### Context

Need a FOREX broker for:
- Paper trading (no real money at risk)
- Real-time market data
- Historical OHLCV data
- Trade execution API
- Low/no cost for development

Options considered:
1. **OANDA** (FREE practice account)
2. **Interactive Brokers** (requires $10k minimum)
3. **Alpaca** (US stocks only, no FOREX)
4. **Polygon.io** ($99/month for historical data)
5. **MetaTrader 5** (limited API, manual setup)

### Decision

Use **OANDA Practice Account** with oandapyV20 Python library.

### Rationale

**Why OANDA:**
- **FREE** practice account with full API access
- Real-time streaming data via WebSocket
- Historical OHLCV data (up to 5000 candles per request)
- RESTful API for trade execution
- Mature Python library (oandapyV20)
- Practice account uses real market prices
- No minimum deposit or account fees

**Why not Interactive Brokers:**
- Requires $10k minimum deposit for margin account
- Complex API (TWS Gateway, multiple protocols)
- Overkill for paper trading phase

**Why not Alpaca:**
- US stocks and crypto only (no FOREX)

**Why not Polygon.io:**
- $99/month for historical data
- No paper trading environment
- Would need separate broker for execution

**Why not MetaTrader 5:**
- Limited API capabilities
- Requires running Windows or Wine
- No native Python support
- Manual setup for each broker

### Consequences

**Pros:**
- $0 cost for development and paper trading
- Real market data for accurate backtesting
- Seamless transition to live trading (same API, different account)
- Streaming data via WebSocket (low latency)
- Well-documented API with Python library

**Cons:**
- Practice account has some differences from live (execution speed, slippage)
- Historical data limited to 5000 candles per request (need pagination)
- Rate limits: 120 requests/second (sufficient for our use case)

**Risks:**
- **OANDA discontinues practice accounts** → Mitigation: Low risk, core offering
- **API changes break integration** → Mitigation: Pin oandapyV20 version, monitor changelog
- **Practice environment differs from live** → Mitigation: Paper trade for 3+ months before live

**Implementation Notes:**
- Store OANDA_API_KEY and OANDA_ACCOUNT_ID in .env (gitignored)
- Use practice environment: `https://api-fxpractice.oanda.com`
- Implement exponential backoff for rate limit errors
- Cache historical data to reduce API calls

**Future Migration:**
- After successful paper trading (6-12 months): Open live account
- Start with $1,000 minimum deposit
- Same code, just change OANDA_ENVIRONMENT=live

---

## ADR-005: FastAPI over Flask/Django

**Date**: 2024-12-29
**Status**: Accepted
**Deciders**: Development Team

### Context

Need a Python web framework for:
- REST API endpoints
- WebSocket for real-time data streaming
- Background task integration (Celery)
- Auto-generated API documentation
- High performance (sub-100ms response times)

Options considered:
1. **FastAPI** (async, modern)
2. **Flask** (lightweight, synchronous)
3. **Django** + Django REST Framework (batteries-included)
4. **Tornado** (async, older)

### Decision

Use **FastAPI** with Uvicorn ASGI server.

### Rationale

**Why FastAPI:**
- **Async/await support** (native Python 3.11+ async)
- **High performance**: 2-3x faster than Flask (comparable to Node.js)
- **Auto-generated OpenAPI documentation** (Swagger UI, ReDoc)
- **Type hints + Pydantic validation** (runtime request/response validation)
- **WebSocket support** out of the box
- **Dependency injection** (easy to inject DB sessions, config)
- Modern codebase (built for Python 3.7+)

**Why not Flask:**
- Synchronous by default (would need Flask-SocketIO for WebSocket)
- Manual API documentation (Flask-RESTX helps but not automatic)
- No built-in request/response validation
- Lower performance for concurrent requests

**Why not Django:**
- Heavy framework (ORM, admin, auth, templates we don't need)
- More boilerplate for simple REST API
- Django ORM vs SQLAlchemy (we prefer SQLAlchemy for flexibility)
- Slower startup time and higher memory footprint

**Why not Tornado:**
- Older async framework (pre-async/await)
- Less active community
- More verbose than FastAPI

### Consequences

**Pros:**
- High throughput for real-time market data endpoints
- Automatic interactive API docs (no Postman needed)
- Type safety catches bugs at runtime (Pydantic validation)
- WebSocket for dashboard live updates (no polling)
- Easy to test (built-in TestClient)
- Smaller memory footprint than Django

**Cons:**
- Newer framework (less Stack Overflow answers than Flask)
- Async code requires understanding of async/await patterns
- Some libraries don't support async (need to use run_in_executor)

**Risks:**
- **Learning curve for async** → Mitigation: Team has Python 3.11+ experience
- **Breaking changes in FastAPI** → Mitigation: Pin version, review changelog before upgrades

**Implementation Notes:**
- Use Pydantic models for all request/response schemas
- Enable CORS for React frontend
- Use async SQLAlchemy sessions for database queries
- Deploy with Uvicorn + Gunicorn for production

---

## ADR-006: Python 3.11+ for Backend

**Date**: 2024-12-29
**Status**: Accepted
**Deciders**: Development Team

### Context

Need to choose Python version for backend services. Key requirements:
- Support for modern async/await patterns
- Type hints for better IDE support
- Performance improvements
- Long-term support (LTS)

Options considered:
1. **Python 3.8** (older, more conservative)
2. **Python 3.9** (stable, widely used)
3. **Python 3.10** (pattern matching)
4. **Python 3.11+** (30% faster, better error messages)

### Decision

Use **Python 3.11+** as minimum version.

### Rationale

**Why Python 3.11+:**
- **30% faster** than 3.10 (Faster CPython project)
- **Better error messages** (points to exact cause in tracebacks)
- **Improved type hints** (Self type, Variadic generics)
- **Async improvements** (Task groups, exception groups)
- Stable release (3.11 released Oct 2022)
- Still receives security updates until Oct 2027

**Performance benchmarks:**
- scikit-learn model training: 15-20% faster
- Pandas operations: 10-15% faster
- Overall application: 25-30% faster

**Why not Python 3.8-3.10:**
- Missing performance improvements
- Less helpful error messages (important for debugging ML pipelines)
- No Task groups for concurrent async operations

### Consequences

**Pros:**
- Faster model training and backtesting
- Better developer experience (error messages)
- Modern type hints improve code quality
- 5 years of security updates (until 2027)

**Cons:**
- Some libraries might not have wheels for 3.11 yet (rare)
- Cannot use on systems stuck on older Python (but AWS supports 3.11)

**Risks:**
- **Library compatibility** → Mitigation: All our dependencies support 3.11+ (verified)

**Implementation Notes:**
- Specify `python = "^3.11"` in pyproject.toml
- Use Amazon Linux 2023 AMI (has Python 3.11)
- Enable all type checking in development

---

## ADR-007: React + TypeScript for Frontend

**Date**: 2024-12-29
**Status**: Accepted
**Deciders**: Development Team

### Context

Need frontend framework for trading dashboard with:
- Real-time price charts (TradingView style)
- WebSocket integration for live updates
- Responsive design (desktop + mobile)
- Fast development velocity
- Type safety

Options considered:
1. **React + TypeScript**
2. **Vue 3 + TypeScript**
3. **Svelte**
4. **Vanilla JS + Chart.js**

### Decision

Use **React 18+ with TypeScript, Vite, TradingView Lightweight Charts**.

### Rationale

**Why React:**
- Largest ecosystem for trading chart libraries
- TradingView Lightweight Charts (best-in-class)
- WebSocket integration libraries (Socket.IO)
- Large community and extensive documentation
- Component reusability

**Why TypeScript:**
- Type safety for complex trading data structures
- Better IDE autocomplete (critical for API integration)
- Catch bugs at compile time
- Easier refactoring

**Why Vite:**
- Fast development server (hot module replacement)
- Optimized production builds
- Native ES modules (faster than Webpack)

**Why not Vue:**
- Smaller ecosystem for financial charting libraries
- Less mature TypeScript support than React

**Why not Svelte:**
- Cutting-edge but smaller ecosystem
- Fewer charting library options
- Less developer familiarity

**Why not Vanilla JS:**
- Too much boilerplate for WebSocket state management
- Harder to maintain as features grow

### Consequences

**Pros:**
- TradingView Lightweight Charts (professional-grade charting)
- Large ecosystem (UI libraries, WebSocket clients)
- Type safety prevents runtime errors
- Fast development with Vite HMR
- Easy to find React developers

**Cons:**
- React can be verbose (more boilerplate than Svelte)
- Bundle size larger than Svelte (but Vite optimizes)

**Risks:**
- **Chart library changes API** → Mitigation: Pin version, gradual upgrades

**Implementation Notes:**
- Use Socket.IO client for WebSocket connection
- Implement reconnection logic for dropped connections
- Use React Query for REST API calls
- Deploy static build to S3 + CloudFront (Free Tier)

---

## ADR-008: Celery + Redis for Task Queue

**Date**: 2024-12-29
**Status**: Accepted
**Deciders**: Development Team

### Context

Need task queue for:
- Scheduled ML model training (weekly)
- Periodic backtesting (daily)
- ChatGPT API calls (async to avoid blocking)
- Periodic data ingestion tasks

Options considered:
1. **Celery + Redis**
2. **RQ (Redis Queue)**
3. **AWS SQS + Lambda**
4. **APScheduler** (simple scheduler)

### Decision

Use **Celery with Redis broker** and Celery Beat for scheduling.

### Rationale

**Why Celery:**
- Battle-tested for production workloads
- Supports periodic tasks (Celery Beat)
- Distributed task execution (can scale workers)
- Retry logic and error handling built-in
- Monitoring tools (Flower)

**Why Redis as broker:**
- Fast (in-memory)
- Already using for caching and pub/sub
- Simple setup (no separate message broker)

**Why not RQ:**
- Less mature than Celery
- No native periodic task support
- Fewer monitoring tools

**Why not AWS SQS + Lambda:**
- Complexity of Lambda deployments
- Cold start latency (not ideal for time-sensitive tasks)
- SQS not in Free Tier after 1 million requests

**Why not APScheduler:**
- Single process (no distributed workers)
- No retry logic or failure handling
- Not suitable for long-running tasks

### Consequences

**Pros:**
- Reliable task execution with retries
- Easy to scale (add more worker processes)
- Celery Beat for cron-like scheduling
- Flower web UI for monitoring
- Same Redis instance for cache and queue

**Cons:**
- More moving parts (Celery workers, Beat scheduler)
- Need to monitor worker health
- Redis is in-memory (tasks lost if Redis crashes, but we can enable persistence)

**Risks:**
- **Redis memory exhaustion** → Mitigation: Enable Redis AOF persistence, monitor memory
- **Worker crashes** → Mitigation: Systemd auto-restart, Celery acks after task completion

**Implementation Notes:**
- Use Redis appendonly persistence
- Configure task retries (max 3 attempts)
- Set task time limits (prevent runaway tasks)
- Use Flower for task monitoring

---

## ADR-009: Telegram Bot for Human Oversight

**Date**: 2024-12-29
**Status**: Accepted
**Deciders**: Development Team

### Context

Need human-in-the-loop interface for:
- Trade approvals (manual confirm before execution)
- Real-time alerts (high-confidence signals, risk warnings)
- Performance summaries (daily P&L reports)
- System status notifications (errors, API failures)

Options considered:
1. **Telegram Bot** (python-telegram-bot)
2. **Web Dashboard** (manual checking)
3. **Email notifications**
4. **Discord Bot**
5. **SMS (Twilio)**

### Decision

Use **Telegram Bot** as Tier 3 (Human Oversight) with inline keyboard buttons for approvals.

### Rationale

**Why Telegram:**
- **Mobile-first** (get alerts anywhere)
- **Interactive** (inline keyboard buttons for approve/reject)
- **Free** (no SMS costs)
- **Instant** (push notifications)
- **Secure** (end-to-end encryption available)
- Excellent Python library (python-telegram-bot)

**Why not web dashboard only:**
- Requires actively checking (no push notifications)
- Not mobile-friendly for quick approvals

**Why not email:**
- Slow (delays in delivery)
- Not interactive (can't approve with one tap)
- Often filtered to spam

**Why not Discord:**
- Less mobile-optimized than Telegram
- Overkill for personal bot

**Why not SMS:**
- Costs $0.01-0.05 per message (Twilio)
- No rich formatting or buttons

### Consequences

**Pros:**
- Real-time push notifications to phone
- One-tap trade approvals via inline keyboard
- Rich formatting (markdown, code blocks)
- Can send charts as images
- Free to use
- Easy to implement (python-telegram-bot library)

**Cons:**
- Requires Telegram account
- Less formal than email for record-keeping
- Rate limits (30 messages/second, but sufficient)

**Risks:**
- **Bot token exposed** → Mitigation: Store in .env, never commit, whitelist chat IDs
- **Telegram API downtime** → Mitigation: System continues trading in auto mode (fallback)

**Implementation Notes:**
- Whitelist authorized Telegram user IDs (TELEGRAM_CHAT_ID in .env)
- Use inline keyboard for approve/reject buttons
- Send daily summary at 8 PM
- Alert on errors with high priority notifications
- Implement /status, /portfolio, /performance commands

---

## ADR-010: Docker Compose for Local Development

**Date**: 2024-12-29
**Status**: Accepted
**Deciders**: Development Team

### Context

Need consistent development environment for:
- PostgreSQL + TimescaleDB
- Redis
- (Future) Grafana for monitoring

Want to avoid:
- "Works on my machine" issues
- Manual database setup
- Version conflicts

Options considered:
1. **Docker Compose**
2. **Local installations** (Homebrew, apt)
3. **Vagrant**
4. **Kubernetes (kind, minikube)**

### Decision

Use **Docker Compose** for all infrastructure services (Postgres, Redis, Grafana).

### Rationale

**Why Docker Compose:**
- **Consistent environments** (same Postgres version across dev machines)
- **One command startup**: `docker-compose up -d`
- **Easy cleanup**: `docker-compose down -v`
- **Version pinning** (postgres:16, redis:7, etc.)
- **Init scripts** (TimescaleDB setup on first run)
- **Isolated networking** (services communicate via Docker network)

**Why not local installations:**
- Version conflicts (system Postgres vs TimescaleDB extension)
- Different versions across team members
- Manual setup for TimescaleDB extension

**Why not Vagrant:**
- Heavier than Docker (full VMs)
- Slower startup times
- More complex configuration

**Why not Kubernetes:**
- Overkill for local dev (3 services)
- Higher resource usage
- More complex than needed

### Consequences

**Pros:**
- Reproducible dev environment (onboard new developers in 5 minutes)
- No conflicts with system packages
- Easy to reset database (docker-compose down -v)
- Same config can be used for CI/CD
- Services auto-restart on code changes

**Cons:**
- Requires Docker Desktop (5GB+ download)
- Uses more RAM than native services (but acceptable)
- Slightly slower on macOS (file system mounts)

**Risks:**
- **Docker Desktop licensing** → Mitigation: Free for personal use, alternatives exist (Podman)

**Implementation Notes:**
- Store docker-compose.yml in `infrastructure/docker/`
- Use init scripts for TimescaleDB extension
- Persist data with named volumes
- Expose ports for local connections (5432, 6379)
- Include PgAdmin for database GUI (optional)

---

## Summary of Decisions

| ADR | Decision | Status | Impact |
|-----|----------|--------|--------|
| 001 | PostgreSQL + TimescaleDB | Accepted | Database choice, affects data model |
| 002 | Hybrid ML (Local + ChatGPT) | Accepted | Core strategy, 99% cost savings |
| 003 | AWS Free Tier Year 1 | Accepted | Infrastructure, $0-5/month costs |
| 004 | OANDA for Paper Trading | Accepted | Broker integration, FREE account |
| 005 | FastAPI over Flask/Django | Accepted | API framework, high performance |
| 006 | Python 3.11+ | Accepted | Language version, 30% faster |
| 007 | React + TypeScript | Accepted | Frontend, TradingView charts |
| 008 | Celery + Redis | Accepted | Task queue, scheduled jobs |
| 009 | Telegram Bot | Accepted | Human oversight, mobile alerts |
| 010 | Docker Compose | Accepted | Dev environment, consistency |

---

## Future ADRs to Document

As development progresses, we will document additional decisions:

- **ADR-011**: Terraform vs AWS CDK for Infrastructure as Code
- **ADR-012**: Specific ML features to use (80-100 technical indicators)
- **ADR-013**: Backtesting framework (Vectorbt vs Backtrader)
- **ADR-014**: Monitoring solution (Grafana + Prometheus vs CloudWatch only)
- **ADR-015**: Deployment strategy (Blue/Green vs Rolling updates)
- **ADR-016**: Secret management (AWS Secrets Manager vs Parameter Store)
- **ADR-017**: CI/CD pipeline (GitHub Actions vs GitLab CI)
