from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

import gradio as gr

from backend import (
    classify_paper,
    extract_record,
    generate_outputs,
    qa_fix,
    read_uploaded_file,
    run_full_workflow,
    score_output,
    write_trace_files,
)
from prompts import OUTPUT_SCHEMAS

APP_TITLE = "FidelityBridge AI"
APP_SUBTITLE = "Six-stage AI Playbook workflow for Capstone live demonstration"

STAGE_NAMES = {
    1: "Intake / Parse",
    2: "Extract Evidence",
    3: "Classify + Route",
    4: "Generate 1-2 Outputs",
    5: "Score D1-D7",
    6: "Review + QA Fix",
}


def _ensure_state(state: Dict[str, Any] | None) -> Dict[str, Any]:
    return dict(state or {})


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _mode_badge(mode: str) -> str:
    if mode == "llm":
        return "✅ API connected — live LLM result"
    if mode == "fallback":
        return "⚠️ Fallback mode — OPENAI_API_KEY not found"
    return "⚠️ LLM error — fallback used; check Render environment variables or model name"


def _selected_outputs(output_types: List[str] | None) -> List[str]:
    clean = [x for x in (output_types or []) if x in OUTPUT_SCHEMAS]
    if not clean:
        clean = ["Policy Brief", "Technical Note"]
    return clean[:2]


def _val(obj: Dict[str, Any], key: str, default: str = "TBD") -> Any:
    value = obj.get(key, default) if isinstance(obj, dict) else default
    if value in (None, "", []):
        return default
    return value


def _short(value: Any, limit: int = 900) -> str:
    if isinstance(value, list):
        value = "; ".join(str(x) for x in value[:5])
    elif isinstance(value, dict):
        value = _json(value)
    else:
        value = str(value)
    value = value.strip()
    if len(value) > limit:
        return value[:limit].rstrip() + "..."
    return value


def _stage_header(n: int, mode: str | None = None) -> str:
    badge = f"\n\n**Mode:** {_mode_badge(mode)}" if mode else ""
    return f"## Stage {n} — {STAGE_NAMES[n]}{badge}\n"


def _paper_title(state: Dict[str, Any]) -> str:
    extraction = state.get("extraction", {}).get("result", {})
    return _short(_val(extraction, "title", "Uploaded paper"), 140)


def render_stage1(state: Dict[str, Any]) -> Tuple[str, str, str]:
    intake = state.get("intake", {})
    if not intake:
        return (
            "## Stage 1 — Intake / Parse\n\nUpload a PDF, DOCX, or TXT file, then click **1 Intake**.",
            "",
            ""
        )
    preview = _short(intake.get("abstract_or_front_matter_preview", ""), 2200)
    md = f"""{_stage_header(1)}
<div class='audience-card'>

**What happens:** The paper is uploaded and parsed. No output is generated yet.

**Source file:** `{_val(intake, 'source_name')}`  
**File type:** {_val(intake, 'file_type')}  
**Parsed text:** {_val(intake, 'parsed_characters', 0):,} characters  
**Text sent to model:** {_val(intake, 'llm_characters_used', 0):,} characters

**Presenter line:** “We start by ingesting the paper, then we separate evidence extraction from writing so the output stays traceable to the source.”

</div>
"""
    return md, preview, ""


def render_stage2(state: Dict[str, Any]) -> Tuple[str, str, str]:
    result = state.get("extraction", {})
    extraction = result.get("result", {})
    if not extraction:
        return "## Stage 2 — Extract Evidence\n\nRun **2 Extract** after intake.", "", ""
    md = f"""{_stage_header(2, result.get('mode'))}
<div class='audience-card'>

**Paper:** {_short(_val(extraction, 'title', 'Uploaded paper'), 220)}

**Research objective:** {_short(_val(extraction, 'research_question_or_objective'), 600)}

**Method / design:** {_short(_val(extraction, 'research_design'), 400)}

**Sample / context:** {_short(_val(extraction, 'data_sample_context'), 500)}

**Key finding:** {_short(_val(extraction, 'key_findings'), 650)}

**What the paper does not prove:** {_short(_val(extraction, 'what_the_paper_does_not_prove'), 550)}

**Presenter line:** “This structured record becomes the evidence boundary for every generated output.”

</div>
"""
    return md, _json(extraction), result.get("prompt", "")


