import inspect
import json
from typing import Any, Dict, List, Optional

import gradio as gr

import backend as backend_mod
from backend import run_workflow, save_trace
from prompts import APP_TITLE, OUTPUT_TYPES, STAGE_PROMPTS, STAGES

CSS = """
:root {
  --brand: #f97316;
  --ink: #111827;
  --muted: #4b5563;
  --line: #e5e7eb;
  --panel: #ffffff;
  --bg: #f8fafc;
}
* { box-sizing: border-box; }
.gradio-container {
  max-width: 1280px !important;
  margin: 0 auto !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, "PingFang SC", "Microsoft YaHei", sans-serif !important;
  background: var(--bg) !important;
  color: var(--ink) !important;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
.hero {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 22px 26px;
  margin-bottom: 12px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
}
.hero h1 { margin: 0 0 8px 0; font-size: 30px; line-height: 1.25; font-weight: 800; }
.hero p { margin: 0; color: var(--muted); font-size: 16px; line-height: 1.55; }
.left-panel, .stage-output {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 16px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
}
.section-label { font-weight: 750; margin: 6px 0 8px; color: var(--ink); }
button.stage-btn {
  border-radius: 16px !important;
  min-height: 64px !important;
  font-size: 18px !important;
  font-weight: 750 !important;
  border: 1px solid var(--line) !important;
  background: #fff !important;
  color: var(--ink) !important;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06) !important;
}
button.stage-btn:hover {
  border-color: #fdba74 !important;
  box-shadow: 0 6px 16px rgba(249, 115, 22, 0.16) !important;
}
button.primary-run {
  border-radius: 14px !important;
  min-height: 56px !important;
  font-size: 18px !important;
  font-weight: 800 !important;
  background: var(--brand) !important;
  color: white !important;
  border: none !important;
}
.stage-title { margin: 0 0 14px; font-size: 28px; line-height: 1.25; font-weight: 800; color: var(--ink); }
.stage-card {
  border-left: 6px solid var(--brand);
  background: #fff;
  border-radius: 18px;
  padding: 22px 24px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
  font-size: 16px;
  line-height: 1.68;
  overflow-wrap: break-word;
  word-break: normal;
}
.stage-card h3 { margin: 0 0 12px; font-size: 22px; line-height: 1.3; font-weight: 800; }
.stage-card p { margin: 10px 0; }
.stage-card strong { font-weight: 800; color: var(--ink); }
.stage-card table { width: 100%; border-collapse: collapse; margin: 8px 0 14px; table-layout: fixed; }
.stage-card th, .stage-card td { border-bottom: 1px solid #edf1f7; padding: 10px 8px; vertical-align: top; overflow-wrap: break-word; }
.stage-card th { width: 190px; text-align: left; background: #f9fafb; font-weight: 800; }
.stage-card ul { margin: 8px 0 0 22px; padding: 0; }
.stage-card li { margin: 4px 0; }
.status-row { margin: 8px 0 16px; display: flex; flex-wrap: wrap; gap: 8px; }
.status-pill { display: inline-block; padding: 7px 10px; border-radius: 999px; border: 1px solid #d1d5db; background: #fff; color: #374151; font-size: 14px; font-weight: 700; }
.status-pill.done { background: #ecfdf5; border-color: #a7f3d0; color: #047857; }
.status-pill.active { background: #fff7ed; border-color: #fdba74; color: #c2410c; }
.audit-box { margin-top: 16px; color: #4b5563; }
.audit-box summary { cursor: pointer; font-weight: 700; }
.audit-pre {
  white-space: pre-wrap;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  color: #374151;
  font-size: 14px;
  line-height: 1.55;
}
.code-section {
  margin-top: 20px;
  border-top: 1px solid #e5e7eb;
  padding-top: 16px;
}
.code-title {
  font-size: 18px;
  font-weight: 800;
  margin: 0 0 10px;
  color: #111827;
}
.code-pre {
  white-space: pre-wrap;
  background: #0f172a;
  color: #e5e7eb;
  border: 1px solid #1f2937;
  border-radius: 14px;
  padding: 16px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.55;
  max-height: 420px;
  overflow: auto;
}
.compare-table th { width: 160px !important; }
pre.json-block {
  white-space: pre-wrap;
  background: #111827;
  color: #f9fafb;
  border-radius: 12px;
  padding: 14px;
  overflow: auto;
  font-size: 14px;
  line-height: 1.5;
}
textarea, input { border-radius: 12px !important; }
@media (max-width: 900px) {
  .stage-title { font-size: 24px; }
  .stage-card { font-size: 15px; padding: 18px; }
  .stage-card th { width: 135px; }
  button.stage-btn { font-size: 16px !important; min-height: 56px !important; }
}
"""


