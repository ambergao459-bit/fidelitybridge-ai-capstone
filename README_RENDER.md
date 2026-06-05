# Render Deployment Guide: FidelityBridge AI

This version is ready for Render. The app is a Gradio web app with a Python backend.

## 1. Files to upload

Upload the whole project folder to a GitHub repository, including:

- `app.py`
- `backend.py`
- `prompts.py`
- `requirements.txt`
- `render.yaml`
- `Procfile`
- `.env.example`

Do **not** upload your real `.env` file or API key.

## 2. Deploy on Render

1. Go to Render and create a new **Web Service**.
2. Connect the GitHub repository.
3. Use these settings:

```text
Environment: Python
Build Command: pip install -r requirements.txt
Start Command: python app.py
Plan: Free
```

The included `render.yaml` already contains the same basic configuration. You can use Render's Blueprint flow or manually create a Web Service.

## 3. Add environment variables

In Render dashboard, go to the Web Service -> **Environment** and add:

```text
OPENAI_API_KEY = your OpenAI API key
OPENAI_MODEL = gpt-4o-mini
MAX_CHARS_FOR_LLM = 45000
```

Optional, only if using an OpenAI-compatible provider:

```text
OPENAI_BASE_URL = provider API base URL
```

## 4. Important classroom notes

- Free Render services may sleep after inactivity. Open the app 5-10 minutes before class and run one test upload.
- Keep a local backup running on your laptop:

```bash
python app.py
```

- In the live demo, upload the instructor's paper and click stages one by one:
  1. Intake
  2. Extract
  3. Classify
  4. Show Prompt
  5. Generate
  6. Score D1-D7
  7. QA Fix

- Select only 1-2 outputs. Do not try to generate all 18 during the live run.

## 5. Troubleshooting

### App builds but the webpage does not open
Check that `app.py` ends with:

```python
app.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", 7860)),
    show_error=True,
)
```

### App runs but uses fallback mode
That means `OPENAI_API_KEY` is missing or invalid in Render environment variables.

### Upload is slow
Use a smaller PDF or paste the abstract/method/results text into the text box. The app truncates very long papers for model calls using `MAX_CHARS_FOR_LLM`.