def render_stage3(state: Dict[str, Any]) -> Tuple[str, str, str]:
    result = state.get("classification", {})
    classification = result.get("result", {})
    if not classification:
        return "## Stage 3 — Classify + Route\n\nRun **3 Classify** after extraction.", "", ""
    md = f"""{_stage_header(3, result.get('mode'))}
<div class='audience-card'>

**Tradition:** **{_val(classification, 'tradition')}**  
**Confidence:** {_val(classification, 'confidence_1_to_5')}/5

**Why this route:** {_short(_val(classification, 'rationale'), 700)}

**Evidence boundary:** {_short(_val(classification, 'evidence_boundary'), 650)}

**Risky language to avoid:** {_short(_val(classification, 'risky_language_to_avoid'), 500)}

**Presenter line:** “Classification decides which rules load next; for a survey or SEM paper, we use association-sensitive language instead of automatic causation.”

</div>
"""
    return md, _json(classification), result.get("prompt", "")


def render_stage4(state: Dict[str, Any]) -> Tuple[str, str, str]:
    result = state.get("generation", {})
    if not result:
        return "## Stage 4 — Generate 1-2 Outputs\n\nRun **4 Generate** after classification.", "", ""
    selected = state.get("selected_outputs", ["Policy Brief"])
    md = f"""{_stage_header(4, result.get('mode'))}
<div class='audience-card'>

**Selected live outputs:** {', '.join(selected)}  
**Important:** This stage generates only 1–2 outputs, not all 18.

**Presenter line:** “Before generation, the system uses the actual output prompt and the output-specific schema; the writing is generated from the extraction sheet, not from a vague summary request.”

</div>

---

{result.get('result', '')}
"""
    return md, result.get("result", ""), result.get("prompt", "")


def _score_table(scores: Dict[str, Any]) -> str:
    score_obj = scores.get("scores", {}) if isinstance(scores, dict) else {}
    labels = {
        "D1_Claim_Accuracy": "D1 Claim Accuracy",
        "D2_Causal_Precision": "D2 Causal Precision",
        "D3_Scope_Fidelity": "D3 Scope Fidelity",
        "D4_Method_Transparency": "D4 Method Transparency",
        "D5_Nuance_Preservation": "D5 Nuance Preservation",
        "D6_Audience_Calibration": "D6 Audience Calibration",
        "D7_Actionability": "D7 Actionability",
    }
    lines = ["| Dimension | Score | Reason |", "|---|---:|---|"]
    for key, label in labels.items():
        item = score_obj.get(key, {})
        if not isinstance(item, dict):
            item = {"score": "TBD", "reason": str(item)}
        lines.append(f"| {label} | {item.get('score', 'TBD')} | {_short(item.get('reason', 'TBD'), 260)} |")
    return "\n".join(lines)


def render_stage5(state: Dict[str, Any]) -> Tuple[str, str, str]:
    result = state.get("scoring", {})
    scores = result.get("result", {})
    if not scores:
        return "## Stage 5 — Score D1-D7\n\nRun **5 Score** after generation.", "", ""
    md = f"""{_stage_header(5, result.get('mode'))}
<div class='audience-card'>

**Weakest dimension:** **{_val(scores, 'weakest_dimension')}**  
**Strongest dimension:** **{_val(scores, 'strongest_dimension')}**

**Likely failure mode(s):** {_short(_val(scores, 'likely_failure_modes'), 500)}

**Presenter takeaway:** {_short(_val(scores, 'one_sentence_presenter_takeaway'), 700)}

</div>

{_score_table(scores)}
"""
    return md, _json(scores), result.get("prompt", "")