def esc(text: Any) -> str:
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def bullet(items: Optional[List[str]]) -> str:
    if not items:
        return "<p>None detected.</p>"
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def json_pretty(obj: Any) -> str:
    return "<pre class='json-block'>" + esc(json.dumps(obj, ensure_ascii=False, indent=2)) + "</pre>"


def render_before_after(items: Optional[List[Dict[str, Any]]]) -> str:
    if not items:
        return "<p>No review rewrite item was generated.</p>"
    rows = []
    for item in items:
        rows.append(
            "<tr><th>Location</th><td>" + esc(item.get("location")) + "</td></tr>"
            "<tr><th>Before</th><td>" + esc(item.get("before")) + "</td></tr>"
            "<tr><th>After</th><td>" + esc(item.get("after")) + "</td></tr>"
            "<tr><th>Reason</th><td>" + esc(item.get("reason")) + "</td></tr>"
        )
    return "<table class='compare-table'>" + "".join(rows) + "</table>"


STAGE_FUNCTIONS = {
    "intake": ["read_uploaded_file", "read_pdf", "read_docx", "normalize_text", "clean_pdf_artifacts"],
    "extract": [
        "make_extraction_record",
        "detect_title",
        "detect_authors",
        "detect_publication_year",
        "detect_publication_venue",
        "detect_doi",
        "detect_research_objective",
        "detect_method",
        "detect_sample",
        "detect_key_findings",
        "detect_limitations",
    ],
    "classify": ["classify_record"],
    "generate": ["bounded_finding", "generate_output", "generate_outputs"],
    "score": ["score_one_output", "score_outputs"],
    "review": ["_plain_output_sentences", "_rewrite_sentence_for_review", "_select_review_sentence", "review_outputs"],
}


def code_block(stage: str) -> str:
    names = STAGE_FUNCTIONS.get(stage, [])
    blocks = []
    for name in names:
        obj = getattr(backend_mod, name, None)
        if obj is None:
            continue
        try:
            blocks.append(inspect.getsource(obj).strip())
        except Exception:
            continue
    if not blocks:
        return ""
    return f"""
    <div class='code-section'>
      <div class='code-title'>Code used for this stage</div>
      <pre class='code-pre'>{esc(chr(10) + chr(10).join(blocks))}</pre>
    </div>
    """


def status_html(active: str, has_trace: bool) -> str:
    pills = []
    for key, label in STAGES:
        cls = "active" if key == active else ("done" if has_trace else "")
        pills.append(f"<span class='status-pill {cls}'>{esc(label)}</span>")
    return "<div class='status-row'>" + "".join(pills) + "</div>"


def render_empty() -> str:
    return """
    <div class='stage-output'>
      <div class='stage-title'>Ready</div>
      <div class='stage-card'>
        <h3>Upload a paper and run the workflow</h3>
        <p>The system will process the paper through six visible stages: Intake, Extract, Classify, Generate, Score, and Review.</p>
        
      </div>
    </div>
    """


