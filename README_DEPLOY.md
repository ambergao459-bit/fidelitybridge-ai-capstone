# Deployment Guide for FidelityBridge AI

## Recommended for this class: Render

This package has already been modified for Render. The important Render fix is in `app.py`:

```python
app.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", 7860)),
    show_error=True,
)
```

Render settings:

```text
Environment: Python
Build Command: pip install -r requirements.txt
Start Command: python app.py
```

Environment variables:

```text
OPENAI_API_KEY = your key
OPENAI_MODEL = gpt-4o-mini
MAX_CHARS_FOR_LLM = 45000
```

The project also includes `render.yaml` and `Procfile`.

## Local backup

Always keep a local backup for class day:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Windows: copy .env.example .env
python app.py
```

Then open the local Gradio link shown in the terminal.

## Class-day checklist

- API key is set in Render.
- App opens before class starts.
- Prepared e-government paper has been tested once.
- Output types are limited to 1-2.
- The team knows how to click each stage separately.
- Local backup is ready if the Render free service sleeps or restarts.