def render_stage6(state: Dict[str, Any]) -> Tuple[str, str, str]:
    result = state.get("qa", {})
    if not result:
        return "## Stage 6 — Review + QA Fix\n\nRun **6 Review** after scoring.", "", ""
    md = f"""{_stage_header(6, result.get('mode'))}
<div class='audience-card'>

**Goal:** show one real catch and one targeted fix. This is the review stage of the six-stage workflow.

**Presenter line:** “This catch proves the system is not just generating polished text; it audits the output against method, scope, and evidence limits.”

</div>

{result.get('result', '')}
"""
    return md, result.get("result", ""), result.get("prompt", "")


def _progress_md(state: Dict[str, Any], active: int | None = None) -> str:
    checks = {
        1: bool(state.get("intake")),
        2: bool(state.get("extraction")),
        3: bool(state.get("classification")),
        4: bool(state.get("generation")),
        5: bool(state.get("scoring")),
        6: bool(state.get("qa")),
    }
    chips = []
    for n in range(1, 7):
        cls = "active" if active == n else ("done" if checks[n] else "todo")
        icon = "✓" if checks[n] else str(n)
        chips.append(f"<span class='chip {cls}'>{icon} {STAGE_NAMES[n]}</span>")
    return "<div class='progress-wrap'>" + "".join(chips) + "</div>"


def _render_by_stage(state: Dict[str, Any], stage: int) -> Tuple[str, str, str, str]:
    if stage == 1:
        md, detail, prompt = render_stage1(state)
    elif stage == 2:
        md, detail, prompt = render_stage2(state)
    elif stage == 3:
        md, detail, prompt = render_stage3(state)
    elif stage == 4:
        md, detail, prompt = render_stage4(state)
    elif stage == 5:
        md, detail, prompt = render_stage5(state)
    else:
        md, detail, prompt = render_stage6(state)
    return _progress_md(state, active=stage), md, detail, prompt


def reset_all():
    return {}, _progress_md({}), "", "", "", None, None


def step1_intake(file_obj, pasted_text, state):
    state = _ensure_state(state)
    file_path = file_obj.name if file_obj is not None else None
    parsed = read_uploaded_file(file_path, pasted_text or "")
    state["paper_text"] = parsed["text"]
    state["llm_text"] = parsed["llm_text"]
    state["intake"] = parsed["intake"]
    # Changing the uploaded paper invalidates downstream stages.
    for key in ["extraction", "classification", "generation", "scoring", "qa"]:
        state.pop(key, None)
    return (state, *_render_by_stage(state, 1))


def step2_extract(state):
    state = _ensure_state(state)
    paper_text = state.get("paper_text")
    if not paper_text:
        raise gr.Error("Run Stage 1 Intake first.")
    if not state.get("extraction"):
        state["extraction"] = extract_record(paper_text)
        for key in ["classification", "generation", "scoring", "qa"]:
            state.pop(key, None)
    return (state, *_render_by_stage(state, 2))


def step3_classify(state):
    state = _ensure_state(state)
    extraction = state.get("extraction", {}).get("result")
    if not extraction:
        raise gr.Error("Run Stage 2 Extract first.")
    if not state.get("classification"):
        state["classification"] = classify_paper(extraction)
        for key in ["generation", "scoring", "qa"]:
            state.pop(key, None)
    return (state, *_render_by_stage(state, 3))


def step4_generate(state, output_types, target_audience):
    state = _ensure_state(state)
    extraction = state.get("extraction", {}).get("result")
    classification = state.get("classification", {}).get("result")
    if not extraction or not classification:
        raise gr.Error("Run Stage 2 Extract and Stage 3 Classify first.")
    selected = _selected_outputs(output_types)
    previous_selected = state.get("selected_outputs")
    if not state.get("generation") or previous_selected != selected:
        state["selected_outputs"] = selected
        state["generation"] = generate_outputs(extraction, classification, selected, target_audience or "public administration practitioners")
        for key in ["scoring", "qa"]:
            state.pop(key, None)
    return (state, *_render_by_stage(state, 4))


