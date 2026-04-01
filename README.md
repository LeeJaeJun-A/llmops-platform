# LLMOps Platform

Production-ready LLMOps microservice that centralizes LLM operations for your organization. Any service calls one API — gets automatic observability, prompt management, quality scoring, and A/B testing.

```
┌──────────────┐     ┌─────────────────────────────────────┐     ┌─────────────┐
│ Service A    │────>│         LLMOps Platform              │────>│  Anthropic  │
│ Service B    │────>│                                      │────>│  Gemini     │
│ Service C    │────>│  Scoring · Prompts · Tuning · Traces │     └─────────────┘
└──────────────┘     └─────────────────────────────────────┘
                            │          │         │
                       Langfuse   PostgreSQL   Redis
```

## What This Project Does

LLMOps Platform is a **self-hosted API gateway** that sits between your applications and LLM providers. Instead of each service managing its own API keys, prompts, and LLM calls, everything goes through this single platform:

- **Unified LLM Gateway** — One API endpoint for Anthropic Claude and Google Gemini. Switch providers by changing a single field.
- **Prompt Management** — Version-controlled Jinja2 templates stored in PostgreSQL. Create, iterate, and promote prompts (draft → staging → production) without redeploying your apps.
- **Automated Scoring** — Evaluate LLM output quality with pluggable strategies: rule-based checks, embedding similarity, LLM-as-judge, and composite pipelines.
- **A/B Testing** — Run experiments comparing models, temperatures, or prompt variants with consistent-hash traffic splitting and automatic winner detection.
- **Observability** — Every LLM call is automatically traced in Langfuse with token counts, latencies, costs, and scores.
- **Prometheus Metrics** — Built-in `/metrics` endpoint for Kubernetes monitoring (request latency, LLM token usage, scoring job stats, worker health).

## Why Use This

| Problem | Without This | With This |
|---------|-------------|-----------|
| API key sprawl | Keys scattered across services, hard to rotate | One place to manage all LLM provider keys |
| No cost visibility | No idea which service burns how much | Per-service, per-model cost tracking in real-time |
| Prompt changes = redeploy | Templates hardcoded in app code | Change prompts via API, promote to production instantly |
| No quality measurement | Ship LLM outputs and hope for the best | Automated scoring pipelines grade every response |
| Can't compare approaches | Manual testing, gut feeling | Built-in A/B testing with statistical results |
| Provider lock-in | Anthropic code everywhere, switching is a rewrite | Change `"model": "claude-..."` to `"model": "gemini-..."` |
| No rate limiting | One runaway service exhausts your API quota | Redis-backed per-service rate limiter |
| Logging is an afterthought | Add tracing later (or never) | Every call auto-traced from day one |

### Key Advantages

- **Zero SDK lock-in** — Your services use one REST API. They never import `anthropic` or `google-genai`.
- **Async everything** — FastAPI + asyncpg + async Redis. Non-blocking from request to database.
- **Pluggable architecture** — Every major component (LLM providers, scoring strategies, observability backends) is an ABC interface. Swap or extend without touching existing code.
- **Production-ready infra** — Terraform modules for VPC, EKS, RDS, ElastiCache, Karpenter. Helm charts with dev/staging/prod values. GitHub Actions CI/CD.
- **Structured logging** — JSON logs in production via structlog, human-readable in development. Every log entry includes request context.
- **Worker reliability** — Scoring and tuning workers have exponential backoff retry (3 attempts) with dead-letter queues for failed jobs.

### Langfuse vs This Platform

Langfuse is the **observability backend** — it watches and records your LLM calls. This platform is the **control plane** — it decides what happens.

| Capability | Langfuse alone | This platform (with Langfuse) |
|-----------|:-:|:-:|
| Trace LLM calls | Yes | Yes |
| Cost dashboard | Yes (UI) | Yes (API + UI) |
| Prompt management UI | Yes | No (API only) |
| Centralize API keys | No | **Yes** |
| Unified multi-provider API | No | **Yes** |
| Automated scoring pipelines | Partial | **Yes (4 strategies, weighted)** |
| A/B testing | No | **Yes** |
| Rate limiting & auth | No | **Yes** |
| Prometheus metrics | No | **Yes** |

