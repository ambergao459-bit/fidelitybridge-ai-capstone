import json
from typing import Any, Dict, List

import gradio as gr

from backend import run_workflow, save_trace
from prompts import APP_TITLE, OUTPUT_TYPES, STAGE_PROMPTS, STAGES

CSS = """
:root { --brand:#ff6b1a; --ink:#172033; --soft:#fff4e8; --line:#e8ecf3; --green:#12a150; }
.gradio-container { max-width: 1320px !important; margin: auto !important; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif !important; background:#f7f9fc !important; }
.hero { padding: 26px 30px; border:1px solid #dbece3; border-radius:24px; background:linear-gradient(135deg,#f7fffb,#eef7ff); box-shadow:0 8px 30px rgba(15,23,42,.06); }
.hero h1 { margin:0; font-size:34px; color:var(--ink); }
.hero p { margin:10px 0 0; line-height:1.65; color:#344054; }
.panel { border:1px solid var(--line); border-radius:22px; background:#fff; box-shadow:0 8px 22px rgba(15,23,42,.06); padding:18px; }
.stage-title { font-size:30px; font-weight:850; color:var(--ink); margin:8px 0 12px; }
.mode-ok { display:inline-block; padding:8px 12px; border-radius:999px; background:#e9fff2; color:#07783d; font-weight:750; border:1px solid #b9efcf; }
.workflow-note { color:#526071; font-size:15px; margin-bottom:16px; }
.stage-card { border-left:8px solid var(--brand); background:#fff; border-radius:20px; padding:24px 28px; box-shadow:0 8px 28px rgba(15,23,42,.08); font-size:17px; line-height:1.72; color:#172033; }
.stage-card h3 { margin-top:0; font-size:24px; }
.stage-card strong { color:#121a2b; }
.stage-card table { width:100%; border-collapse:collapse; margin-top:8px; }
.stage-card td, .stage-card th { border-bottom:1px solid #edf1f7; padding:10px 8px; vertical-align:top; }
.stage-card th { text-align:left; background:#f8fafc; }
button.stage-btn { border-radius:22px !important; min-height:72px !important; font-size:20px !important; font-weight:850 !important; border:1px solid #e3e8ef !important; background:white !important; box-shadow:0 8px 20px rgba(15,23,42,.08) !important; color:#172033 !important; }
button.stage-btn:hover { border-color:#ffad7c !important; box-shadow:0 10px 26px rgba(255,107,26,.18) !important; transform:translateY(-1px); }
button.primary-run { border-radius:16px !important; min-height:58px !important; font-size:20px !important; font-weight:850 !important; background:var(--brand) !important; color:white !important; border:0 !important; }
.label-pill { display:inline-block; margin:4px 6px 4px 0; padding:8px 12px; border-radius:999px; background:#f2f5f9; border:1px solid #e1e7ef; font-weight:700; color:#4b5565; }
.label-done { background:#eafff3; border-color:#b8edcf; color:#087a3d; }
.label-active { background:#fff2e8; border-color:#ffc69e; color:#b54600; }
textarea, input { border-radius:14px !important; }
"""


def esc(text: Any) -> str:
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bullet(items: List[str]) -> str:
    if not items:
        return "<em>None detected.</em>"
    return "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>"


def json_pretty(obj: Any) -> str:
    return "<pre style='white-space:pre-wrap;background:#0b1020;color:#eaf2ff;border-radius:14px;padding:16px;overflow:auto;'>" + esc(json.dumps(obj, ensure_ascii=False, indent=2)) + "</pre>"


def render_empty() -> str:
    return """
    <div class='stage-title'>Ready for live demo</div>
    <div class='workflow-note'>Upload a paper or paste text, choose 1-2 output types, then click <strong>Run Full Workflow</strong>. After it runs, click the six stage cards above to present each part.</div>
    <div class='stage-card'>
      <h3>What this free version does</h3>
      <p><strong>No paid API is required.</strong> This version uses deterministic parsing, method detection, output templates, fidelity scoring rules, and QA checks. It is fully interactive and safe for a classroom demo when API credits are unavailable.</p>
      <p>It still follows the required staged workflow: <strong>Intake → Extract → Classify → Generate → Score → Review</strong>.</p>
    </div>
    """


def progress_html(active: str, has_trace: bool) -> str:
    pills = []
    for idx, (key, label) in enumerate(STAGES, start=1):
        cls = "label-active" if key == active else ("label-done" if has_trace else "")
        check = "✓ " if has_trace else ""
        pills.append(f"<span class='label-pill {cls}'>{check}{esc(label)}</span>")
    return "".join(pills)


