from __future__ import annotations

import json
from typing import Any, Dict, List

import gradio as gr

from backend import (
    build_generation_prompt,
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
APP_SUBTITLE = "A staged AI Playbook workflow for Capstone live demonstration"


def _ensure_state(state: Dict[str, Any] | None) -> Dict[str, Any]:
    return dict(state or {})


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _mode_badge(mode: str) -> str:
    if mode == "llm":
        return "✅ LLM mode: API connected"
    if mode == "fallback":
        return "⚠️ Fallback mode: no OPENAI_API_KEY found"
    return "⚠️ LLM error: fallback used"


def _selected_outputs(output_types: List[str] | None) -> List[str]:
    clean = [x for x in (output_types or []) if x in OUTPUT_SCHEMAS]
    if not clean:
        clean = ["Policy Brief", "Technical Note"]
    if len(clean) > 2:
        clean = clean[:2]
    return clean


def reset_all():
    return (
        {},
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        None,
        None,
    )


def step1_intake(file_obj, pasted_text, state):
    state = _ensure_state(state)
    file_path = file_obj.name if file_obj is not None else None
    parsed = read_uploaded_file(file_path, pasted_text or "")
    state["paper_text"] = parsed["text"]
    state["llm_text"] = parsed["llm_text"]
    state["intake"] = parsed["intake"]
    intake_md = f"""## Stage 1 — Intake / Parse

**Source:** {parsed['intake']['source_name']}  
**Parsed characters:** {parsed['intake']['parsed_characters']:,}  
**Characters sent to LLM:** {parsed['intake']['llm_characters_used']:,}  

**What the audience should see:** the paper is uploaded, parsed, and ready for extraction. We do not generate outputs yet.
"""
    preview = parsed["text"][:7000]
    return state, intake_md, preview


def step2_extract(state):
    state = _ensure_state(state)
    paper_text = state.get("paper_text")
    if not paper_text:
        raise gr.Error("Run Stage 1 intake first.")
    result = extract_record(paper_text)
    state["extraction"] = result
    prompt = result["prompt"]
    out = f"{_mode_badge(result['mode'])}\n\n" + _json(result["result"])
    return state, prompt, out


def step3_classify(state):
    state = _ensure_state(state)
    extraction = state.get("extraction", {}).get("result")
    if not extraction:
        raise gr.Error("Run Stage 2 extraction first.")
    result = classify_paper(extraction)
    state["classification"] = result
    prompt = result["prompt"]
    out = f"{_mode_badge(result['mode'])}\n\n" + _json(result["result"])
    return state, prompt, out


def step4_show_prompt(state, output_types, target_audience):
    state = _ensure_state(state)
    extraction = state.get("extraction", {}).get("result")
    classification = state.get("classification", {}).get("result")
    if not extraction or not classification:
        raise gr.Error("Run Stage 2 extraction and Stage 3 classification first.")
    selected = _selected_outputs(output_types)
    prompt = build_generation_prompt(extraction, classification, selected, target_audience or "public administration practitioners")
    state["stage4_generation_prompt_preview"] = prompt
    out = f"## Stage 4 — Show the Actual Prompt\n\nSelected outputs: **{', '.join(selected)}**\n\nThis is the real prompt that will fire in Stage 5. Show this on screen before clicking Generate."
    return state, prompt, out


def step5_generate(state, output_types, target_audience):
    state = _ensure_state(state)
    extraction = state.get("extraction", {}).get("result")
    classification = state.get("classification", {}).get("result")
    if not extraction or not classification:
        raise gr.Error("Run Stage 2 extraction and Stage 3 classification first.")
    selected = _selected_outputs(output_types)
    result = generate_outputs(extraction, classification, selected, target_audience or "public administration practitioners")
    state["generation"] = result
    return state, result["prompt"], f"{_mode_badge(result['mode'])}\n\n{result['result']}"


def step6_score(state):
    state = _ensure_state(state)
    extraction = state.get("extraction", {}).get("result")
    classification = state.get("classification", {}).get("result")
    generated = state.get("generation", {}).get("result")
    if not extraction or not classification or not generated:
        raise gr.Error("Run through Stage 5 generation first.")
    result = score_output(extraction, classification, generated)
    state["scoring"] = result
    return state, result["prompt"], f"{_mode_badge(result['mode'])}\n\n" + _json(result["result"])


def step7_qa(state):
    state = _ensure_state(state)
    extraction = state.get("extraction", {}).get("result")
    classification = state.get("classification", {}).get("result")
    generated = state.get("generation", {}).get("result")
    scores = state.get("scoring", {}).get("result")
    if not extraction or not classification or not generated or not scores:
        raise gr.Error("Run through Stage 6 scoring first.")
    result = qa_fix(extraction, classification, generated, scores)
    state["qa"] = result
    return state, result["prompt"], f"{_mode_badge(result['mode'])}\n\n{result['result']}"


def full_run(file_obj, pasted_text, output_types, target_audience, state):
    state = _ensure_state(state)
    # If no intake exists, parse now.
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

    intake = state.get("intake", {})
    intake_md = f"""## Stage 1 — Intake / Parse

**Source:** {intake.get('source_name', 'uploaded paper')}  
**Parsed characters:** {intake.get('parsed_characters', 0):,}  
**Characters sent to LLM:** {intake.get('llm_characters_used', 0):,}
"""
    prompt = workflow["qa"]["prompt"]
    extraction_out = f"{_mode_badge(workflow['extraction']['mode'])}\n\n" + _json(workflow["extraction"]["result"])
    classification_out = f"{_mode_badge(workflow['classification']['mode'])}\n\n" + _json(workflow["classification"]["result"])
    gen_out = f"{_mode_badge(workflow['generation']['mode'])}\n\n" + workflow["generation"]["result"]
    score_out = f"{_mode_badge(workflow['scoring']['mode'])}\n\n" + _json(workflow["scoring"]["result"])
    qa_out = f"{_mode_badge(workflow['qa']['mode'])}\n\n" + workflow["qa"]["result"]
    return state, intake_md, state["paper_text"][:7000], prompt, extraction_out, classification_out, gen_out, score_out, qa_out


def export_trace(state):
    state = _ensure_state(state)
    if not state:
        raise gr.Error("No trace to export yet. Run at least one stage first.")
    json_path, md_path = write_trace_files(state)
    return json_path, md_path


CSS = """
#title-block {border-radius: 18px; padding: 20px; background: linear-gradient(90deg, #f7fbff, #eef7f2); border: 1px solid #d8e6e2;}
.stage-note {font-size: 0.95rem; color: #41505a;}
textarea {font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;}
"""


def build_app():
    with gr.Blocks(title=APP_TITLE, css=CSS) as demo:
        state = gr.State({})

        gr.Markdown(
            f"""
<div id="title-block">

# {APP_TITLE}

**{APP_SUBTITLE}**

This interface is designed for the Capstone requirement: one visible staged workflow, not one mega-prompt. Upload the instructor's out-of-sample paper, then run **Intake → Extract → Classify → Show Prompt → Generate → Score → QA Fix**. Every intermediate record stays visible for the audience.

</div>
"""
        )

        with gr.Row():
            with gr.Column(scale=1):
                file_input = gr.File(label="Upload paper PDF / DOCX / TXT", file_types=[".pdf", ".docx", ".txt", ".md"])
                pasted_text = gr.Textbox(label="Or paste paper text", lines=8, placeholder="Paste abstract, methods, or full paper text here if needed...")
                output_types = gr.Dropdown(
                    choices=list(OUTPUT_SCHEMAS.keys()),
                    value=["Policy Brief", "Technical Note"],
                    multiselect=True,
                    label="Output types for live demo (choose 1-2)",
                    info="The app will only use the first two selected outputs, as required for live demo.",
                )
                target_audience = gr.Textbox(
                    label="Target audience",
                    value="public administration practitioners and agency managers",
                )
                with gr.Row():
                    run_all_btn = gr.Button("Run Full Workflow", variant="primary")
                    reset_btn = gr.Button("Reset")
                with gr.Row():
                    export_btn = gr.Button("Export Trace")
                trace_file = gr.File(label="Download JSON trace")
                card_file = gr.File(label="Download presenter card")

            with gr.Column(scale=2):
                gr.Markdown("### Live Demo Stages")
                with gr.Row():
                    step1_btn = gr.Button("1 Intake")
                    step2_btn = gr.Button("2 Extract")
                    step3_btn = gr.Button("3 Classify")
                    step4_btn = gr.Button("4 Show Prompt")
                with gr.Row():
                    step5_btn = gr.Button("5 Generate")
                    step6_btn = gr.Button("6 Score D1-D7")
                    step7_btn = gr.Button("7 QA Fix")

                with gr.Tab("Stage 1 Intake"):
                    intake_md = gr.Markdown()
                    paper_preview = gr.Textbox(label="Parsed paper preview", lines=16)
                with gr.Tab("Visible Prompt"):
                    prompt_box = gr.Textbox(label="Actual prompt shown to audience", lines=22)
                with gr.Tab("Stage 2 Extraction JSON"):
                    extraction_box = gr.Textbox(label="Structured extraction record", lines=24)
                with gr.Tab("Stage 3 Classification + Route"):
                    classification_box = gr.Textbox(label="Methodological tradition and routing rules", lines=18)
                with gr.Tab("Stage 5 Generated Outputs"):
                    generated_md = gr.Markdown()
                with gr.Tab("Stage 6 D1-D7 Scores"):
                    score_box = gr.Textbox(label="Fidelity scores", lines=24)
                with gr.Tab("Stage 7 QA Catch + Fix"):
                    qa_md = gr.Markdown()

        gr.Markdown(
            """
### Presenter reminder
- For prepared trace: upload your prepared paper and click stages one by one so the class sees the workflow.
- For out-of-sample: upload the instructor's paper, predict the tradition aloud, then run the same stages.
- Do **not** generate all 18 outputs live; generate only 1-2 and score them on D1-D7.
- Keep the trace export as backup evidence.
"""
        )

        step1_btn.click(step1_intake, inputs=[file_input, pasted_text, state], outputs=[state, intake_md, paper_preview])
        step2_btn.click(step2_extract, inputs=[state], outputs=[state, prompt_box, extraction_box])
        step3_btn.click(step3_classify, inputs=[state], outputs=[state, prompt_box, classification_box])
        step4_btn.click(step4_show_prompt, inputs=[state, output_types, target_audience], outputs=[state, prompt_box, generated_md])
        step5_btn.click(step5_generate, inputs=[state, output_types, target_audience], outputs=[state, prompt_box, generated_md])
        step6_btn.click(step6_score, inputs=[state], outputs=[state, prompt_box, score_box])
        step7_btn.click(step7_qa, inputs=[state], outputs=[state, prompt_box, qa_md])
        run_all_btn.click(
            full_run,
            inputs=[file_input, pasted_text, output_types, target_audience, state],
            outputs=[state, intake_md, paper_preview, prompt_box, extraction_box, classification_box, generated_md, score_box, qa_md],
        )
        export_btn.click(export_trace, inputs=[state], outputs=[trace_file, card_file])
        reset_btn.click(
            reset_all,
            inputs=[],
            outputs=[state, intake_md, paper_preview, prompt_box, extraction_box, classification_box, generated_md, score_box, qa_md, trace_file, card_file],
        )
    return demo


if __name__ == "__main__":
    import os

    app = build_app()
    # Render provides the PORT environment variable. Binding to 0.0.0.0 is
    # required so Render can route external traffic to the Gradio server.
    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
        show_error=True,
    )
