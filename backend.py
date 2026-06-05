"""Backend workflow for FidelityBridge AI.

The backend is organized around the required demo stages:
1 intake/parse -> 2 extract -> 3 classify/route -> 4 show prompt ->
5 generate -> 6 score -> 7 QA catch/fix.

It uses OpenAI or any OpenAI-compatible API when OPENAI_API_KEY is set.
If no API key is present, it falls back to a transparent rule-based demo mode so
students can still click through the interface, but real presentation use should
set an API key.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from prompts import (
    CLASSIFICATION_PROMPT,
    EXTRACTION_PROMPT,
    FAILURE_MODES,
    FIDELITY_DIMENSIONS,
    GENERATION_PROMPT,
    METHOD_TRADITIONS,
    OUTPUT_SCHEMAS,
    QA_FIX_PROMPT,
    SCORING_PROMPT,
    SYSTEM_MESSAGE,
)

MAX_CHARS_FOR_LLM = int(os.getenv("MAX_CHARS_FOR_LLM", "45000"))
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _safe_json_loads(text: str) -> Any:
    """Parse JSON from strict JSON or from text containing a JSON block."""
    if isinstance(text, (dict, list)):
        return text
    if not text:
        return {}
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, flags=re.S)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            return {"raw_text": text}
    return {"raw_text": text}


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _truncate_text(text: str, max_chars: int = MAX_CHARS_FOR_LLM) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.65)]
    tail = text[-int(max_chars * 0.25) :]
    return head + "\n\n[... middle of paper truncated for live demo speed ...]\n\n" + tail


def read_uploaded_file(file_path: Optional[str], pasted_text: str = "") -> Dict[str, Any]:
    """Parse an uploaded PDF/DOCX/TXT or directly pasted text."""
    text_parts: List[str] = []
    source_name = "pasted text"
    file_type = "text"

    if file_path:
        path = Path(file_path)
        source_name = path.name
        suffix = path.suffix.lower()
        file_type = suffix.replace(".", "") or "unknown"
        if suffix == ".pdf":
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(str(path))
                for i, page in enumerate(doc, start=1):
                    page_text = page.get_text("text") or ""
                    text_parts.append(f"\n\n--- PAGE {i} ---\n{page_text}")
            except Exception as exc:
                raise RuntimeError(
                    f"Could not parse PDF. Make sure PyMuPDF is installed. Detail: {exc}"
                ) from exc
        elif suffix in {".txt", ".md"}:
            text_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        elif suffix == ".docx":
            try:
                import docx

                document = docx.Document(str(path))
                text_parts.extend([p.text for p in document.paragraphs if p.text.strip()])
            except Exception as exc:
                raise RuntimeError(
                    f"Could not parse DOCX. Make sure python-docx is installed. Detail: {exc}"
                ) from exc
        else:
            raise ValueError("Supported file types: PDF, DOCX, TXT, MD.")

    if pasted_text and pasted_text.strip():
        text_parts.append("\n\n--- PASTED TEXT ---\n" + pasted_text.strip())

    full_text = "\n".join(text_parts).strip()
    if not full_text:
        raise ValueError("Please upload a paper or paste paper text first.")

    abstract_preview = _extract_abstract_preview(full_text)
    intake = {
        "stage": "1_intake_parse",
        "source_name": source_name,
        "file_type": file_type,
        "parsed_characters": len(full_text),
        "llm_characters_used": min(len(full_text), MAX_CHARS_FOR_LLM),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "abstract_or_front_matter_preview": abstract_preview,
        "visible_stage_note": "Paper has been ingested. Next step: extract structured facts before generating outputs.",
    }
    return {"intake": intake, "text": full_text, "llm_text": _truncate_text(full_text)}


def _extract_abstract_preview(text: str) -> str:
    lower = text.lower()
    idx = lower.find("abstract")
    if idx >= 0:
        return text[idx : idx + 1800].strip()
    return text[:1800].strip()


def _get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        base_url = os.getenv("OPENAI_BASE_URL") or None
        return OpenAI(api_key=api_key, base_url=base_url)
    except Exception:
        return None


def llm_call(prompt: str, expect_json: bool = False, temperature: float = 0.15) -> Tuple[str, str]:
    """Call OpenAI/OpenAI-compatible API. Return (content, mode)."""
    client = _get_openai_client()
    if client is None:
        return "", "fallback"

    kwargs: Dict[str, Any] = {
        "model": os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    if expect_json:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or "", "llm"
    except Exception as exc:
        # Some OpenAI-compatible providers do not support response_format.
        if expect_json and "response_format" in kwargs:
            kwargs.pop("response_format", None)
            try:
                response = client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or "", "llm"
            except Exception as exc2:
                return f"LLM call failed: {exc2}", "error"
        return f"LLM call failed: {exc}", "error"


def build_extraction_prompt(paper_text: str) -> str:
    return EXTRACTION_PROMPT.format(paper_text=_truncate_text(paper_text))


def extract_record(paper_text: str) -> Dict[str, Any]:
    prompt = build_extraction_prompt(paper_text)
    content, mode = llm_call(prompt, expect_json=True)
    if mode == "llm":
        parsed = _safe_json_loads(content)
    elif mode == "error":
        parsed = fallback_extract(paper_text)
        parsed["llm_error"] = content
    else:
        parsed = fallback_extract(paper_text)
        parsed["demo_mode_warning"] = "No OPENAI_API_KEY was found. This is a rule-based fallback, not the recommended live-demo mode."
    return {"prompt": prompt, "result": parsed, "mode": mode}


def build_classification_prompt(extraction: Dict[str, Any]) -> str:
    return CLASSIFICATION_PROMPT.format(extraction_json=_json_dumps(extraction))


def classify_paper(extraction: Dict[str, Any]) -> Dict[str, Any]:
    prompt = build_classification_prompt(extraction)
    content, mode = llm_call(prompt, expect_json=True)
    if mode == "llm":
        parsed = _safe_json_loads(content)
    elif mode == "error":
        parsed = fallback_classify(extraction)
        parsed["llm_error"] = content
    else:
        parsed = fallback_classify(extraction)
        parsed["demo_mode_warning"] = "No OPENAI_API_KEY was found. This is a rule-based fallback, not the recommended live-demo mode."
    return {"prompt": prompt, "result": parsed, "mode": mode}


def _selected_schema_text(output_types: List[str]) -> str:
    clean = [x for x in (output_types or []) if x in OUTPUT_SCHEMAS]
    if not clean:
        clean = ["Policy Brief"]
    if len(clean) > 2:
        clean = clean[:2]
    return "\n".join([f"- {name}: {OUTPUT_SCHEMAS[name]}" for name in clean])


def build_generation_prompt(
    extraction: Dict[str, Any],
    classification: Dict[str, Any],
    output_types: List[str],
    target_audience: str,
) -> str:
    return GENERATION_PROMPT.format(
        target_audience=target_audience or "public administration practitioners",
        selected_schemas=_selected_schema_text(output_types),
        classification_json=_json_dumps(classification),
        extraction_json=_json_dumps(extraction),
    )


def generate_outputs(
    extraction: Dict[str, Any],
    classification: Dict[str, Any],
    output_types: List[str],
    target_audience: str,
) -> Dict[str, Any]:
    prompt = build_generation_prompt(extraction, classification, output_types, target_audience)
    content, mode = llm_call(prompt, expect_json=False, temperature=0.25)
    if mode == "llm":
        result = content
    elif mode == "error":
        result = fallback_generate(extraction, classification, output_types, target_audience) + f"\n\n> LLM error: {content}"
    else:
        result = fallback_generate(extraction, classification, output_types, target_audience)
    return {"prompt": prompt, "result": result, "mode": mode}


def build_scoring_prompt(
    extraction: Dict[str, Any],
    classification: Dict[str, Any],
    generated_output: str,
) -> str:
    dimensions = "\n".join([f"- {k}: {v}" for k, v in FIDELITY_DIMENSIONS.items()])
    return SCORING_PROMPT.format(
        dimensions=dimensions,
        extraction_json=_json_dumps(extraction),
        classification_json=_json_dumps(classification),
        generated_output=generated_output,
    )


def score_output(
    extraction: Dict[str, Any],
    classification: Dict[str, Any],
    generated_output: str,
) -> Dict[str, Any]:
    prompt = build_scoring_prompt(extraction, classification, generated_output)
    content, mode = llm_call(prompt, expect_json=True)
    if mode == "llm":
        parsed = _safe_json_loads(content)
    elif mode == "error":
        parsed = fallback_score(extraction, classification, generated_output)
        parsed["llm_error"] = content
    else:
        parsed = fallback_score(extraction, classification, generated_output)
        parsed["demo_mode_warning"] = "No OPENAI_API_KEY was found. This is a rule-based fallback, not the recommended live-demo mode."
    return {"prompt": prompt, "result": parsed, "mode": mode}


def build_qa_prompt(
    extraction: Dict[str, Any],
    classification: Dict[str, Any],
    generated_output: str,
    scores: Dict[str, Any],
) -> str:
    return QA_FIX_PROMPT.format(
        failure_modes=_json_dumps(FAILURE_MODES),
        extraction_json=_json_dumps(extraction),
        classification_json=_json_dumps(classification),
        scores_json=_json_dumps(scores),
        generated_output=generated_output,
    )


def qa_fix(
    extraction: Dict[str, Any],
    classification: Dict[str, Any],
    generated_output: str,
    scores: Dict[str, Any],
) -> Dict[str, Any]:
    prompt = build_qa_prompt(extraction, classification, generated_output, scores)
    content, mode = llm_call(prompt, expect_json=False, temperature=0.2)
    if mode == "llm":
        result = content
    elif mode == "error":
        result = fallback_qa_fix(extraction, classification, generated_output, scores) + f"\n\n> LLM error: {content}"
    else:
        result = fallback_qa_fix(extraction, classification, generated_output, scores)
    return {"prompt": prompt, "result": result, "mode": mode}


def run_full_workflow(
    paper_text: str,
    output_types: List[str],
    target_audience: str,
) -> Dict[str, Any]:
    extraction = extract_record(paper_text)
    classification = classify_paper(extraction["result"])
    generation = generate_outputs(extraction["result"], classification["result"], output_types, target_audience)
    scoring = score_output(extraction["result"], classification["result"], generation["result"])
    qa = qa_fix(extraction["result"], classification["result"], generation["result"], scoring["result"])
    return {
        "extraction": extraction,
        "classification": classification,
        "generation": generation,
        "scoring": scoring,
        "qa": qa,
    }


def write_trace_files(state: Dict[str, Any]) -> Tuple[str, str]:
    """Write JSON trace and Markdown presenter card. Return paths."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(tempfile.gettempdir()) / "fidelitybridge_ai"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"trace_{stamp}.json"
    md_path = out_dir / f"presenter_card_{stamp}.md"
    json_path.write_text(_json_dumps(state), encoding="utf-8")
    md_path.write_text(build_presenter_card(state), encoding="utf-8")
    return str(json_path), str(md_path)