**Use Langfuse directly** if you have 1-2 services that just need observability. **Use this platform** when you have multiple services and need centralized control, automated quality scoring, or experimentation.

## Features

### LLM Gateway

Unified API for Anthropic Claude and Google Gemini. Your services never touch provider SDKs or API keys.

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer test-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

Switch to Gemini by changing one field:
```bash
  -d '{"model": "gemini-2.5-flash", ...}'
```

Streaming supported via SSE with `"stream": true`.

### Prompt Management

Version-controlled Jinja2 templates with environment promotion (draft → staging → production). No redeploys needed.

```bash
# Create a prompt
curl -X POST /v1/prompts \
  -d '{"name": "support-bot", "template": "You are a {{ role }}. Help with {{ topic }}."}'

# Render with variables
curl -X POST /v1/prompts/support-bot/compile \
  -d '{"variables": {"role": "support agent", "topic": "billing"}}'

# Promote to production
curl -X POST /v1/prompts/support-bot/promote \
  -d '{"version": 1, "target_env": "production"}'

# Use in completions (auto-resolves prompt)
curl -X POST /v1/chat/completions \
  -d '{
    "model": "gemini-2.5-flash",
    "prompt_name": "support-bot",
    "prompt_env": "production",
    "prompt_variables": {"role": "agent", "topic": "refunds"},
    "messages": [{"role": "user", "content": "I need help"}]
  }'
```

### Scoring Engine

Pluggable scoring pipelines with weighted strategies. Runs async via background workers — doesn't add latency to responses.

| Strategy | What it does |
|----------|-------------|
| `rule_based` | Regex, length, JSON validity, keyword checks |
| `llm_judge` | Another LLM rates quality with configurable rubric |
| `embedding` | Cosine similarity against reference text |
| `composite` | Nest pipelines for recursive scoring |

```bash
# Create pipeline
curl -X POST /v1/scoring/pipelines -d '{
  "name": "quality-check",
  "scorers": [
    {"strategy": "rule_based", "weight": 0.6, "config": {"rules": [{"type": "min_length", "min": 50}]}},
    {"strategy": "embedding", "weight": 0.4}
  ]
}'

# Evaluate
curl -X POST /v1/scoring/evaluate -d '{
  "trace_id": "...", "pipeline_id": "...",
  "input_text": "...", "output_text": "...", "reference_text": "..."
}'
# → {"aggregate_score": 0.94, "individual_scores": [...]}
```

### A/B Testing

Test models, temperatures, or prompt variants with consistent-hash traffic splitting.

```bash
# Create experiment
curl -X POST /v1/tuning/experiments -d '{
  "name": "temp-test",
  "parameter_space": {
    "parameters": [{"name": "temperature", "type": "categorical", "values": [0.3, 0.7, 1.0]}]
  }
}'

# Start → allocate → record trials → conclude (auto-picks winner)
```

### Observability & Monitoring

- **Langfuse** — Every call auto-traced with model, tokens, latency, input/output, and scores
- **Prometheus** — `/metrics` endpoint with HTTP latencies, LLM token counters, scoring job stats, worker retry/DLQ metrics
- **Structured logging** — JSON in production (machine-parseable), pretty console in development via structlog
- **Cost tracking** — Per-service, per-model usage and cost estimates via `/v1/usage/summary`

### Auth, Rate Limiting, Cost Tracking

- API key authentication per service (`Authorization: Bearer <key>`)
- Redis-backed sliding window rate limiter (configurable RPM)
- Per-model cost estimation with usage summary endpoint

## Quick Start

### Local (Docker Compose)

```bash
# 1. Setup
cp .env.example .env
cp .env.secrets.example .env.secrets
# Edit .env.secrets — add your ANTHROPIC_API_KEY and/or GEMINI_API_KEY

# 2. Deploy (one command)
make local-deploy

# 3. Use
# App:      http://localhost:8000
# API Docs: http://localhost:8000/docs
# Metrics:  http://localhost:8000/metrics
# Langfuse: http://localhost:3000 (wait ~2 min)

# 4. Stop
make local-down          # keep data
make local-teardown      # remove everything
```

