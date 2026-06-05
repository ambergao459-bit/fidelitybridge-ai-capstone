---
title: FidelityBridge AI
emoji: 🧭
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
pinned: false
license: mit
---

# FidelityBridge AI

FidelityBridge AI is an interactive Capstone demo system for translating public-administration research papers into practitioner-ready outputs while preserving evidence fidelity.

It is built around the required visible workflow:

1. Intake / parse uploaded paper
2. Extract a structured evidence record
3. Classify methodological tradition and route guardrails
4. Show the actual generation prompt
5. Generate 1-2 output types
6. Score D1-D7 fidelity dimensions
7. Catch and fix one failure mode

The interface is designed for both the prepared trace demo and the out-of-sample live Q&A paper.

## Local Quick Start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add OPENAI_API_KEY
python app.py
```

Then open the local Gradio URL shown in the terminal.

## Required Secret

Set `OPENAI_API_KEY` for real analysis. Without it, the app still opens and runs a transparent rule-based fallback, but the fallback is not recommended for your graded live demo.

## Presenter Use

For the prepared trace, upload your prepared e-government paper and click each stage one by one so the audience sees every intermediate result. For the out-of-sample paper, upload the instructor's file and run the same stages live.

Do not generate all 18 outputs during the demo. Select only 1-2 outputs, then score them on D1-D7.