def build_presenter_card(state: Dict[str, Any]) -> str:
    extraction = state.get("extraction", {}).get("result", {})
    classification = state.get("classification", {}).get("result", {})
    scores = state.get("scoring", {}).get("result", {})
    qa = state.get("qa", {}).get("result", "")
    title = extraction.get("title") or "Uploaded paper"
    tradition = classification.get("tradition") or extraction.get("methodological_tradition_candidate") or "Unknown"
    weakest = scores.get("weakest_dimension", "TBD") if isinstance(scores, dict) else "TBD"
    return f"""# FidelityBridge AI Presenter Card

## Paper
- **Title:** {title}
- **Tradition:** {tradition}
- **Evidence boundary:** {classification.get('evidence_boundary', extraction.get('causal_language_boundary', 'TBD'))}

## Live Workflow Script
1. Intake: uploaded and parsed the paper.
2. Extract: showed method, sample/context, findings, limits, and what the paper does not prove.
3. Classify: routed it to **{tradition}** rules.
4. Prompt: showed the actual output prompt before generation.
5. Generate: produced only 1-2 outputs, not all 18.
6. Score: scored D1-D7 and identified **{weakest}** as weakest.
7. QA catch: connected the fix to a named failure mode.

## QA Catch / Fix
{qa}
"""