def render_stage(trace: Dict[str, Any] | None, stage: str) -> str:
    if not trace:
        return render_empty()
    mode = trace.get("mode", "Free workflow")
    header = f"<span class='mode-ok'>Mode: {esc(mode)}</span>"
    progress = progress_html(stage, True)

    if stage == "intake":
        meta = trace.get("intake", {})
        preview = trace.get("raw_text_preview", "")
        body = f"""
        <div class='stage-title'>Stage 1 — Intake / Parse</div>
        {header}<div style='height:12px'></div>{progress}
        <div class='stage-card'>
          <h3>What the system ingested</h3>
          <table>
            <tr><th>Source type</th><td>{esc(meta.get('source_type'))}</td></tr>
            <tr><th>File name</th><td>{esc(meta.get('file_name'))}</td></tr>
            <tr><th>File size</th><td>{esc(meta.get('file_size_kb', 'N/A'))} KB</td></tr>
            <tr><th>Text characters used</th><td>{esc(meta.get('text_characters_used'))}</td></tr>
          </table>
          <h3>Parsed paper preview</h3>
          <p>{esc(preview[:1400])}</p>
          <p><strong>Presenter line:</strong> “This first step proves we are feeding the paper into a staged workflow, not hiding the process inside one mega-prompt.”</p>
        </div>
        """
    elif stage == "extract":
        ex = trace.get("extraction", {})
        body = f"""
        <div class='stage-title'>Stage 2 — Extract Evidence</div>
        {header}<div style='height:12px'></div>{progress}
        <div class='stage-card'>
          <h3>Structured extraction record</h3>
          <table>
            <tr><th>Title</th><td>{esc(ex.get('paper_title'))}</td></tr>
            <tr><th>Author(s)</th><td>{esc(ex.get('authors'))}</td></tr>
            <tr><th>Publication year</th><td>{esc(ex.get('publication_year'))}</td></tr>
            <tr><th>Publication venue</th><td>{esc(ex.get('publication_venue'))}</td></tr>
            <tr><th>Publication period</th><td>{esc(ex.get('publication_period'))}</td></tr>
            <tr><th>DOI</th><td>{esc(ex.get('doi'))}</td></tr>
          </table>
          <p><strong>APA-style citation draft:</strong> {esc(ex.get('citation_apa'))}</p>
          <p><strong>Research objective:</strong> {esc(ex.get('research_objective'))}</p>
          <p><strong>Method / design:</strong> {esc(ex.get('method_design'))}</p>
          <p><strong>Sample / context:</strong> {esc(ex.get('sample_context'))}</p>
          <p><strong>Variables / constructs:</strong> {esc(', '.join(ex.get('variables_constructs', [])))}</p>
          <p><strong>Key finding:</strong> {esc(ex.get('key_findings'))}</p>
          <p><strong>Limits / boundaries:</strong> {esc(ex.get('limitations_or_boundaries'))}</p>
          <p><strong>What the paper does not prove:</strong> {esc(ex.get('what_the_paper_does_not_prove'))}</p>
          <p><strong>Presenter line:</strong> “This extraction sheet captures citation metadata first, then method, sample, findings, and evidence limits.”</p>
        </div>
        """
    elif stage == "classify":
        cl = trace.get("classification", {})
        body = f"""
        <div class='stage-title'>Stage 3 — Classify + Route</div>
        {header}<div style='height:12px'></div>{progress}
        <div class='stage-card'>
          <h3>Methodological classification</h3>
          <table>
            <tr><th>Tradition</th><td><strong>{esc(cl.get('methodological_tradition'))}</strong></td></tr>
            <tr><th>Confidence</th><td>{esc(cl.get('confidence'))}</td></tr>
            <tr><th>Route</th><td>{esc(cl.get('route'))}</td></tr>
            <tr><th>Evidence boundary</th><td>{esc(cl.get('evidence_boundary'))}</td></tr>
          </table>
          <h3>Guardrails loaded</h3>
          {bullet(cl.get('recommended_guardrails', []))}
          <p><strong>Presenter line:</strong> “The classifier decides which evidence rules load before generation.”</p>
        </div>
        """
    elif stage == "generate":
        outputs = trace.get("outputs", {})
        cards = ""
        for name, text in outputs.items():
            cards += f"<h3>{esc(name)}</h3><div style='border:1px solid #edf1f7;border-radius:16px;padding:16px;margin-bottom:18px;background:#fbfcff'>{text}</div>"
        body = f"""
        <div class='stage-title'>Stage 4 — Generate 1-2 Outputs</div>
        {header}<div style='height:12px'></div>{progress}
        <div class='stage-card'>
          <p><strong>Live-demo rule:</strong> only generate 1-2 representative outputs, not all 18.</p>
          {cards}
          <p><strong>Presenter line:</strong> “The output is generated from the extraction record, not from a hidden all-in-one prompt.”</p>
        </div>
        """
    elif stage == "score":
        scores = trace.get("scores", {})
        means = scores.get("dimension_means", {})
        by_output = scores.get("by_output", {})
        rows = "".join(f"<tr><td>{esc(k)}</td><td><strong>{esc(v)}</strong></td></tr>" for k, v in means.items())
        details = json_pretty(by_output)
        body = f"""
        <div class='stage-title'>Stage 5 — Score D1-D7</div>
        {header}<div style='height:12px'></div>{progress}
        <div class='stage-card'>
          <h3>Dimension means</h3>
          <table><tr><th>Dimension</th><th>Mean score</th></tr>{rows}</table>
          <p><strong>Weakest dimension:</strong> {esc(scores.get('weakest_dimension'))}</p>
          <details><summary><strong>Open detailed scores by output</strong></summary>{details}</details>
          <p><strong>Presenter line:</strong> “We are not just saying the output looks good; we score it dimension by dimension.”</p>
        </div>
        """
    else:
        rev = trace.get("review", {})
        body = f"""
        <div class='stage-title'>Stage 6 — Review / QA Fix</div>
        {header}<div style='height:12px'></div>{progress}
        <div class='stage-card'>
          <h3>QA catch</h3>
          <p>{esc(rev.get('qa_catch'))}</p>
          <h3>Issues detected</h3>
          {bullet(rev.get('issues_detected', []))}
          <h3>Targeted fixes</h3>
          {bullet(rev.get('targeted_fixes', []))}
          <p><strong>Presenter line:</strong> “This is the review step that prevents causal creep, scope collapse, and invented specificity before the output is used.”</p>
        </div>
        """

    prompt = STAGE_PROMPTS.get(stage, "")
    return body + f"<details style='margin-top:16px'><summary><strong>Optional audit: rule/prompt used for this stage</strong></summary>{json_pretty(prompt)}</details>"