def render_stage(trace: Optional[Dict[str, Any]], stage: str) -> str:
    if not trace:
        return render_empty()

    progress = status_html(stage, True)

    if stage == "intake":
        meta = trace.get("intake", {})
        preview = trace.get("raw_text_preview", "")
        content = f"""
        <div class='stage-title'>Stage 1 — Intake / Parse</div>
        {progress}
        <div class='stage-card'>
          <h3>Input record</h3>
          <table>
            <tr><th>Source type</th><td>{esc(meta.get('source_type'))}</td></tr>
            <tr><th>File name</th><td>{esc(meta.get('file_name'))}</td></tr>
            <tr><th>File size</th><td>{esc(meta.get('file_size_kb', 'N/A'))} KB</td></tr>
            <tr><th>Text characters used</th><td>{esc(meta.get('text_characters_used'))}</td></tr>
          </table>
          <h3>Parsed preview</h3>
          <p>{esc(preview[:1500])}</p>
        </div>
        {code_block(stage)}
        """
    elif stage == "extract":
        ex = trace.get("extraction", {})
        content = f"""
        <div class='stage-title'>Stage 2 — Extract Evidence</div>
        {progress}
        <div class='stage-card'>
          <h3>Article metadata</h3>
          <table>
            <tr><th>Title</th><td>{esc(ex.get('paper_title'))}</td></tr>
            <tr><th>Author(s)</th><td>{esc(ex.get('authors'))}</td></tr>
            <tr><th>Publication year</th><td>{esc(ex.get('publication_year'))}</td></tr>
            <tr><th>Publication venue</th><td>{esc(ex.get('publication_venue'))}</td></tr>
            <tr><th>Publication period</th><td>{esc(ex.get('publication_period'))}</td></tr>
            <tr><th>DOI</th><td>{esc(ex.get('doi'))}</td></tr>
            <tr><th>Citation draft</th><td>{esc(ex.get('citation_apa'))}</td></tr>
          </table>
          <h3>Evidence record</h3>
          <p><strong>Research objective:</strong> {esc(ex.get('research_objective'))}</p>
          <p><strong>Method / design:</strong> {esc(ex.get('method_design'))}</p>
          <p><strong>Sample / context:</strong> {esc(ex.get('sample_context'))}</p>
          <p><strong>Variables / constructs:</strong> {esc(', '.join(ex.get('variables_constructs', [])))}</p>
          <p><strong>Key finding:</strong> {esc(ex.get('key_findings'))}</p>
          <p><strong>Limits / boundaries:</strong> {esc(ex.get('limitations_or_boundaries'))}</p>
          <p><strong>What the paper does not prove:</strong> {esc(ex.get('what_the_paper_does_not_prove'))}</p>
        </div>
        {code_block(stage)}
        """
    elif stage == "classify":
        cl = trace.get("classification", {})
        content = f"""
        <div class='stage-title'>Stage 3 — Classify + Route</div>
        {progress}
        <div class='stage-card'>
          <h3>Method classification</h3>
          <table>
            <tr><th>Tradition</th><td>{esc(cl.get('methodological_tradition'))}</td></tr>
            <tr><th>Confidence</th><td>{esc(cl.get('confidence'))}</td></tr>
            <tr><th>Route</th><td>{esc(cl.get('route'))}</td></tr>
            <tr><th>Evidence boundary</th><td>{esc(cl.get('evidence_boundary'))}</td></tr>
          </table>
          <h3>Guardrails loaded</h3>
          {bullet(cl.get('recommended_guardrails', []))}
        </div>
        {code_block(stage)}
        """
    elif stage == "generate":
        outputs = trace.get("outputs", {})
        cards = ""
        for name, text in outputs.items():
            cards += f"<h3>{esc(name)}</h3><div style='border:1px solid #edf1f7;border-radius:14px;padding:16px;margin:0 0 18px;background:#fbfcff'>{text}</div>"
        content = f"""
        <div class='stage-title'>Stage 4 — Generate Outputs</div>
        {progress}
        <div class='stage-card'>
          <p><strong>Output count:</strong> {len(outputs)} selected output type(s)</p>
          {cards}
        </div>
        {code_block(stage)}
        """
    elif stage == "score":
        scores = trace.get("scores", {})
        means = scores.get("dimension_means", {})
        rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in means.items())
        details = json_pretty(scores.get("by_output", {}))
        content = f"""
        <div class='stage-title'>Stage 5 — Score D1-D7</div>
        {progress}
        <div class='stage-card'>
          <h3>Dimension means</h3>
          <table><tr><th>Dimension</th><th>Mean score</th></tr>{rows}</table>
          <table>
            <tr><th>Strongest dimension</th><td>{esc(scores.get('strongest_dimension_label'))} ({esc(scores.get('strongest_dimension'))}) — {esc(scores.get('strongest_score'))}/5</td></tr>
            <tr><th>Weakest dimension</th><td>{esc(scores.get('weakest_dimension_label'))} ({esc(scores.get('weakest_dimension'))}) — {esc(scores.get('weakest_score'))}/5</td></tr>
          </table>
          <details><summary><strong>Detailed scores by output</strong></summary>{details}</details>
        </div>
        {code_block(stage)}
        """
    elif stage == "review":
        review = trace.get("review", {})
        content = f"""
        <div class='stage-title'>Stage 6 — Review / QA Fix</div>
        {progress}
        <div class='stage-card'>
          <h3>QA check</h3>
          <p>{esc(review.get('qa_catch'))}</p>
          <h3>Before / after comparison</h3>
          {render_before_after(review.get('before_after_comparison', []))}
          <h3>Issues detected</h3>
          {bullet(review.get('issues_detected', []))}
          <h3>Targeted fixes</h3>
          {bullet(review.get('targeted_fixes', []))}
        </div>
        {code_block(stage)}
        """
    else:
        content = render_empty()

    return f"<div class='stage-output'>{content}</div>"