# -------------------------
# Rule-based fallback tools
# -------------------------


def fallback_extract(paper_text: str) -> Dict[str, Any]:
    text = paper_text or ""
    front = text[:5000]
    title = _guess_title(front)
    authors = _guess_authors(front)
    year = _guess_year(front)
    sample = _find_sample(text)
    design = _guess_design(text)
    findings = _extract_findings(text)
    limitations = _extract_limitations(text)
    tradition = _guess_tradition(text)
    return {
        "apa_citation_best_effort": f"{authors or 'Author(s)'}. ({year or 'n.d.'}). {title or 'Untitled paper'}. [Best-effort citation].",
        "title": title,
        "authors": authors,
        "year": year,
        "research_question_or_objective": _extract_objective(text),
        "public_administration_topic": _guess_topic(text),
        "data_sample_context": sample,
        "research_design": design,
        "methodological_tradition_candidate": tradition,
        "variables_or_constructs": _extract_variables(text),
        "key_findings": findings,
        "limitations_stated_or_inferred": limitations,
        "what_the_paper_does_not_prove": "This paper should not be treated as universal proof. The claim strength depends on its design, sample, and context.",
        "causal_language_boundary": _causal_boundary_from_tradition(tradition),
        "direct_evidence_quotes_short": [],
        "translation_guardrails": [
            "Generate from extracted facts only.",
            "Avoid invented quotations, agencies, dates, budgets, or local details.",
            "Use bounded causal language unless design supports causation.",
        ],
    }