### AWS Cloud (EKS)

```bash
# 1. Setup
cp .env.secrets.example .env.secrets
# Edit .env.secrets — add your API keys

# 2. Deploy (one command — takes ~20 min)
make cloud-deploy
# Deploys: VPC, EKS, RDS, ElastiCache, Karpenter, Langfuse, app

# 3. Access
kubectl port-forward svc/llmops-llmops-platform 8000:8000
kubectl port-forward svc/langfuse-web 3000:3000 -n langfuse

# 4. Teardown (~$12/day when running)
make cloud-teardown
```

### Re-run individual steps
```bash
./scripts/cloud/lib/07-docker-build.sh    # just rebuild + push
./scripts/cloud/lib/09-db-migrate.sh      # just run migrations
./scripts/cloud/lib/11-verify.sh          # just run smoke tests
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/chat/completions` | LLM completion (Anthropic/Gemini, streaming supported) |
| `POST` | `/v1/prompts` | Create a prompt |
| `GET` | `/v1/prompts` | List all prompts |
| `GET` | `/v1/prompts/{name}` | Get prompt by name |
| `GET` | `/v1/prompts/{name}/versions` | List prompt versions |
| `POST` | `/v1/prompts/{name}/versions` | Create new version |
| `POST` | `/v1/prompts/{name}/compile` | Render template with variables |
| `POST` | `/v1/prompts/{name}/promote` | Promote version to environment |
| `GET` | `/v1/scoring/strategies` | List available scoring strategies |
| `POST` | `/v1/scoring/pipelines` | Create scoring pipeline |
| `GET` | `/v1/scoring/pipelines` | List scoring pipelines |
| `GET` | `/v1/scoring/pipelines/{id}` | Get pipeline by ID |
| `POST` | `/v1/scoring/evaluate` | Run scoring on an LLM output |
| `GET` | `/v1/scoring/results/{trace_id}` | Get scores for a trace |
| `POST` | `/v1/tuning/experiments` | Create A/B experiment |
| `GET` | `/v1/tuning/experiments` | List experiments |
| `GET` | `/v1/tuning/experiments/{id}` | Get experiment by ID |
| `POST` | `/v1/tuning/experiments/{id}/start` | Start experiment |
| `POST` | `/v1/tuning/experiments/{id}/allocate` | Allocate variant for a request |
| `POST` | `/v1/tuning/experiments/{id}/trials` | Record trial result |
| `GET` | `/v1/tuning/experiments/{id}/results` | Get aggregated results |
| `POST` | `/v1/tuning/experiments/{id}/conclude` | End experiment (auto-picks winner) |
| `POST` | `/v1/tuning/experiments/{id}/cancel` | Cancel experiment |
| `GET` | `/v1/usage/summary` | Cost and token usage per service |
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/readyz` | Readiness probe (checks DB + Redis) |
| `GET` | `/metrics` | Prometheus metrics |

All endpoints except `/healthz`, `/readyz`, and `/metrics` require `Authorization: Bearer <key>`.

## Architecture

```
src/llmops/
├── api/
│   ├── v1/                  # FastAPI route handlers
│   │   ├── gateway.py       # POST /v1/chat/completions
│   │   ├── scoring.py       # /v1/scoring/*
│   │   ├── prompts.py       # /v1/prompts/*
│   │   ├── tuning.py        # /v1/tuning/*
│   │   └── admin.py         # /healthz, /readyz, /v1/usage
│   ├── schemas/             # Pydantic request/response models
│   └── middleware/          # Auth, rate limiting, request context
├── core/
│   ├── gateway/             # LLMProvider ABC → Anthropic, Gemini providers
│   │                        # Router (model → provider resolution + observability)
│   │                        # Cost tracker (Redis-backed per-service/model)
│   ├── scoring/             # Scorer ABC → 4 strategies (rule_based, llm_judge,
│   │                        #   embedding, composite) + pipeline orchestrator
│   ├── tuning/              # ExperimentRunner, ABTestAllocator, parameter space
│   ├── prompts/             # PromptStore ABC → PostgreSQL manager, Jinja2 renderer
│   └── observability/       # ObservabilityBackend ABC → Langfuse, Noop
├── db/
│   ├── models/              # SQLAlchemy async models (prompts, experiments, scores)
│   ├── repositories/        # Data access layer (prompt, experiment, score repos)
│   └── migrations/          # Alembic migration scripts
├── workers/                 # Background workers (scoring queue, tuning poller)
│                            # Retry with exponential backoff + dead-letter queue
├── logging.py               # Structured logging (structlog, JSON in prod)
└── metrics.py               # Prometheus metrics collection + /metrics endpoint
```

```
scripts/
├── local/               # Docker Compose deploy/teardown
├── cloud/               # AWS EKS deploy/teardown (11 composable steps)
│   └── lib/01-11*.sh   # Each step independently runnable
└── shared/              # Config, helpers, secret upload