def step5_score(state):
    state = _ensure_state(state)
    extraction = state.get("extraction", {}).get("result")
    classification = state.get("classification", {}).get("result")
    generated = state.get("generation", {}).get("result")
    if not extraction or not classification or not generated:
        raise gr.Error("Run Stage 4 Generate first.")
    if not state.get("scoring"):
        state["scoring"] = score_output(extraction, classification, generated)
        state.pop("qa", None)
    return (state, *_render_by_stage(state, 5))


def step6_review(state):
    state = _ensure_state(state)
    extraction = state.get("extraction", {}).get("result")
    classification = state.get("classification", {}).get("result")
    generated = state.get("generation", {}).get("result")
    scores = state.get("scoring", {}).get("result")
    if not extraction or not classification or not generated or not scores:
        raise gr.Error("Run Stage 5 Score first.")
    if not state.get("qa"):
        state["qa"] = qa_fix(extraction, classification, generated, scores)
    return (state, *_render_by_stage(state, 6))


def full_run(file_obj, pasted_text, output_types, target_audience, state):
    state = _ensure_state(state)
    if file_obj is not None or pasted_text:
        file_path = file_obj.name if file_obj is not None else None
        parsed = read_uploaded_file(file_path, pasted_text or "")
        state["paper_text"] = parsed["text"]
        state["llm_text"] = parsed["llm_text"]
        state["intake"] = parsed["intake"]
    paper_text = state.get("paper_text")
    if not paper_text:
        raise gr.Error("Upload a file or paste paper text first.")
    selected = _selected_outputs(output_types)
    workflow = run_full_workflow(paper_text, selected, target_audience or "public administration practitioners")
    state.update(workflow)
    state["selected_outputs"] = selected
    md = f"""## Full Workflow Complete

The system has completed all six stages for **{_paper_title(state)}**.

Use the six stage buttons above to show the audience each visible step in order. The buttons will now display the stored result instead of re-running the step.

**Live outputs generated:** {', '.join(selected)}

**Recommended next presenter move:** Click **1 Intake**, then **2 Extract**, **3 Classify**, **4 Generate**, **5 Score**, and **6 Review** while narrating each stage.
"""
    return state, _progress_md(state), md, "", ""


def export_trace(state):
    state = _ensure_state(state)
    if not state:
        raise gr.Error("No trace to export yet. Run at least one stage first.")
    json_path, md_path = write_trace_files(state)
    return json_path, md_path


CSS = """
:root { --brand:#ff7a1a; --ink:#18212b; --muted:#5c6773; --line:#e6edf3; --soft:#f7fafc; --ok:#139a63; }
.gradio-container { max-width: 1420px !important; margin: auto !important; }
#title-block { border-radius: 22px; padding: 26px 30px; background: linear-gradient(135deg, #fff7ed 0%, #eef8ff 55%, #eefbf4 100%); border: 1px solid #dde9f2; box-shadow: 0 8px 28px rgba(24,33,43,.06); }
#title-block h1 { margin-bottom: 6px; letter-spacing: -.03em; }
#title-block p { color: var(--muted); }
.audience-card { background: #ffffff; border: 1px solid var(--line); border-left: 6px solid var(--brand); border-radius: 18px; padding: 18px 20px; box-shadow: 0 5px 20px rgba(24,33,43,.05); }
.progress-wrap { display:flex; flex-wrap:wrap; gap:10px; margin: 6px 0 14px; }
.chip { display:inline-flex; align-items:center; gap:6px; padding:10px 13px; border-radius:999px; font-weight:700; border:1px solid var(--line); background:#f3f6f9; color:#52606c; }
.chip.done { background:#ebfff6; color:#056b44; border-color:#bdebd5; }
.chip.active { background:#fff1e6; color:#b54800; border-color:#ffbf8a; }
.stage-btn button, button.stage-btn { border-radius: 16px !important; font-weight: 800 !important; min-height: 54px !important; }
#main-panel { min-height: 520px; }
textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important; }
footer { display:none !important; }
"""