def fallback_classify(extraction: Dict[str, Any]) -> Dict[str, Any]:
    tradition = extraction.get("methodological_tradition_candidate") or "Quantitative"
    if tradition not in METHOD_TRADITIONS:
        tradition = "Quantitative"
    return {
        "tradition": tradition,
        "confidence_1_to_5": 3,
        "rationale": "Rule-based classification from keywords in the abstract/methods text.",
        "evidence_boundary": _causal_boundary_from_tradition(tradition),
        "routing_rules": [
            "Keep method and sample visible.",
            "Use output-specific schema.",
            "Score D1-D7 before public use.",
        ],
        "risky_language_to_avoid": ["proves", "causes", "guarantees", "will automatically lead to"],
        "recommended_outputs_for_demo": ["Policy Brief", "Technical Note"],
    }


def fallback_generate(
    extraction: Dict[str, Any],
    classification: Dict[str, Any],
    output_types: List[str],
    target_audience: str,
) -> str:
    chosen = [x for x in (output_types or ["Policy Brief"]) if x in OUTPUT_SCHEMAS][:2]
    if not chosen:
        chosen = ["Policy Brief"]
    title = extraction.get("title") or "the uploaded paper"
    method = extraction.get("research_design") or classification.get("tradition")
    sample = extraction.get("data_sample_context") or "the study context described in the paper"
    findings = extraction.get("key_findings") or "The paper reports findings relevant to public administration practice."
    boundary = classification.get("evidence_boundary") or extraction.get("causal_language_boundary") or "Use bounded evidence language."
    blocks = []
    for name in chosen:
        blocks.append(
            f"""## {name}

**Source:** {title}

**Audience:** {target_audience or 'public administration practitioners'}

**Evidence base:** The paper uses {method} with {sample}.

**Key finding:** {findings if isinstance(findings, str) else '; '.join(map(str, findings[:3]))}

**What this does not show:** {boundary}

**Practical takeaway:** Treat the finding as decision support, not automatic proof. Use it to guide further review, pilot testing, or context-specific implementation.
"""
        )
    return "\n".join(blocks) + "\n\n> Demo mode note: no OPENAI_API_KEY was found, so this was generated by a transparent fallback template."


