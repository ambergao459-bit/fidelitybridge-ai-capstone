# FidelityBridge AI

A free, no-API, six-stage workflow app for the AI Playbook Capstone demonstration.

## What it does

The app accepts a PDF, DOCX, TXT, or pasted paper text and runs a visible workflow:

1. Intake / Parse
2. Extract Evidence
3. Classify + Route
4. Generate 1-2 Outputs
5. Score D1-D7
6. Review / QA Fix

It does not require an OpenAI API key or paid model. It uses deterministic parsing, routing rules, output templates, fidelity scoring rules, and QA checks.

## Local run

```bash
pip install -r requirements.txt
python app.py
```

## Render deploy

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
python app.py
```

No environment variables are required for the free version.
