# Temporal-HalluBench

Temporal-HalluBench is a research benchmark for evaluating hallucinations,
factual reliability, temporal reasoning, and forecasting ability of Large
Language Models (LLMs).

The project evaluates multiple LLMs across different real-world domains
using source-backed ground truth.

## Research Questions

The benchmark investigates:

1. How often do different LLMs hallucinate?
2. What types of hallucinations occur most frequently?
3. Which types of questions are most difficult for LLMs?
4. How frequently do LLMs hallucinate proper nouns, attributes, relationships,
   and numerical facts?
5. How well do LLMs handle multi-hop questions?
6. How well do LLMs reject false-premise questions?
7. How do hallucination rates change for temporal information?
8. How accurately can LLMs forecast future information when given only
   historical data?

## Domains

The benchmark will initially contain:

- Cricket
- Cinema
- Scientists
- CRM complaints
- Quick-commerce reviews
- Smartphones

The smartphone domain will additionally be used for temporal forecasting.

## Models

The benchmark is designed to evaluate multiple LLM providers, including:

- OpenAI
- Google Gemini
- Anthropic Claude
- xAI Grok
- DeepSeek
- Qwen

Exact model versions will be recorded in the experiment configuration.

## Hallucination Categories

The benchmark will detect and classify:

1. Fabricated Entity
2. Wrong Entity
3. Proper-Noun Hallucination
4. Alias/Nickname Error
5. Attribute Error
6. Common-Concept / Unsupported Attribute
7. Numerical Error
8. Relationship Error
9. Multi-Hop Error
10. Entity Mixing
11. Temporal Error
12. Unsupported Claim
13. False-Premise Acceptance

Forecasting errors will be evaluated separately from hallucinations.

## Core Pipeline

```text
Real Data Sources
        ↓
Data Collection
        ↓
Raw Data
        ↓
Cleaning
        ↓
Normalization
        ↓
Ground Truth
        ↓
Question Generation
        ↓
LLM Evaluation
        ↓
Claim Extraction
        ↓
Ground Truth Matching
        ↓
Hallucination Classification
        ↓
Metrics
        ↓
Analysis