def fallback_score(
    extraction: Dict[str, Any],
    classification: Dict[str, Any],
    generated_output: str,
) -> Dict[str, Any]:
    text = generated_output.lower()
    causal_risk = any(w in text for w in ["prove", "proves", "cause", "causes", "guarantee", "guarantees"])
    method_visible = any(w in text for w in ["method", "survey", "experiment", "sample", "data", "review", "meta-analysis"])
    scores = {
        "D1_Claim_Accuracy": {"score": 4, "reason": "Generated from the extraction sheet, but needs human source check."},
        "D2_Causal_Precision": {"score": 2 if causal_risk else 4, "reason": "Flagged for causal wording." if causal_risk else "Causal language appears bounded."},
        "D3_Scope_Fidelity": {"score": 4, "reason": "Includes a boundary statement."},
        "D4_Method_Transparency": {"score": 4 if method_visible else 3, "reason": "Method is visible." if method_visible else "Method could be more explicit."},
        "D5_Nuance_Preservation": {"score": 3, "reason": "Needs richer caveats from the source."},
        "D6_Audience_Calibration": {"score": 4, "reason": "Tone is practitioner-oriented."},
        "D7_Actionability": {"score": 3, "reason": "Action guidance is bounded but could be more specific."},
    }
    weakest = min(scores.items(), key=lambda kv: kv[1]["score"])[0]
    return {
        "scores": scores,
        "weakest_dimension": weakest,
        "strongest_dimension": "D1_Claim_Accuracy",
        "likely_failure_modes": ["Causal upgrading"] if causal_risk else ["Actionability drift"],
        "targeted_revision_needed": "Revise the weak section only; keep claims bounded to the method and context.",
        "one_sentence_presenter_takeaway": f"The weakest dimension is {weakest}, so the fix should target that specific fidelity risk rather than rewrite the whole output.",
    }


def fallback_qa_fix(
    extraction: Dict[str, Any],
    classification: Dict[str, Any],
    generated_output: str,
    scores: Dict[str, Any],
) -> str:
    return textwrap.dedent(
        f"""
        ## 1. QA Catch
        Check whether the output uses causal or universal language that is stronger than the paper's design.

        ## 2. Failure Mode Name
        Causal upgrading / Scope collapse.

        ## 3. Why It Matters
        The presentation must show that the workflow catches fidelity risks before public-facing use.

        ## 4. Before -> After Fix
        **Before:** "This proves the policy works."  
        **After:** "This study suggests the policy may be associated with better outcomes in the studied context."

        ## 5. Revised Output Section Only
        Add this boundary sentence: "Because the evidence comes from {classification.get('tradition', 'the identified design')}, this output should guide context-specific review rather than be treated as universal proof."

        ## 6. Presenter Line
        This catch shows why our workflow separates extraction, classification, generation, scoring, and review instead of using one mega-prompt.
        """
    ).strip()


def _guess_title(front: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in front.splitlines() if line.strip()]
    ignore = {"original research", "abstract", "introduction"}
    candidates = [line for line in lines[:30] if len(line) > 15 and line.lower() not in ignore]
    return candidates[0] if candidates else "Untitled paper"


def _guess_authors(front: str) -> str:
    # Best effort: line after title often contains author names.
    lines = [re.sub(r"\s+", " ", line).strip() for line in front.splitlines() if line.strip()]
    for line in lines[:40]:
        if re.search(r"\b(and|&|,|\d)\b", line) and not re.search(r"abstract|journal|doi|university", line, re.I):
            if 5 <= len(line) <= 120:
                return line
    return ""


def _guess_year(front: str) -> str:
    match = re.search(r"\b(20\d{2}|19\d{2})\b", front)
    return match.group(1) if match else ""


def _find_sample(text: str) -> str:
    patterns = [
        r"\bN\s*=\s*[\d,]+[^\.\n]{0,120}",
        r"sample(?:s| size)?[^\.\n]{0,160}",
        r"survey of [^\.\n]{0,160}",
        r"interviews? with [^\.\n]{0,160}",
    ]
    for pat in patterns:
        match = re.search(pat, text, flags=re.I)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return "Sample/context should be verified from the paper."