def run_and_render(file_obj: Any, pasted_text: str, selected_outputs: List[str], audience: str):
    try:
        selected = selected_outputs or ["Technical Note", "Media Release"]
        trace = run_workflow(file_obj, pasted_text, selected[:2], audience or "public administration practitioners")
        export_path = save_trace(trace)
        return trace, render_stage(trace, "intake"), export_path
    except Exception as exc:
        error_html = f"""
        <div class='stage-output'>
          <div class='stage-title'>Error</div>
          <div class='stage-card'><p>{esc(str(exc))}</p></div>
        </div>
        """
        return None, error_html, None


def show_stage(trace: Optional[Dict[str, Any]], stage: str):
    return render_stage(trace, stage)


with gr.Blocks(title=APP_TITLE, css=CSS) as demo:
    gr.HTML(
        """
        <div class='hero'>
          <h1>FidelityBridge AI</h1>
          <p>Upload a paper, choose 1-2 output types, and run the six-stage workflow.</p>
        </div>
        """
    )
    state = gr.State(value=None)

    with gr.Row():
        with gr.Column(scale=4):
            with gr.Group(elem_classes=["left-panel"]):
                gr.Markdown("### Paper input")
                file_in = gr.File(label="Upload paper PDF / DOCX / TXT", file_types=[".pdf", ".docx", ".txt"])
                pasted = gr.Textbox(
                    label="Or paste paper text",
                    lines=8,
                    placeholder="Paste abstract, methods, or full paper text here if needed...",
                )
                outputs = gr.CheckboxGroup(
                    choices=OUTPUT_TYPES,
                    value=["Technical Note", "Media Release"],
                    label="Output types for live run",
                    info="Choose 1-2. The system uses only the first two selected outputs.",
                )
                audience = gr.Textbox(
                    label="Target audience",
                    value="public administration practitioners and agency managers",
                )
                run_btn = gr.Button("Run Full Workflow", elem_classes=["primary-run"])
                reset_btn = gr.Button("Reset")
                export_file = gr.File(label="Download JSON trace", interactive=False)

        with gr.Column(scale=8):
            gr.Markdown("### Six workflow stages")
            with gr.Row():
                b1 = gr.Button("1 Intake", elem_classes=["stage-btn"])
                b2 = gr.Button("2 Extract", elem_classes=["stage-btn"])
                b3 = gr.Button("3 Classify", elem_classes=["stage-btn"])
            with gr.Row():
                b4 = gr.Button("4 Generate", elem_classes=["stage-btn"])
                b5 = gr.Button("5 Score D1-D7", elem_classes=["stage-btn"])
                b6 = gr.Button("6 Review / QA Fix", elem_classes=["stage-btn"])
            display = gr.HTML(value=render_empty())

    run_btn.click(run_and_render, inputs=[file_in, pasted, outputs, audience], outputs=[state, display, export_file])
    b1.click(lambda tr: show_stage(tr, "intake"), inputs=[state], outputs=[display])
    b2.click(lambda tr: show_stage(tr, "extract"), inputs=[state], outputs=[display])
    b3.click(lambda tr: show_stage(tr, "classify"), inputs=[state], outputs=[display])
    b4.click(lambda tr: show_stage(tr, "generate"), inputs=[state], outputs=[display])
    b5.click(lambda tr: show_stage(tr, "score"), inputs=[state], outputs=[display])
    b6.click(lambda tr: show_stage(tr, "review"), inputs=[state], outputs=[display])
    reset_btn.click(lambda: (None, render_empty(), None), outputs=[state, display, export_file])

if __name__ == "__main__":
    import os
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)), show_error=True)
