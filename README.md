# FidelityBridge AI — Free Workflow Demo

This version is built for a classroom Capstone live demonstration when API credits are unavailable.

It uses no paid OpenAI API call. The workflow is deterministic and interactive:

1. Intake / Parse
2. Extract Evidence
3. Classify + Route
4. Generate 1-2 Outputs
5. Score D1-D7
6. Review / QA Fix

## Local run

```bash
pip install -r requirements.txt
python app.py
```

## Render deployment

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
python app.py
```

No `OPENAI_API_KEY` is required.

## What to tell the instructor

This is not one mega-prompt. It is an automated, staged workflow that makes each intermediate record visible. It uses rule-based extraction, method-aware routing, output schemas, D1-D7 scoring, and QA failure-mode checks.
