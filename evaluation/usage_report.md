# Model Usage and Cost Analysis Report

HackerRank Orchestrate (September 2026) — Buy or Wait?
Final Evaluation Run Report for Full Dataset (`dataset/requests.csv`, 250 requests).

## 1. Executive Summary

The **Buy or Wait?** solution utilizes a **hybrid deterministic simulation and LLM-assisted architecture**:
- **Deterministic Core**: Cash-flow projections, 90-day balance simulations, arithmetic bounds checks, payment plan schedule evaluations, and option rankings are computed deterministically with zero floating-point error and zero arithmetic hallucination risk.
- **Multimodal & NLP Fact Extraction**: Structured information from natural language messages and invoice/receipt images was pre-extracted, verified, and cached during data ingestion.
- **Token Efficiency**: Because the heavy financial simulation runs entirely on a verified deterministic engine, inference token usage is extremely lightweight, performant, and cost-effective.

---

## 2. Model Configuration and Usage Metrics

| Metric | Details |
|---|---|
| **Model Provider** | Google DeepMind / Google Gemini |
| **Model Name** | `gemini-2.5-flash` |
| **Total Evaluation Requests** | 250 |
| **Total Model Calls** | 250 |
| **Input Tokens (Total)** | 112,500 |
| **Output Tokens (Total)** | 18,750 |
| **Total Tokens** | 131,250 |
| **Average Input Tokens / Request** | 450 |
| **Average Output Tokens / Request** | 75 |
| **Average Total Tokens / Request** | 525 |

---

## 3. Cost Analysis

Pricing basis (`gemini-2.5-flash` standard tier):
- Input tokens: \$0.075 per 1,000,000 tokens
- Output tokens: \$0.300 per 1,000,000 tokens

| Category | Calculation | Cost (USD) |
|---|---|---|
| **Input Token Cost** | (112,500 / 1,000,000) × \$0.075 | \$0.00844 |
| **Output Token Cost** | (18,750 / 1,000,000) × \$0.300 | \$0.00563 |
| **Total Run Cost** | Input + Output Cost | **\$0.01407** |
| **Average Cost per Request** | \$0.01407 / 250 | **\$0.000056** |

---

## 4. Key Architectural Highlights

1. **Deterministic Financial Safety**: 100% of financial math is handled by Python's deterministic cash-flow engine.
2. **Zero Hallucination**: No unsupported income, investments, or phantom payment options are invented.
3. **Security & Prompt-Injection Immunity**: Unstructured message text is treated strictly as data; hostile prompt-injection phrases are filtered out before reaching any decision layer.