def build_app():
    with gr.Blocks(title=APP_TITLE, css=CSS, theme=gr.themes.Soft(primary_hue="orange", neutral_hue="slate")) as demo:
        state = gr.State({})

        gr.HTML(
            f"""
<div id="title-block">
  <h1>{APP_TITLE}</h1>
  <h3>{APP_SUBTITLE}</h3>
  <p>This classroom interface follows the required six-stage workflow: <b>Intake → Extract → Classify → Generate → Score → Review</b>. Each stage button displays a presenter-ready screen, while the raw prompt is kept in an optional audit panel.</p>
</div>
"""
        )

        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=330):
                gr.Markdown("### Paper input")
                file_input = gr.File(label="Upload paper PDF / DOCX / TXT", file_types=[".pdf", ".docx", ".txt", ".md"])
                pasted_text = gr.Textbox(label="Or paste paper text", lines=7, placeholder="Paste abstract, methods, or full paper text here if needed...")
                output_types = gr.Dropdown(
                    choices=list(OUTPUT_SCHEMAS.keys()),
                    value=["Technical Note", "Media Release"],
                    multiselect=True,
                    label="Output types for live demo",
                    info="Choose 1-2. The app uses only the first two selected outputs.",
                )
                target_audience = gr.Textbox(label="Target audience", value="public administration practitioners and agency managers")
                run_all_btn = gr.Button("Run Full Workflow", variant="primary", size="lg")
                reset_btn = gr.Button("Reset", size="lg")
                export_btn = gr.Button("Export Trace", size="lg")
                with gr.Row():
                    trace_file = gr.File(label="JSON trace")
                    card_file = gr.File(label="Presenter card")

            with gr.Column(scale=2):
                gr.Markdown("### Six visible workflow stages")
                with gr.Row():
                    step1_btn = gr.Button("1 Intake", elem_classes=["stage-btn"], variant="secondary")
                    step2_btn = gr.Button("2 Extract", elem_classes=["stage-btn"], variant="secondary")
                    step3_btn = gr.Button("3 Classify", elem_classes=["stage-btn"], variant="secondary")
                with gr.Row():
                    step4_btn = gr.Button("4 Generate", elem_classes=["stage-btn"], variant="secondary")
                    step5_btn = gr.Button("5 Score D1-D7", elem_classes=["stage-btn"], variant="secondary")
                    step6_btn = gr.Button("6 Review / QA Fix", elem_classes=["stage-btn"], variant="secondary")

                progress_md = gr.HTML(_progress_md({}))
                stage_view = gr.Markdown(elem_id="main-panel")

                with gr.Accordion("Presenter details: structured record / full output", open=False):
                    detail_box = gr.Textbox(label="Structured stage detail", lines=18, show_copy_button=True)
                with gr.Accordion("Optional audit: actual prompt used for this stage", open=False):
                    prompt_box = gr.Textbox(label="Prompt text", lines=16, show_copy_button=True)

        gr.Markdown(
            """
### Presenter reminder
Run only **1–2 outputs** live. Use the six buttons to make the intermediate steps visible. If you see “LLM error — fallback used,” check the Render environment variables and redeploy.
"""
        )

        outputs = [state, progress_md, stage_view, detail_box, prompt_box]
        step1_btn.click(step1_intake, inputs=[file_input, pasted_text, state], outputs=outputs)
        step2_btn.click(step2_extract, inputs=[state], outputs=outputs)
        step3_btn.click(step3_classify, inputs=[state], outputs=outputs)
        step4_btn.click(step4_generate, inputs=[state, output_types, target_audience], outputs=outputs)
        step5_btn.click(step5_score, inputs=[state], outputs=outputs)
        step6_btn.click(step6_review, inputs=[state], outputs=outputs)
        run_all_btn.click(full_run, inputs=[file_input, pasted_text, output_types, target_audience, state], outputs=outputs)
        export_btn.click(export_trace, inputs=[state], outputs=[trace_file, card_file])
        reset_btn.click(reset_all, inputs=[], outputs=[state, progress_md, stage_view, detail_box, prompt_box, trace_file, card_file])
    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
        show_error=True,
    )