helm/llmops-platform/    # Kubernetes Helm charts (dev/staging/prod values)
infra/                   # Terraform modules + Terragrunt (VPC, EKS, RDS, Redis, Karpenter)
.github/workflows/       # CI (lint, typecheck, test, helm lint), Build, Deploy
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| App | Python 3.12, FastAPI, SQLAlchemy async, Jinja2 |
| LLM Providers | Anthropic SDK, Google GenAI SDK |
| Database | PostgreSQL 17 (asyncpg driver) |
| Cache / Queue | Redis 7 (rate limiting, scoring job queue, cost tracking) |
| Observability | Langfuse v3 (pluggable via ABC interface) |
| Monitoring | Prometheus metrics, structlog (JSON logging) |
| Infrastructure | Terraform + Terragrunt (VPC, EKS, RDS, ElastiCache, S3) |
| Scaling | Karpenter (node auto-scaling), HPA (pod auto-scaling) |
| Deployment | Helm 3, Docker, GitHub Actions CI/CD |

## Configuration

### Environment Variables

```bash
cp .env.example .env                  # App config
cp .env.secrets.example .env.secrets  # API keys & auth
```

**Config** (`.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | `development` / `staging` / `production` | `development` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://llmops:llmops@localhost:5432/llmops` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `OBSERVABILITY_BACKEND` | `langfuse` or `noop` | `noop` |
| `LANGFUSE_HOST` | Langfuse server URL | `http://localhost:3000` |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | Per-service rate limit | `60` |

**Secrets** (`.env.secrets`):

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `LANGFUSE_PUBLIC_KEY` | From Langfuse UI → Settings → API Keys |
| `LANGFUSE_SECRET_KEY` | From Langfuse UI → Settings → API Keys |
| `API_KEYS` | Comma-separated keys for client auth (e.g. `svc-a-key,svc-b-key`) |

## Testing

```bash
# Unit tests (148 tests, 79% coverage, no DB required)
make test

# Integration tests (requires running services)
make test-integration

# Lint + type check
make lint

# Full E2E test against deployed environment
./scripts/cloud/lib/11-verify.sh
```

| Test Suite | Tests | Coverage |
|-----------|-------|----------|
| API endpoints (admin, gateway, prompts, scoring, tuning) | 28 | 66-100% |
| Gateway core (providers, router, schemas, registry, cost) | 18 | 97-100% |
| Scoring engine (rule_based, embedding, pipeline) | 16 | 92-100% |
| Tuning (A/B allocator, parameter space) | 11 | 90-100% |
| Prompt renderer | 9 | 89% |
| Middleware (auth, rate limit) | 14 | 91-100% |
| Observability (Langfuse, Noop backends) | 10 | 100% |
| Repositories (prompt, experiment, score) | 20 | 78-94% |
| Workers (scoring, tuning + retry/DLQ) | 8 | 67-77% |
| Metrics (path normalization) | 7 | 95% |
| Integration (health endpoints) | 2 | — |

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues and fixes.

## License

MIT
