<div align="center">

# Quant Agent EU — Open-Source OKX Europe X-Perp AI Trading Bot

### Risk-first AI trading agent with deterministic execution controls

[![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
![OKX Europe X-Perps](https://img.shields.io/badge/OKX%20Europe-X--Perps-111111.svg?style=flat-square)
[![Execution](https://img.shields.io/badge/Live%20execution-disabled%20by%20default-orange.svg?style=flat-square)](#live-execution)

**AI agents may propose orders; deterministic Python risk gates retain final authority.**

[Quick start](#quick-start) · [EEA support](#eea-x-perp-support) · [Security](#security) · [Risk](#risk-defaults) · [Compensation](#referral-and-broker-compensation) · [Limitations](#known-limitations)

</div>

> [!IMPORTANT]
> This is an independent derivative of the MIT-licensed AstraQuant project. It is not endorsed by OKX, does not guarantee profitability, and is not financial advice. Leveraged derivatives can lose the full allocated margin.

> [!TIP]
> **New to OKX Europe? [Create an account through the Quant Agent EU referral link](https://my.okx.com/nl/join/4QJU7QRA) to check the currently available welcome offer, which may advertise rewards worth up to US$400.** Eligibility, required tasks, deadlines, reward type, and value are determined by OKX and may vary by country or campaign. The project operator may receive referral compensation. Using the link is optional and does not affect the software.

## EEA X-Perp support

This fork targets eligible, verified OKX Europe accounts. It uses the EEA private API at `https://eea.okx.com` and discovers contracts as `instType=FUTURES` with `ruleType=xperp`. It supports full expiry-suffixed IDs, USD-equivalent collateral, isolated margin, one-way/net and hedge position modes, attached exchange-side TP/SL, product-isolated reconciliation, expiry guards, and emergency flattening.

Eligibility remains controlled by OKX and can require KYC, an appropriateness assessment, risk-disclosure acceptance, account-level approval, and supported collateral. The software never bypasses those controls.

## Quick start

```bash
git clone https://github.com/TheMMMdev/okx-europe-xperp-ai-trading-agent.git
cd quant-agent-eu
cp env.example .env
# Prefer entering credentials in the encrypted admin interface after first start.
docker compose up -d --build
```

Open `http://127.0.0.1:8080`. The Docker port is bound to localhost by default.

| Surface | URL | Access |
|---|---|---|
| Trading workstation | `http://127.0.0.1:8080/trading` | Local browser |
| Admin control plane | `http://127.0.0.1:8080/admin/login` | Authenticated |
| OpenAPI | `http://127.0.0.1:8080/docs` | Local browser |

Live X-Perp execution is physically disabled by default:

```env
ASTRA_OKX_ENV=demo
ASTRA_OKX_PRODUCT=xperp
ASTRA_XPERP_SETTLEMENT_CCY=USD
ASTRA_XPERP_MARGIN_MODE=isolated
ASTRA_XPERP_EXECUTION=0
```

Use demo credentials first. Switch only `ASTRA_OKX_ENV` to `live` after the EEA API key has read-and-trade permission, eligible collateral is in the trading account, and read-only diagnostics pass. Do not set `ASTRA_XPERP_EXECUTION=1` until instrument discovery, collateral checks, and a minimum-size lifecycle validation all pass.

## Security

- Create API keys with Read and Trade only. Never enable withdrawals.
- Use IP restrictions where practical.
- `.env`, encrypted stores, Fernet keys, databases, logs, ledgers, backups, fills, and order IDs are excluded from Git.
- Prefer the encrypted admin credential store over plaintext `.env` secrets.
- Plugins execute in-process and are not sandboxed. Install only reviewed plugins.
- The dashboard binds to `127.0.0.1` in Docker; use an authenticated reverse proxy for remote access.
- Run `python scripts/release_preflight.py` before every public release.

## Live execution

The default is read-only with `ASTRA_XPERP_EXECUTION=0`. Enabling execution is an operator action, not an installation step. A safe rollout is: read-only API check → instrument discovery → shadow decisions → minimum isolated lifecycle → monitored single-position pilot. The project contains `scripts/xperp_lifecycle_check.py`, which can place real orders and therefore requires an exact confirmation phrase.

## Risk defaults

The public template uses one position, 1× isolated leverage, 1% target risk, 2% daily-loss circuit breaker, minimum 2R structure, no pyramiding, no partial scale-out, high confidence gating, and limit entries. These are safety defaults, not performance claims. Contract minimums can cause orders to be skipped when percentage sizing cannot be represented safely.

## Referral and broker compensation

This distribution includes the operator's disclosed OKX Europe referral URL but no broker tag:

```env
OKX_INVITE_URL=https://my.okx.com/nl/join/4QJU7QRA
OKX_BROKER_TAG=
```

`OKX_INVITE_URL` is an optional public registration link. The operator may receive referral compensation when an eligible user registers or completes qualifying activity through it. Any advertised reward—including an offer worth up to US$400—is conditional on the live offer shown by OKX, the user's country, KYC, required tasks, deadlines, and OKX's terms; it is not guaranteed by this project. `OKX_BROKER_TAG` remains blank and should be configured only after OKX assigns or authorizes a 1–16 character ASCII alphanumeric code. A referral link does not authorize order-flow attribution, and this software does not claim that user fees are reduced or transferred in full.

To obtain a standard EEA referral link, sign in to OKX Europe and open **More → Referral** (or the approved affiliate flow under **More → Affiliates**), then copy your unique link into `OKX_INVITE_URL`. Order-flow attribution is separate: apply to OKX's Broker Program, wait for approval, retrieve the assigned broker code from the Broker Dashboard, and only then set `OKX_BROKER_TAG`. Do not invent a broker code; unauthorized or malformed values are rejected at startup/order assembly and may cause orders to fail.

## Known limitations

- No audited or statistically significant profitability record is included.
- Live validation covered minimum-size ETH X-Perp long and short lifecycles, protection readback, close, cleanup, and ledger ingestion; it did not prove strategy alpha.
- Partial fills, real TP/SL triggers, long-duration funding, daily settlement, process restart while holding, and final expiry settlement need broader live observation.
- Private REST retry/backoff and clock-drift handling remain less mature than institutional execution stacks.
- The default strategy is crypto-oriented; TradFi X-Perps are excluded from the generated pool.
- Paid multi-agent LLM usage can cost more than a small account earns.
- One-way/net mode and isolated margin are supported, but operators remain responsible for account settings and collateral.

## Upstream attribution

Derived from [0xethanq/astra-quant-agent](https://github.com/0xethanq/astra-quant-agent) under the MIT License. Preserve the repository `LICENSE` and upstream copyright notice when redistributing.

---

## 🏛 Architecture

One 15-minute cycle, four hard boundaries. Everything below the line is ordinary Python you can read, test, and patch:

```text
                    ┌───────────────────────────────────────────────┐
                    │        Scheduler · 15-minute brain cycle       │
                    │  trader · news(10m) · factors(60s) · evolve(6h)│
                    └───────────────────────┬───────────────────────┘
                                            ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 1 · MARKET REGIME & CALCULUS                                           │
   │   velocity v · acceleration a · impulse I · energy ∫E · deviation ∫A   │
   │   probability (skew / kurtosis / VaR / CVaR) · ADX · depth · OI · news │
   │   → regime label (bull trend / wide chop / low-velocity range / …)      │
   └───────────────────────────────┬────────────────────────────────────────┘
                                   ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 2 · MULTI-MODEL COMMITTEE            (user-defined seats, any provider)│
   │   Trend seat · Momentum seat · Quant-math seat · Macro/news seat        │
   │   cross-examination rounds  →  CIO seat arbitrates one order intent     │
   └───────────────────────────────┬────────────────────────────────────────┘
                                   ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 3 · FAIL-CLOSED PHYSICAL RISK PIPELINE        (non-bypassable Python)  │
   │   data validity · price geometry · R:R floor · 4H direction veto        │
   │   leverage & margin caps · exposure quota · interceptor plugins         │
   │   ⚠️ any exception or timeout  =  HARD REJECT (never "open anyway")     │
   └───────────────────────────────┬────────────────────────────────────────┘
                                   ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 4 · OKX-NATIVE EXECUTION                                               │
   │   maker / BBO limit · attached TP1 · TP2 · cloud stop-loss legs         │
   │   scale-out (35% at 2.0×ATR) · profit ratchet · time stop (8h)          │
   └────────────────────────────────────────────────────────────────────────┘
```

Every arrow is observable: the full Chain-of-Thought, each seat's transcript, the calculus snapshot, the interceptor verdicts, and the final `policy_hash` are persisted per decision.

---

## 🎯 Design principles

1. **Cognition belongs to the model; physical risk control belongs to the base layer.**
   LLMs and committees hold only the **right to propose**. Before an order reaches an exchange socket it must pass 100% of the Python risk gates. Any interceptor that raises or times out causes a **fail-closed block**. Model hallucinations cannot become losses.

2. **Market-regime auto-detection, not curve fitting.**
   Trend-following bleeds in chop; mean-reversion grids blow up in breakouts. Regime is derived continuously from calculus and volatility structure, and the active prompt strategy and leverage band adapt with it.

3. **OKX-native by design.**
   One venue, one credential set, one signing path, one order contract. The old venue-abstraction layer is gone: no divergent exchange code paths, no parity claims, no inter-venue matrix. Every entry carries native attached conditional protection from the same single path.

4. **White-box explainability and closed-loop evolution.**
   Every decision records its reasoning chain, debate transcripts, calculus features, and execution evidence. Four times a day the self-evolution engine mines the **real closed-trade ledger** and distils lessons into long-term heuristic memory — under strict anti-fabrication rules (see [Prompt system](#-prompt-system)).

---

## ⏱ Scheduling

All cadences are declared in one place (`astra_gateway/scheduler.py`), so this table is the contract:

| Job | Cadence | Timeout | What it does |
|---|---|---|---|
| `trader` | **every 15 min** | 1260 s | Full brain cycle: market data → committee → risk gates → OKX execution |
| `news` | every 10 min | 300 s | Harvests and weights macro/crypto headlines for the news seat |
| `factor_library` | every 60 s | 55 s | Refreshes the technical-factor library |
| `self_improvement` | **02:00 / 08:00 / 14:00 / 20:00** | 1200 s | Closed-trade attribution → long-term memory update |
| `daily_briefing` | 08:00 / 20:00 | 600 s | Daily summary and backup |

---

## 🎨 Prompt system

> **This is the part most people get wrong about AstraQuant, so it is stated plainly.**

**All prompt text lives in one file** — `data/prompt_library.json` (the shipped baseline, git-tracked; your edits go to `data/prompt_library.local.json`). There is **no prompt prose in Python**.

| Piece | Owned by | Editable? |
|---|---|---|
| **Output JSON schema** — the machine contract for the model's reply | **Code** (`scripts/ai_brain_trader.py`) | ❌ **Read-only**: the studio disables it, the API rejects changes, and the renderer re-inserts it if deleted |
| Role, doctrine, entry rules, rhythm rules, task lists, review rules | `data/prompt_library.json` | ✅ Fully editable in the visual Prompt Studio |
| Live data (price matrix, positions, budget, memory, news) | Code, regenerated each cycle | injected through `{{slot}}` variables |

**Why the schema is read-only.** It is not documentation — it is the contract the parser depends on. Renaming one field can make an entire decision cycle fail to parse. It therefore ships with the code and moves only by release, never by a studio edit.

**Why prose left Python.** The same text used to exist in three copies (Python constants, the JSON baseline, and your local edits). Changing one left the others stale, which surfaced as *"I edited it in the studio but the live prompt never changed."* One source of truth removes that whole failure class.

**Live variable slots** — 8 semantic slots carry the runtime state: `{{decision_timestamp}}` `{{account_balance}}` `{{risk_budget}}` `{{account_positions}}` `{{pending_orders}}` `{{market_matrix}}` `{{news_intelligence}}` `{{trading_memory}}` (24 variables in total across all pipelines, including the evolution pipeline's ledger slots).

📖 Full authoring guide, slot dictionary, and the shipped doctrine: **[`docs/PROMPT_GUIDE.md`](docs/PROMPT_GUIDE.md)**

---

## 🧩 Strategy configuration centers

> *The right to define strategy belongs to the trader, never to hardcoded logic.*

| # | Module | What it governs |
|---|---|---|
| 1 | 🎨 **Prompt Studio** | Edit the four prompt pipelines as ordered modules; inject live slots; duplicate / import / export profiles; anti-poisoning guardrails; the output schema stays locked |
| 2 | 👥 **Multi-Model Committee** | User-defined seats bound to any OpenAI- or Anthropic-compatible provider; voting weights, cross-examination rounds, CIO arbitration |
| 3 | 🛡️ **Fail-Closed Interceptors** | Non-bypassable Python plugin gates (4H macro direction, entry confidence, ADX chop filter, R:R floor). Any plugin fault halts entry |
| 4 | 🧬 **Self-Evolution Engine** | 6-hourly closed-trade attribution; distils operational lessons into prompt memory with outlier rejection and anti-fabrication rules |
| 5 | 📦 **Policy Snapshots** | Hashes prompts + interceptors + committee seats + instrument parameters into fingerprints; sub-second atomic rollback; audit `policy_hash` per trade |
| 6 | 🎛️ **Risk Control Center** | All **27** physical execution knobs configurable from the UI, with conservative / balanced / aggressive presets and typed confirmation on destructive actions |
| 7 | 🤖 **LLM Gateway** | Multi-provider connections; thinking budget up to 1800 s for reasoning models; failover on rate limits (HTTP 429) or outages |
| 8 | 🌐 **OKX Connectivity** | Native OKX V5 with separate demo / live credential profiles; funding, open interest, and momentum analytics |
| 9 | 🧪 **Backtest & Sandbox** | Multi-instrument portfolio backtests and sandbox replays that execute the **same** Python risk and sizing code paths as live trading |

---

## 💰 Risk model

The public EEA template is intentionally conservative. Percentage sizing still rounds down to exchange contract lots, so small accounts may skip trades rather than exceed their risk budget.

| Rule | Public default |
| :--- | ---: |
| Concurrent positions | 1 |
| Same-direction positions | 1 |
| Risk target per trade | 1% of available eligible collateral |
| Max margin per trade | 18% of available eligible collateral |
| Single-asset cumulative margin | 18% |
| Daily drawdown circuit breaker | 2% of equity, subject to absolute cap |
| Leverage | 1× isolated |
| Reward:risk floor / cap | 2.0 / 3.0 |
| Minimum entry confidence | 85% |
| Pyramiding | Disabled |
| Partial scale-out | Disabled by default |
| Post-stop cooldown | 120 minutes |
| Contract expiry guard | 30 days |
| Autonomous live execution | Disabled |

These are safety defaults, not a claim of optimality or profitability. Review the actual values in `env.example` and `scripts/risk_constants.py` before deployment.

---

## 📸 Visual tour

| | |
|---|---|
| **Live trading workstation**<br>![Live trading workstation](docs/images/v840_live_dashboard.png) | **Chain-of-Thought reasoning drawer**<br>![Chain-of-Thought](docs/images/v840_trajectory_cot.png) |
| **Causal calculus dynamics**<br>![Calculus factors](docs/images/v840_calculus_factors.png) | **Multi-model committee board**<br>![Committee](docs/images/v840_council_board.png) |
| **Visual Prompt Studio**<br>![Prompt Studio](docs/images/v840_prompt_studio.png) | **Self-evolution engine**<br>![Self-evolution](docs/images/v840_self_evolution.png) |
| **Fail-closed interceptors**<br>![Interceptors](docs/images/v840_interceptors_failclosed.png) | **Policy snapshots & rollback**<br>![Policy snapshot](docs/images/v840_policy_snapshot.png) |
| **Execution risk control**<br>![Risk control](docs/images/v840_risk_control.png) | **LLM gateway & reasoning config**<br>![LLM hub](docs/images/v840_llm_hub.png) |
| **Admin control plane**<br>![Admin overview](docs/images/v840_admin_overview.png) | **Security & Strategy Plaza**<br>![Security](docs/images/v840_security_plaza.png) |

---

## 📊 Observability

| Logger | Path | Emitted by | Scope |
| :--- | :--- | :--- | :--- |
| `trader` | `logs/ai_factor_trader.log` | Brain cycle daemon | Quotes, debate, confidence grading, orders, brackets, trailing ratchets |
| `backend` | `logs/uvicorn.log` | FastAPI / Uvicorn | Request lifecycle, auth, CORS, exceptions, telemetry |
| `scheduler` | `logs/astra_gateway.log` | Scheduler daemon | Lock leases, cron dispatch, heartbeats, log pruning |
| `audit` | `logs/astra_admin_audit.jsonl` | Security subsystem | Append-only JSONL: time, IP, actor, action |

Both Docker containers run an in-container watchdog and expose health checks, because `restart:` only covers *exits* — a hung-but-alive process would otherwise go unnoticed.

> 📈 **Prometheus & Grafana**: pre-built dashboards in [`deploy/observability/README.md`](deploy/observability/README.md) visualise `/api/v1/admin/metrics`.

---

## 🧪 Tests

Documentation claims in this repository are backed by automated gates; passing them is part of the deliverable.

```bash
python scripts/release_preflight.py
python -m unittest discover -s tests

cd frontend
npm ci
npx vue-tsc --noEmit -p tsconfig.app.json
npm run build
npm test
```

CI runs backend tests on Python 3.11 and 3.12, frontend checks on Node 22.15, the release preflight, and a Docker image build.

---

## 🚀 Deploy

### Option A 🐳 Docker (recommended — zero host dependencies)

Packages Python 3.11, compiles the Vue 3 bundle, and runs the web app plus the scheduler:

```bash
git clone https://github.com/TheMMMdev/okx-europe-xperp-ai-trading-agent.git
cd quant-agent-eu
cp env.example .env && vim .env      # configure LLM + OKX credentials
./deploy/docker-start.sh             # == docker compose up -d --build

docker compose ps                    # status
docker compose logs -f               # aggregated logs
```

> 💡 The launcher pre-flight-checks for the classic Docker trap where a missing host `./.env` gets silently created as a **directory**, which would make every config save fail. If it happens, the entrypoint refuses to start and prints the exact fix.

### Option B Bare metal

```bash
git clone https://github.com/TheMMMdev/okx-europe-xperp-ai-trading-agent.git
cd quant-agent-eu
sh deploy/install.sh                 # creates .venv and installs dependencies
vim .env

cd frontend && npm install && npm run build && cd ..
./start.sh                           # starts Uvicorn on 0.0.0.0:8080
```

Windows: `start.ps1`. Systemd units: `deploy/astra-quant.service`, `deploy/astra-gateway.service`, `deploy/astra-scheduler.service`.

---

<a id="code-map"></a>
## 🗂 Code map

> ⚠️ This repository has **never contained an `OPENCODE.md`** — external prompts pointing at that path are erroneous. The authoritative entry points are:

| To learn about | Read |
|---|---|
| **Architecture & module layout** | [`docs/STRUCTURE_OVERVIEW.md`](docs/STRUCTURE_OVERVIEW.md) |
| **Backend layering (L0→L4)** | [`astra_backend/README.md`](astra_backend/README.md) |
| **Runtime scripts & daemons** | [`scripts/README.md`](scripts/README.md) |
| **Prompt engineering** | [`docs/PROMPT_GUIDE.md`](docs/PROMPT_GUIDE.md) |
| **Failure semantics (why each gate exists)** | [`docs/FAILURE_SEMANTICS.md`](docs/FAILURE_SEMANTICS.md) |
| **Beijing-time contract** | [`docs/BEIJING_TIME_CONTRACT.md`](docs/BEIJING_TIME_CONTRACT.md) |
| **Frontend components & state** | [`frontend/src/components/admin/README.md`](frontend/src/components/admin/README.md) |
| **Standalone deployment** | [`STANDALONE.md`](STANDALONE.md) |
| **Emergency recovery** | [`RECOVERY_GUIDE.md`](RECOVERY_GUIDE.md) |
| **Observability** | [`deploy/observability/README.md`](deploy/observability/README.md) |

**Gates watching this repository:**

| Gate | What it prevents |
|---|---|
| `tests/audit/test_directory_docs_current.py` | A module existing without being registered in its `__init__.py` **and** its `README.md` |
| `tests/core/test_readme_baseline_numbers.py` | Documented test counts rotting away from reality |
| `tests/audit/test_doc_paths_are_committed.py` | Documentation pointing at paths that do not exist or are not committed |
| `tests/audit/test_brand_strings_are_consistent.py` | Brand / namespace drift that would break live production data |
| `tests/audit/test_deployment_scripts_are_sound.py` | Startup or Docker scripts that cannot actually start the project |

---

## 🏷 Distribution name and internal namespace

- **Distribution**: **Quant Agent EU**
- **Upstream project**: **AstraQuant**
- **Internal namespace**: **`astra`** (packages `astra_backend`, `astra_gateway`; config prefix `ASTRA_*`)

`AstraQuant` remains in code, prompts, tests, and upstream-facing metadata for compatibility and attribution. Do not perform a global rename: several historical markers protect existing databases, backups, exchange order tags, and test baselines.

### Intentional legacy markers — do not rename

Three historical markers are retained to protect live production data and open positions (`tests/audit/test_brand_strings_are_consistent.py`):

1. **Exchange leg tags `t-r20sl*` / `t-r20tp*`** — conditional orders placed before the namespace upgrade are still live on the matching engine. `scripts/tag_markers.py` preserves them so cloud ratchets keep managing them; new orders use `astrasl` / `astratp`.
2. **Encrypted backup magic `R20GCM2` + NUL** — existing user archives must remain decryptable. New archives use `ASTRAGCM`.
3. **`cpa.r20.cn` in test fixtures** — the maintainer's upstream DNS gateway for LLM endpoints, not a repository namespace.

---

## 🤝 Upstream acknowledgement

Thanks to the upstream AstraQuant contributors and the LINUX DO community for the original implementation, technical discussion, and feedback. This repository is an independent fork; references to upstream are attribution, not an endorsement of this distribution or its strategy results.

---

## ⚠️ Disclaimer

1. This project is **open-source algorithmic trading software and a quantitative research framework**, for research, education, and simulation only.
2. Crypto derivatives trading carries substantial risk of loss and extreme volatility. Past performance and backtests do not guarantee future returns.
3. Users must understand risk management and should validate strategies in a **DEMO / paper** environment before deploying real funds.
4. The authors and contributors accept no liability for financial losses arising from use of this software.

---

## 📄 License

Distributed under the [MIT License](LICENSE).