def run_and_render(file_obj, pasted_text, output_types, audience):
    try:
        trace = run_workflow(file_obj, pasted_text or "", output_types or ["Technical Note"], audience or "public administration practitioners")
        return trace, render_stage(trace, "intake"), save_trace(trace)
    except Exception as exc:
        err = {"error": str(exc)}
        html = f"<div class='stage-card'><h3>Could not run workflow</h3><p>{esc(exc)}</p></div>"
        return err, html, None


def show_stage(trace, stage):
    return render_stage(trace, stage)


with gr.Blocks(title=APP_TITLE, css=CSS) as demo:
    gr.HTML(f"""
    <div class='hero'>
      <h1>FidelityBridge AI</h1>
      <p><strong>A free, staged AI Playbook workflow for Capstone live demonstration.</strong></p>
      <p>This version requires <strong>no OpenAI API key, no paid model, and no platform credit</strong>. It runs a deterministic research-translation workflow: <strong>Intake → Extract → Classify → Generate → Score → Review</strong>. Every intermediate result stays visible for the audience.</p>
    </div>
    """)

    state = gr.State(value=None)

    with gr.Row():
        with gr.Column(scale=4, elem_classes=["panel"]):
            gr.Markdown("## Paper input")
            file_in = gr.File(label="Upload paper PDF / DOCX / TXT", file_types=[".pdf", ".docx", ".txt"])
            pasted = gr.Textbox(label="Or paste paper text", placeholder="Paste abstract, methods, or full paper text here if needed...", lines=9)
            outputs = gr.CheckboxGroup(choices=OUTPUT_TYPES, value=["Technical Note", "Media Release"], label="Output types for live demo", info="Choose 1-2. The app uses only the first two selected outputs.")
            audience = gr.Textbox(value="public administration practitioners and agency managers", label="Target audience")
            run_btn = gr.Button("Run Full Workflow", elem_classes=["primary-run"])
            reset_btn = gr.Button("Reset")
            export_file = gr.File(label="Download JSON trace", interactive=False)

        with gr.Column(scale=8):
            gr.Markdown("## Six visible workflow stages")
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
