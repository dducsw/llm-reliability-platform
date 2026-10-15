# Cấu trúc Repository

## 1. Nguyên tắc tổ chức

1. **Chia theo đơn vị triển khai** (`apps/`) và **thư viện dùng chung** (`packages/`). Mỗi app chỉ phụ thuộc vào packages, không phụ thuộc lẫn nhau. Một lint rule (`import-linter`) kiểm tra điều này.
2. **Logic thuần nằm ở `reflex-core`** (router, breaker, retry, SLI math, histogram, validator, policy schema): không I/O, inject clock và rng. Gateway và Time Machine **dùng chung** code này, nên replay đúng với hành vi thật.
3. **Pipeline là code có ID** (`reflex-mongo/pipelines/a04_burn_rate.py`). Pipeline được test, explain-test, và Console tra ngược được.
4. **Hạ tầng là code** (`infra/`): Mongo migrations, search index JSON, Terraform cho Datadog, compose.
5. **Scenario là dữ liệu** (`scenarios/*.yaml`): vừa để demo, vừa làm e2e test, vừa làm bộ eval cho Cortex.
6. **Docs đánh số theo lớp** (`docs/00-…70-`): người đọc đi từ "tại sao" xuống "làm thế nào".

## 2. Cây thư mục

```
llm-reliability-platform/
├── README.md                         # Quickstart cho giám khảo (mục #7 hồ sơ)
├── Taskfile.yml                      # task up | seed | test | scenario | infra:* | demo:*
├── pyproject.toml                    # uv workspace root (ruff, mypy, pytest, import-linter config)
├── uv.lock
├── .env.example                      # mọi biến, không có giá trị
├── .pre-commit-config.yaml           # ruff, mypy, gitleaks, prettier
├── .github/workflows/
│   ├── ci.yml                        # lint → unit → integration (atlas-local) → e2e --fast
│   └── cortex-eval.yml               # chạy thủ công: eval agent trên scenario
│
├── apps/
│   ├── gateway/                      # DATA PLANE
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   └── reflex_gateway/
│   │       ├── main.py               # FastAPI app factory, ddtrace init
│   │       ├── api/                  # /v1/chat/completions, /healthz
│   │       ├── engine/               # orchestrator: attempt loop, hedging, deadline
│   │       ├── adapters/             # openai_compat.py, anthropic.py, mock.py (dịch request/response)
│   │       ├── policy_store.py       # load + Change Stream hot-reload + file snapshot
│   │       ├── health_sync.py        # pull health_state → router inputs
│   │       └── telemetry/            # queue → Mongo batch writer, DogStatsD, LLMObs, structlog
│   │
│   ├── control-plane/                # CONTROL PLANE (modular monolith)
│   │   └── reflex_cp/
│   │       ├── main.py               # khởi động module + leader lease
│   │       ├── sentinel/             # rollup tick, burn rate, health_state, detector
│   │       ├── incidents/            # open/dedup, lifecycle, timeline, signature (A9)
│   │       ├── policy_engine/        # guardrails, decision
│   │       ├── actuator/             # action → policy version, outbox
│   │       ├── verifier/             # recovery proof, failback orchestration
│   │       ├── hooks/                # Datadog webhook ingest
│   │       ├── timemachine/          # world.py, des.py, variants.py
│   │       ├── outbox/               # Datadog events/metrics publisher
│   │       └── api/                  # BFF REST + SSE (Change Streams fan-out)
│   │
│   ├── cortex/                       # AI SRE AGENT
│   │   └── reflex_cortex/
│   │       ├── main.py               # Change Stream consumer
│   │       ├── context_pack.py
│   │       ├── tools/                # mongo_tools.py, datadog_tools.py, memory_tools.py, propose.py
│   │       ├── prompts/              # system.md, investigate.md, postmortem.md (versioned)
│   │       ├── agent.py              # reasoning loop (via gateway), structured output
│   │       ├── evidence.py           # evidence validator
│   │       ├── rules.py              # rule-based fallback classifier
│   │       └── eval/                 # offline eval harness
│   │
│   ├── sim/                          # WORKLOAD & CHAOS
│   │   └── reflex_sim/
│   │       ├── traffic/              # ShopMate generator, prompt templates (vi), diurnal model
│   │       ├── mock_llm/             # deterministic LLM server (SSE)
│   │       ├── chaos_proxy/          # reverse proxy + fault catalog
│   │       ├── prober/               # golden prompts, direct & via_gateway
│   │       ├── scenario/             # YAML loader, runner, expectations checker
│   │       └── bench/                # llm-bench-data importer
│   │
│   └── console/                      # REACT SPA
│       ├── package.json
│       └── src/
│           ├── routes/               # pulse, incidents, war-room, approvals, memory, timemachine, policies, lab, explain
│           ├── components/charts/    # ECharts wrappers + event overlay
│           ├── api/                  # generated OpenAPI types + TanStack Query hooks
│           └── stream/               # SSE client, topic store
│
├── packages/
│   ├── reflex-core/                  # PURE DOMAIN — không I/O
│   │   └── reflex_core/
│   │       ├── ids.py                # target/route/slo id helpers, tag normalization
│   │       ├── events.py             # RequestEvent, AttemptEvent, ProbeEvent (Pydantic, v)
│   │       ├── policy.py             # Policy schema + defaults + diff
│   │       ├── actions.py            # ActionSpec catalog + params schema
│   │       ├── routing.py            # eligibility + scoring + softmax (clock/rng injected)
│   │       ├── breaker.py            # sliding-window breaker state machine
│   │       ├── retry.py              # retry budget, backoff, classification
│   │       ├── hedge.py
│   │       ├── validators/           # not_empty, json_schema, truncation, refusal, lang, length
│   │       ├── sli.py                # good/valid, burn, budget math
│   │       ├── hist.py               # mergeable histogram, quantile
│   │       └── stats.py              # wilson, two-proportion
│   ├── reflex-mongo/
│   │   └── reflex_mongo/
│   │       ├── client.py             # AsyncMongoClient factory, retryable writes
│   │       ├── collections.py        # tên collection, codec
│   │       ├── repos/                # incidents.py, actions.py, policies.py … (một file mỗi aggregate)
│   │       ├── pipelines/            # a01_attempt_rollup.py … a18_cost_daily.py + registry.py
│   │       ├── streams.py            # Change Stream consumer với checkpoint/resume
│   │       ├── leases.py
│   │       └── migrate/              # cli: create collections, indexes, validators, search indexes
│   └── reflex-telemetry/
│       └── reflex_telemetry/
│           ├── setup.py              # ddtrace, LLMObs, structlog, DogStatsD (một hàm init cho mọi app)
│           ├── tags.py               # danh mục tag chuẩn
│           └── datadog_api.py        # client đọc logs/spans/metrics + gửi events
│
├── infra/
│   ├── compose/
│   │   ├── docker-compose.yml        # toàn bộ stack
│   │   ├── docker-compose.demo.yml   # override: Atlas, nginx TLS, vendor thật
│   │   └── nginx/
│   ├── mongo/
│   │   ├── validators/               # *.json sinh từ Pydantic
│   │   └── search/                   # incident_signature.json, postmortems_text.json
│   └── datadog/                      # Terraform
│       ├── main.tf  providers.tf  variables.tf
│       ├── slos.tf  monitors.tf  composites.tf
│       ├── dashboards/               # ops.json, slo.json, cortex.json (templatefile)
│       ├── logs.tf                   # pipeline, facets, log-based metrics
│       └── webhooks.tf
│
├── scenarios/                        # silent-brownout.yaml, 429-storm.yaml, tail-latency.yaml,
│                                     # its-us.yaml, cascading-failover.yaml, real-world-replay.yaml
├── seeds/                            # targets.yaml, slos.yaml, policies.yaml, golden_prompts.yaml
├── tests/
│   ├── unit/                         # (thường nằm cạnh package: packages/*/tests)
│   ├── integration/                  # atlas-local: pipelines golden, explain, streams
│   ├── contract/                     # OpenAI compat, webhook payload, event schemas
│   └── e2e/                          # scenario --fast + expectations
├── tools/                            # scripts dev: gen-types, export-schemas, record-demo
└── docs/                             # (cấu trúc ở docs/README.md)
```

## 3. Ranh giới phụ thuộc (kiểm tra bằng import-linter)

```
apps/*            → packages/*            ✅
apps/X            → apps/Y                ❌
reflex-core       → (stdlib, pydantic, fastjsonschema)   chỉ thế thôi
reflex-mongo      → reflex-core, pymongo
reflex-telemetry  → reflex-core, ddtrace, datadog
```

## 4. Quy ước

- Python: `ruff` (lint + format), `mypy --strict` cho `reflex-core`, `pytest` + `pytest-asyncio` + `hypothesis`.
- Commit: Conventional Commits (`feat(gateway): …`), lấy package làm scope.
- Version: một version chung cho mọi service (`VERSION` file). Image được tag theo version, và DD `version` tag lấy từ đó.
- Mỗi app có `Dockerfile` multi-stage dùng `uv sync --frozen --no-dev`.
