# Buy or Wait? — Autonomous AI Financial Decision Agent

[![HackerRank Orchestrate 2026](https://img.shields.io/badge/HackerRank-Orchestrate%2024h-green.svg)](https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Submission Ready](https://img.shields.io/badge/Status-Submission%20Ready-brightgreen.svg)]()

> An enterprise-grade, hybrid deterministic-AI financial decision engine built for the **HackerRank Orchestrate 24-Hour Hackathon Challenge** (September 2026).
> Evaluates user purchase requests against multi-currency financial profiles, historical/pending events, recurring obligations, seller payment options, and unstructured message/invoice evidence over a conservative 90-day cash flow forecast.

---

##  Table of Contents

- [Executive Summary & Problem Overview](#-executive-summary--problem-overview)
- [Architecture & Engine Design](#-architecture--engine-design)
- [Key Features & Capabilities](#-key-features--capabilities)
- [System Requirements & Installation](#-system-requirements--installation)
- [Quick Start & Terminal Execution](#-quick-start--terminal-execution)
- [Interactive Cockpit Web Dashboard](#-interactive-cockpit-web-dashboard)
- [Dataset Specifications & Input Pipeline](#-dataset-specifications--input-pipeline)
- [Evaluation & Benchmark Suite](#-evaluation--benchmark-suite)
- [Submission Artifacts & Token Cost Analysis](#-submission-artifacts--token-cost-analysis)
- [Project Directory Structure](#-project-directory-structure)
- [License & Credits](#-license--credits)

---

##  Executive Summary & Problem Overview

When a user asks **"Can I afford to buy this laptop today?"**, answering accurately requires far more than checking their current bank balance. 

The **Buy or Wait?** agent reconstructs a complete multi-currency financial balance sheet and simulates daily liquidity for **90 days into the future**. It makes personalized decision recommendations (`affordable_now`, `affordable_with_plan`, `affordable_later`, `not_affordable`) while respecting strict safety constraints:

1. **Safety Floor Maintenance**: The user's balance must never dip below their specified `minimum_balance_to_keep` at any single day in the 90-day forecast.
2. **Essential Spend Protection**: Fixed essential expenses (rent, utilities, groceries) and pending debt obligations are protected ahead of optional discretionary spending.
3. **Pending Debit Reservation**: Unsettled pending debits reserve liquid cash immediately on request date. Unsettled credits/bonuses are ignored until settlement.
4. **Multimodal & Unstructured Fact Extraction**: Messages, invoices, and receipts modify financial events (e.g. salary dates, cancellations, amendments) without letting prompt-injection alter safety rules.

---

## Architecture & Engine Design

The solution relies on a **Hybrid Deterministic-AI Architecture**:

```text
 ┌─────────────────────────┐     ┌───────────────────────────┐     ┌───────────────────────────┐
 │   Multi-Dataset Loader  │     │   Multimodal OCR / NLP    │     │   Fixed Foreign Exchange  │
 │ (Profiles, Events, etc) │     │ (Messages, Invoices/Imgs) │     │ (Dated FX Rate Converter) │
 └────────────┬────────────┘     └─────────────┬─────────────┘     └─────────────┬─────────────┘
              │                                │                                 │
              └────────────────────────┬───────┴─────────────────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │  90-Day Cash Flow Simulator   │
                       │  (Daily Balance Trajectory)   │
                       └───────────────┬───────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │    Payment Plan Evaluator     │
                       │(Full, Part, Installment, Wait)│
                       └───────────────┬───────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │    Safety Gate Validator      │
                       │  (Floor / Essential Guard)    │
                       └───────────────┬───────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │ CSV Serializer & Schema Guard │
                       │ (Strict 8-Column Root Output) │
                       └───────────────────────────────┘
```

### Why Deterministic Simulation?
- **Zero Arithmetic Hallucination**: 100% of cash flow projections, daily interest/balances, and payment plan feasibility are calculated via deterministic Python code with exact decimal precision.
- **Zero API Dependency for Math**: The financial engine runs 100% offline, lightning fast (250 requests processed in under **3.5 seconds**), and deterministically reproducible.

---

##  Key Features & Capabilities

- ⚡ **Lightning Fast Performance**: Evaluates all 250 requests with full 90-day daily balance trajectories in **~3.5 seconds**.
- 🌐 **Multi-Currency FX Support**: Native handling of INR (`₹`), USD (`$`), EUR (`€`), ZAR (`R`), and IDR (`Rp`) using dated exchange rate matrices.
- 💳 **Intelligent Payment Plan Selection**: Automatically evaluates full upfront payment, 2-stage partial payments, provider installment plans, delayed purchase dates, or explicit rejection recommendations.
- ✂️ **Flexible Spending Optimization**: Suggests non-essential spending reductions strictly targeting events marked `flexible=true` (e.g., `stop:<event_id>` or `reduce_to:<event_id>:<amount>`).
- 🖥️ **Interactive Web Cockpit**: Live FastAPI dashboard running on `http://localhost:8000` with interactive request exploration, visual safety checks, and what-if simulation sandbox.

---

##  System Requirements & Installation

### Prerequisites
- **Python**: Version `3.10` or higher
- **OS**: Windows, macOS, or Linux

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/tribhu05/hackerrank-orchestrate-september26.git
   cd hackerrank-orchestrate-september26
   ```

2. **Create and activate virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r code/requirements.txt
   ```
   *(Or install core runtime requirements: `pip install pandas pytest fastapi uvicorn requests`)*

---

## 🚀 Quick Start & Terminal Execution

### 1. Run Main Production Pipeline
Generate the root `output.csv` predictions for all 250 dataset requests:

```bash
python code/main.py
```

*Output:*
```text
============================================================
HackerRank Orchestrate — Buy or Wait? Financial Decision Agent
============================================================
[1/4] Loading datasets...
[2/4] Initializing Decision Engine...
[3/4] Evaluating 250 requests...
[4/4] Validating outputs...
Validation PASSED! All schema, enum, and bound constraints verified.
Predictions written successfully to: output.csv
Total elapsed time: 3.48 seconds
============================================================
```

### 2. Run Evaluation Suite & Schema Benchmark
Audit schema compliance, value constraints, and evaluate accuracy against sample benchmarks:

```bash
python code/evaluation/main.py
```

### 3. Run Automated Tests
Execute the complete `pytest` automated test suite:

```bash
pytest tests
```

---

##  Interactive Cockpit Web Dashboard

Launch the FastAPI web cockpit locally to visually inspect requests, explore safety checks, and test custom scenarios:

```bash
python server.py
```

Open your browser and navigate to **`http://localhost:8000`**

### Dashboard Features
- 📊 **Executive Overview**: Total request counts, status distributions, and affordability metrics.
- 🔍 **Interactive Request Inspector**: Select any of the 250 requests to view user financial profiles, daily projected balances, safety checks (`✓`/`✕`), and recommended payment plans.
- 🧪 **What-If Scenario Sandbox**: Tweak available savings, floor requirements, and income deltas to test live recalculations.
- 📑 **Evaluation Suite & Export**: Run benchmarks on the fly and inspect clean dataset predictions.

---

## 📊 Dataset Specifications & Input Pipeline

The pipeline ingests 8 structured/unstructured files inside `dataset/`:

| Dataset File | Description |
|---|---|
| `requests.csv` | The 250 evaluation requests (`request_id`, `user_id`, `requested_amount`, `currency`, `request_date`, `desired_completion_date`). |
| `financial_profiles.csv` | User home currency, initial available balance, minimum safety floor, payment preferences, and installment caps. |
| `financial_events.csv` | Historical, pending, scheduled, settled, failed, and recurring financial cash flows. |
| `request_payment_options.csv` | Provider payment options (down payments, interest rates, installment frequencies). |
| `exchange_rates.csv` | Fixed settlement exchange rates across INR, EUR, USD, ZAR, and IDR. |
| `messages.csv` | Supporting message evidence (payroll confirmation, payment deferrals, invoices). |
| `images.csv` | Supporting image evidence metadata mapping to `dataset/media/images/*.png`. |
| `output.csv` | Blank output template specifying the 8 required columns. |

---

## 📈 Evaluation & Benchmark Suite

The solution contains a built-in evaluator (`code/evaluation/main.py`) enforcing:

1. **Schema & Header Verification**: Exact 8 required columns in exact required order.
2. **Bounds & Enum Integrity**: $0 \le \text{amount\_safe\_to\_pay} \le \text{requested\_amount}$, valid enum statuses, valid payment plans.
3. **Sample Benchmark Verification**: High accuracy on public sample cases (`dataset/sample_requests.csv`).

```text
[1/4] Auditing Output CSV Schema... [OK]
[2/4] Auditing Value Constraints & Enums... [OK]
[3/4] Prediction Distribution:
      not_affordable       : 91 (36.4%)
      affordable_now       : 57 (22.8%)
      affordable_with_plan : 54 (21.6%)
      affordable_later     : 48 (19.2%)
[4/4] Sample Benchmark Validation... [PASSED]
```

---

## 📜 Submission Artifacts & Token Cost Analysis

As specified in §6.5 of `AGENTS.md`, model usage for the complete 250-request evaluation run is summarized in [`evaluation/usage_report.md`](file:///c:/Users/Tribh/Downloads/hackerrank-orchestrate-september26/evaluation/usage_report.md):

| Metric | Details |
|---|---|
| **Model Provider** | Google DeepMind / Google Gemini |
| **Model Name** | `gemini-2.5-flash` |
| **Total Evaluation Requests** | 250 requests |
| **Total Tokens** | 131,250 tokens |
| **Total Run Cost** | **$0.01407 USD** (~$0.000056 / request) |
| **Execution Time** | **3.48 seconds** |

---

## 📁 Project Directory Structure

```text
hackerrank-orchestrate-september26/
├── AGENTS.md                   # Single source of truth for AI agents & logging rules
├── problem_statement.md        # Official contest problem statement & rules
├── README.md                   # Complete project documentation (this file)
├── output.csv                  # Official generated 250-request predictions
├── server.py                   # FastAPI web cockpit server & static dashboard
├── app.py                      # Alternative Streamlit dashboard
├── log.txt                     # Mandatory session and per-turn audit log
├── code/
│   ├── main.py                 # Primary terminal entry point
│   ├── data_loader.py          # Multi-dataset parser & relationship builder
│   ├── simulator.py            # 90-day daily balance cash flow simulation engine
│   ├── decision_engine.py      # Affordability evaluator, safety gates & plan selection
│   ├── currency.py             # FX converter matrix
│   ├── message_extractor.py    # Unstructured text message parser
│   ├── image_extractor.py      # Invoice/receipt OCR extractor
│   └── evaluation/
│       └── main.py             # Schema & benchmark evaluator
├── dataset/                    # Official challenge datasets
└── tests/                      # Automated unit and integration test suite
    └── test_solution.py
```

---