def _guess_design(text: str) -> str:
    lower = text.lower()
    if "randomized" in lower or "randomised" in lower or "experiment" in lower:
        return "Experimental design or intervention study"
    if "meta-analysis" in lower or "meta analysis" in lower:
        return "Meta-analysis"
    if "systematic review" in lower:
        return "Systematic review"
    if "interview" in lower or "focus group" in lower or "ethnograph" in lower:
        return "Qualitative design"
    if "mixed methods" in lower or "mixed-method" in lower:
        return "Mixed-methods design"
    if "survey" in lower or "sem" in lower or "regression" in lower or "path analysis" in lower:
        return "Quantitative survey/statistical analysis"
    if "theoretical" in lower or "framework" in lower or "conceptual" in lower:
        return "Theoretical/conceptual paper"
    return "Design should be verified from methods section."


def _guess_tradition(text: str) -> str:
    lower = text.lower()
    if "systematic review" in lower:
        return "Systematic Review"
    if "meta-analysis" in lower or "meta analysis" in lower:
        return "Meta-analysis"
    if "randomized" in lower or "randomised" in lower or "experiment" in lower:
        return "Experimental"
    if "mixed methods" in lower or "mixed-method" in lower:
        return "Mixed Methods"
    if "interview" in lower or "focus group" in lower or "thematic analysis" in lower:
        return "Qualitative"
    if "theoretical" in lower or "conceptual framework" in lower:
        return "Theoretical"
    return "Quantitative"


def _extract_objective(text: str) -> str:
    match = re.search(r"objective(?:s)?[^\.]{0,250}\.", text, flags=re.I)
    if match:
        return re.sub(r"\s+", " ", match.group(0)).strip()
    match = re.search(r"research question[^\.]{0,250}\.", text, flags=re.I)
    if match:
        return re.sub(r"\s+", " ", match.group(0)).strip()
    return "Research objective should be verified from the abstract/introduction."


def _guess_topic(text: str) -> str:
    lower = text.lower()
    topics = [
        ("e-government / digital government", ["e-government", "digital government", "ict"]),
        ("public trust / political trust", ["trust in government", "political trust"]),
        ("public management", ["public management", "public administration"]),
        ("policy implementation", ["implementation", "policy"]),
    ]
    found = [topic for topic, keys in topics if any(k in lower for k in keys)]
    return ", ".join(found) if found else "Public administration topic to be verified."


def _extract_variables(text: str) -> List[str]:
    lower = text.lower()
    variables = []
    for term in [
        "trust in government",
        "political trust",
        "e-government",
        "satisfaction",
        "performance of government",
        "structure assurance",
        "expectation confirmation",
        "reciprocity",
        "familiarity",
    ]:
        if term in lower:
            variables.append(term)
    return variables[:10]


def _extract_findings(text: str) -> Any:
    match = re.search(r"findings? indicate[^\.]{0,500}\.", text, flags=re.I)
    if match:
        return re.sub(r"\s+", " ", match.group(0)).strip()
    match = re.search(r"results? (?:show|indicate|suggest)[^\.]{0,500}\.", text, flags=re.I)
    if match:
        return re.sub(r"\s+", " ", match.group(0)).strip()
    return "Key findings should be verified from the results/discussion section."


def _extract_limitations(text: str) -> Any:
    idx = text.lower().find("limitation")
    if idx >= 0:
        return re.sub(r"\s+", " ", text[idx : idx + 800]).strip()
    return "Limitations should be verified from the limitations/conclusion section."


def _causal_boundary_from_tradition(tradition: str) -> str:
    if tradition == "Experimental":
        return "Causal claims may be made only within the tested treatment, setting, and population."
    if tradition == "Quantitative":
        return "Use association language unless the paper clearly establishes causal identification."
    if tradition == "Qualitative":
        return "Translate as contextual insight or mechanisms, not statistical generalization."
    if tradition == "Mixed Methods":
        return "Keep quantitative and qualitative evidence strands visible; avoid flattening both into one claim type."
    if tradition == "Theoretical":
        return "Describe as a framework, argument, or conceptual contribution, not empirical proof."
    if tradition == "Meta-analysis":
        return "Translate synthesized patterns, not universal laws; preserve heterogeneity and inclusion limits."
    if tradition == "Systematic Review":
        return "Preserve search/inclusion boundaries and distinguish mapping a field from proving an effect."
    return "Use evidence-bounded language."
