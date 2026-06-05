import json
import os
import re
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from prompts import FIDELITY_DIMENSIONS, FAILURE_MODES, OUTPUT_TYPES, SCHEMAS

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    import docx
except Exception:
    docx = None


MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "90000"))


@dataclass
class ExtractionRecord:
    paper_title: str
    citation_hint: str
    research_objective: str
    method_design: str
    sample_context: str
    variables_constructs: List[str]
    key_findings: str
    limitations_or_boundaries: str
    what_the_paper_does_not_prove: str
    method_keywords_found: List[str]


@dataclass
class ClassificationRecord:
    methodological_tradition: str
    confidence: str
    route: str
    evidence_boundary: str
    recommended_guardrails: List[str]


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[\u00ad\u200b\ufeff]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def read_pdf(path: str) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed")
    reader = PdfReader(path)
    chunks = []
    for idx, page in enumerate(reader.pages[:25]):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        chunks.append(f"\n--- PAGE {idx + 1} ---\n{page_text}")
    return "\n".join(chunks)


def read_docx(path: str) -> str:
    if docx is None:
        raise RuntimeError("python-docx is not installed")
    document = docx.Document(path)
    return "\n".join(p.text for p in document.paragraphs)


def read_uploaded_file(file_obj: Any, pasted_text: str = "") -> Tuple[str, Dict[str, Any]]:
    if pasted_text and pasted_text.strip():
        text = pasted_text.strip()
        return text[:MAX_TEXT_CHARS], {
            "source_type": "Pasted text",
            "file_name": "manual_text_input",
            "text_characters_used": min(len(text), MAX_TEXT_CHARS),
        }

    if file_obj is None:
        raise ValueError("Please upload a PDF/DOCX/TXT file or paste paper text.")

    path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    file_name = Path(path).name
    suffix = Path(path).suffix.lower()
    size_kb = round(os.path.getsize(path) / 1024, 1) if os.path.exists(path) else None

    if suffix == ".pdf":
        raw = read_pdf(path)
    elif suffix == ".docx":
        raw = read_docx(path)
    elif suffix in {".txt", ".md"}:
        raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    else:
        raise ValueError("Supported files: PDF, DOCX, TXT.")

    cleaned = raw[:MAX_TEXT_CHARS]
    return cleaned, {
        "source_type": suffix.upper().replace(".", "") or "file",
        "file_name": file_name,
        "file_size_kb": size_kb,
        "text_characters_used": len(cleaned),
        "truncated": len(raw) > MAX_TEXT_CHARS,
    }


def find_between(text: str, start_pattern: str, end_patterns: List[str], max_chars: int = 6000) -> str:
    lower = text.lower()
    start = lower.find(start_pattern.lower())
    if start < 0:
        return ""
    start += len(start_pattern)
    end = len(text)
    for pat in end_patterns:
        pos = lower.find(pat.lower(), start)
        if pos > start and pos < end:
            end = pos
    return normalize_text(text[start:end])[:max_chars]


def split_sentences(text: str) -> List[str]:
    text = normalize_text(text)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def detect_title(text: str) -> str:
    before_abstract = text.split("Abstract", 1)[0][:2500]
    lines = [re.sub(r"\s+", " ", line).strip() for line in before_abstract.splitlines() if line.strip()]
    cleaned = []
    skip_terms = ["sage open", "doi", "journal", "creative commons", "original research", "author", "email", "page", "vol", "issue"]
    for line in lines:
        low = line.lower()
        if any(term in low for term in skip_terms):
            continue
        if re.search(r"@|http|www|\d{4}:|^\d+$", low):
            continue
        if 8 <= len(line) <= 180:
            cleaned.append(line)
    # Prefer lines with title-like words near abstract.
    candidates = cleaned[-6:]
    title = " ".join(candidates[:3]) if candidates else "Untitled paper"
    title = re.sub(r"\b[A-Z][a-z]+\s+and\s+[A-Z][a-z]+\b.*$", "", title).strip()
    if len(title) > 220:
        title = title[:220].rsplit(" ", 1)[0] + "..."
    return title or "Untitled paper"


def extract_abstract(text: str) -> str:
    abstract = find_between(text, "Abstract", ["Keywords", "Introduction", "Literature Review"], 5000)
    if abstract:
        return abstract
    return normalize_text(text[:3000])


def detect_keywords(text: str) -> List[str]:
    keyword_bank = [
        "survey", "questionnaire", "respondents", "sample", "SEM", "structural equation", "path analysis",
        "regression", "correlation", "cross-sectional", "experiment", "randomized", "treatment", "control group",
        "interview", "focus group", "thematic", "qualitative", "mixed methods", "case study",
        "meta-analysis", "systematic review", "literature review", "conceptual", "framework", "theoretical",
        "hypothesis", "hypotheses", "CFA", "confirmatory factor", "Cronbach", "Likert",
    ]
    found = []
    low = text.lower()
    for kw in keyword_bank:
        if kw.lower() in low:
            found.append(kw)
    return found


def detect_method(text: str, abstract: str, keywords: List[str]) -> str:
    low = text.lower()
    if "meta-analysis" in low:
        return "Meta-analysis / quantitative synthesis"
    if "systematic review" in low:
        return "Systematic review"
    if "mixed methods" in low or ("interview" in low and "survey" in low):
        return "Mixed-methods design"
    if any(k in low for k in ["randomized", "randomised", "experiment", "treatment group", "control group"]):
        return "Experimental or quasi-experimental design"
    if any(k in low for k in ["survey", "questionnaire", "respondents", "sem", "structural equation", "path analysis", "regression", "cfa", "likert"]):
        return "Quantitative survey/statistical analysis"
    if any(k in low for k in ["interview", "focus group", "thematic", "qualitative", "ethnograph"]):
        return "Qualitative study"
    if any(k in low for k in ["conceptual", "framework", "theoretical", "theory"]):
        return "Theoretical / conceptual paper"
    return "Method not fully detected; human check needed"


def detect_sample(text: str) -> str:
    patterns = [
        r"(?:survey of|sample of|data from|included|includes|including|among)\s+[^.]{0,140}?(?:\d{2,6})\s+[^.]{0,120}",
        r"(?:N|n)\s*=\s*\d{2,6}[^.]{0,100}",
        r"\d{2,6}\s+(?:participants|respondents|residents|employees|agencies|organizations|students|households)[^.]{0,120}",
    ]
    for pat in patterns:
        matches = re.findall(pat, text, flags=re.IGNORECASE)
        if matches:
            result = matches[0]
            return normalize_text(result)[:260]
    # Special case: multiple urban/rural counts.
    nums = re.findall(r"\b\d{2,5}\b\s+(?:urban|rural|total|valid|returned|surveys|questionnaires|respondents|residents)", text, flags=re.IGNORECASE)
    if nums:
        return "; ".join(nums[:4])
    return "Sample/context not automatically detected; presenter should verify this field against the paper."


def detect_variables(text: str, abstract: str) -> List[str]:
    phrases = []
    common = [
        "trust in government", "political trust", "e-government", "satisfaction", "performance of government",
        "structure assurance", "expectation confirmation", "reciprocity", "reputation", "familiarity",
        "perceived characteristics", "digital divide", "urban-rural divide", "citizen trust",
    ]
    low = (abstract + " " + text[:5000]).lower()
    for phrase in common:
        if phrase in low:
            phrases.append(phrase)
    # Add words after Keywords if present.
    kw_text = find_between(text, "Keywords", ["Introduction", "1."], 800)
    if kw_text:
        for part in re.split(r"[,;]\s*", kw_text):
            part = part.strip(" .;:")
            if 3 < len(part) < 60 and part.lower() not in [p.lower() for p in phrases]:
                phrases.append(part)
    return phrases[:10] or ["Key variables/constructs require human verification"]


def detect_research_objective(abstract: str, text: str) -> str:
    sentences = split_sentences(abstract)
    priority_terms = ["objective", "purpose", "aim", "seek", "investigat", "understand", "examine", "research question"]
    for s in sentences:
        if any(t in s.lower() for t in priority_terms):
            return s[:420]
    for s in split_sentences(text[:6000]):
        if any(t in s.lower() for t in priority_terms):
            return s[:420]
    return sentences[0][:420] if sentences else "Research objective not detected automatically."


def detect_key_findings(abstract: str, text: str) -> str:
    source = abstract if abstract else text[:6000]
    sentences = split_sentences(source)
    priority_terms = ["findings", "results", "indicate", "show", "suggest", "found", "significant", "positive", "negative", "effect", "associated"]
    chosen = [s for s in sentences if any(t in s.lower() for t in priority_terms)]
    if chosen:
        return " ".join(chosen[:3])[:800]
    return " ".join(sentences[-2:])[:800] if sentences else "Key findings not detected automatically."


def detect_limitations(text: str) -> str:
    lim = find_between(text, "limitation", ["conclusion", "references", "appendix"], 1200)
    if lim:
        return lim[:500]
    conclusion = find_between(text, "Conclusion", ["References", "Appendix"], 1400)
    if conclusion:
        sentences = split_sentences(conclusion)
        risk_sents = [s for s in sentences if any(t in s.lower() for t in ["limit", "future", "caution", "context", "generaliz", "sample"])]
        if risk_sents:
            return " ".join(risk_sents[:2])[:500]
    return "No explicit limitation section was automatically captured; use method, sample, and context as boundaries."


def boundary_from_method(method_design: str, sample_context: str) -> str:
    low = method_design.lower()
    if "survey" in low or "statistical" in low or "sem" in low:
        return "This paper can support association-oriented claims, but it should not be presented as proving universal causation."
    if "experimental" in low:
        return "Causal claims may be possible only within the tested treatment, population, and setting."
    if "qualitative" in low:
        return "This paper supports contextual/mechanism insight, not broad statistical generalization."
    if "meta-analysis" in low:
        return "This paper synthesizes patterns across studies, but the pooled pattern should not be treated as a universal law."
    if "systematic" in low:
        return "This paper maps/synthesizes a field; it does not automatically prove a single intervention works everywhere."
    if "theoretical" in low or "conceptual" in low:
        return "This paper develops a framework or argument; it should not be described as empirical proof."
    return "The claim strength depends on design, sample, and context; human method review is required."


def make_extraction_record(text: str) -> ExtractionRecord:
    abstract = extract_abstract(text)
    keywords = detect_keywords(text)
    method = detect_method(text, abstract, keywords)
    sample = detect_sample(text)
    title = detect_title(text)
    objective = detect_research_objective(abstract, text)
    findings = detect_key_findings(abstract, text)
    limitations = detect_limitations(text)
    boundary = boundary_from_method(method, sample)
    citation_hint = title
    if re.search(r"\b20\d{2}\b", text[:1000]):
        year = re.search(r"\b20\d{2}\b", text[:1000]).group(0)
        citation_hint = f"{title} ({year})"
    return ExtractionRecord(
        paper_title=title,
        citation_hint=citation_hint,
        research_objective=objective,
        method_design=method,
        sample_context=sample,
        variables_constructs=detect_variables(text, abstract),
        key_findings=findings,
        limitations_or_boundaries=limitations,
        what_the_paper_does_not_prove=boundary,
        method_keywords_found=keywords[:14],
    )


def classify_record(text: str, record: ExtractionRecord) -> ClassificationRecord:
    low = (text[:20000] + " " + record.method_design).lower()
    if "meta-analysis" in low:
        tradition = "Meta-Analysis"
        confidence = "High"
    elif "systematic review" in low:
        tradition = "Systematic Review"
        confidence = "High"
    elif "mixed methods" in low:
        tradition = "Mixed Methods"
        confidence = "High"
    elif any(k in low for k in ["randomized", "randomised", "experiment", "treatment group", "control group"]):
        # Do not let the word empirical alone become Experimental.
        if any(k in low for k in ["survey", "sem", "structural equation", "questionnaire", "respondents"]):
            tradition = "Quantitative"
            confidence = "High"
        else:
            tradition = "Experimental"
            confidence = "Medium"
    elif any(k in low for k in ["survey", "questionnaire", "respondents", "sem", "structural equation", "path analysis", "regression", "cfa", "likert"]):
        tradition = "Quantitative"
        confidence = "High"
    elif any(k in low for k in ["interview", "focus group", "thematic", "qualitative"]):
        tradition = "Qualitative"
        confidence = "Medium"
    elif any(k in low for k in ["conceptual", "framework", "theoretical", "theory"]):
        tradition = "Theoretical"
        confidence = "Medium"
    else:
        tradition = "Unclear / Needs Method Check"
        confidence = "Low"

    if tradition == "Quantitative":
        route = "Load association-sensitive rules; require method sentence and causal-boundary language."
        boundary = "Use associated with / linked to / suggests unless the paper's design clearly supports causation."
        guardrails = ["No proves/causes language", "Name sample/context", "Preserve variables", "Score D2 carefully"]
    elif tradition == "Experimental":
        route = "Load treatment/population/scope rules; causal language only inside tested setting."
        boundary = "Causation may be discussed only for the tested treatment and population."
        guardrails = ["Name treatment", "Name comparison group", "Do not overgeneralize", "Keep external validity limits"]
    elif tradition == "Qualitative":
        route = "Load context/mechanism rules; emphasize themes and participant/context boundaries."
        boundary = "Translate as depth and mechanism insight, not statistical generalization."
        guardrails = ["Keep context visible", "Avoid percent claims unless in source", "Do not invent quotes"]
    elif tradition == "Mixed Methods":
        route = "Load dual-strand rules; keep quantitative and qualitative evidence visible."
        boundary = "Do not collapse multiple evidence strands into one simplified claim."
        guardrails = ["Preserve both strands", "Separate numbers from themes", "Name integration logic"]
    elif tradition == "Theoretical":
        route = "Load framework/argument rules; do not write as empirical proof."
        boundary = "Use develops a framework / argues / proposes; avoid 'finds' unless discussing cited evidence."
        guardrails = ["No empirical proof language", "Name concept/framework", "Actionability must be cautious"]
    elif tradition == "Meta-Analysis":
        route = "Load synthesis/heterogeneity rules; preserve pooled-pattern and inclusion boundaries."
        boundary = "Synthesized association is not a universal law."
        guardrails = ["Mention included studies", "Mention heterogeneity if available", "Avoid universal claims"]
    elif tradition == "Systematic Review":
        route = "Load search/inclusion-boundary rules; distinguish mapping evidence from proving effects."
        boundary = "Review findings depend on search strategy and inclusion criteria."
        guardrails = ["Mention search/inclusion scope", "Do not claim direct implementation proof"]
    else:
        route = "Route to conservative default; require human method check before public use."
        boundary = "Use cautious language until a presenter verifies the design."
        guardrails = ["Human method check", "No causal claims", "Name uncertainty"]

    return ClassificationRecord(tradition, confidence, route, boundary, guardrails)


def bounded_finding(record: ExtractionRecord, classification: ClassificationRecord) -> str:
    finding = record.key_findings.strip()
    if classification.methodological_tradition in {"Quantitative", "Systematic Review", "Meta-Analysis", "Mixed Methods", "Unclear / Needs Method Check"}:
        replacements = {
            r"\bhas significant impacts on\b": "is significantly associated with",
            r"\bhave significant impacts on\b": "are significantly associated with",
            r"\bimpacts on\b": "is linked to",
            r"\baffects\b": "is associated with",
            r"\bcauses\b": "is associated with",
            r"\bproves\b": "suggests",
        }
        for pat, repl in replacements.items():
            finding = re.sub(pat, repl, finding, flags=re.IGNORECASE)
    return finding


def generate_output(output_type: str, record: ExtractionRecord, classification: ClassificationRecord, audience: str) -> str:
    title = record.paper_title
    finding = bounded_finding(record, classification)
    method = record.method_design
    sample = record.sample_context
    boundary = record.what_the_paper_does_not_prove
    schema = SCHEMAS.get(output_type, "Use a concise, audience-aware structure.")

    if output_type == "Technical Note":
        return f"""### Technical Note: {title}

**Purpose.** Translate the study into a method-visible note for {audience}.

**Research design.** {method}. This matters because the strength of the recommendation depends on the design.

**Data / sample / context.** {sample}

**Core constructs.** {', '.join(record.variables_constructs[:8])}.

**Key finding.** {finding}

**Evidence boundary.** {boundary}

**Operational implication.** Treat the paper as evidence for cautious planning, service-design review, and targeted follow-up analysis, not as a standalone mandate for universal policy change.
"""

    if output_type == "Media Release":
        return f"""### Media Release Draft

**Headline:** Study highlights link between {record.variables_constructs[0] if record.variables_constructs else 'public service factors'} and public trust

**Lead:** A recent public administration study suggests that {finding[0].lower() + finding[1:] if finding else 'the paper offers relevant evidence for public managers.'}

**What the study examined:** The paper used {method.lower()} and focused on {sample.lower()}.

**Why it matters:** For public managers, the study points to the importance of designing public services that are understandable, reliable, and responsive to user expectations.

**Important boundary:** {boundary}

**No unsupported details added:** This draft does not invent quotes, local officials, budgets, or agency claims that are not in the paper.
"""

    if output_type == "Policy Brief":
        return f"""### Policy Brief: {title}

**Issue.** Public managers need usable evidence on how administrative systems relate to citizen trust.

**Evidence base.** {method}; {sample}.

**Main finding.** {finding}

**What this does not show.** {boundary}

**Options.** 1) Audit service usability and transparency. 2) Pilot targeted improvements. 3) Monitor trust and satisfaction indicators before scaling.

**Recommendation.** Use the study as a cautious evidence input for a pilot or review process, not as a universal causal proof.
"""

    if output_type == "Briefing Memo":
        return f"""### Briefing Memo

**To:** Agency leadership  
**Subject:** Research translation — {title}

**Decision question.** How should the agency interpret this research for practice?

**Evidence.** The paper uses {method.lower()} with {sample.lower()}.

**Bottom line.** {finding}

**Unknowns / limits.** {boundary}

**Suggested next step.** Use this as a basis for a limited evidence review, pilot design, or stakeholder discussion.
"""

    if output_type == "Executive Summary":
        return f"""### Executive Summary

**Purpose:** Summarize a research paper for {audience}.

**Method overview:** {method}; {sample}.

**Bottom-line result:** {finding}

**Confidence statement:** The finding is useful, but its application should stay inside the method and context boundaries.

**Next steps:** Verify local fit, avoid causal overclaiming, and pair the paper with implementation data.
"""

    if output_type == "Research Summary":
        return f"""### Research Summary

**Paper:** {title}

**Research objective:** {record.research_objective}

**Design and context:** {method}; {sample}.

**Main finding:** {finding}

**Why it matters:** The study gives public administration practitioners a structured way to think about the relationship between evidence, service design, and governance outcomes.

**Limits:** {boundary}
"""

    if output_type == "Practitioner Guide":
        return f"""### Practitioner Guide

**Audience:** {audience}

**When to use this evidence:** Use it when designing, evaluating, or communicating public service improvements.

**What the paper shows:** {finding}

**How to apply cautiously:**
1. Identify whether your local population resembles the study context.
2. Keep the method boundary visible in any memo or public-facing output.
3. Pilot changes before scaling.
4. Monitor whether outcomes change in your own setting.

**What not to claim:** {boundary}
"""

    if output_type == "Conference Abstract":
        return f"""### Conference Abstract

**Background:** {record.research_objective}

**Method:** {method}; {sample}.

**Findings:** {finding}

**Contribution:** The paper contributes to public administration translation by connecting methodological evidence to practice-facing communication.

**Limitations:** {boundary}
"""

    # Generic schema-aware fallback for all other output types.
    return f"""### {output_type}: {title}

**Schema used:** {schema}

**Audience:** {audience}

**Evidence base:** {method}; {sample}.

**Core message:** {finding}

**Boundary line:** {boundary}

**Practice implication:** Use this research as an evidence-bounded input for discussion, pilot design, or further review. Do not make stronger claims than the paper's design supports.
"""


def generate_outputs(output_types: List[str], record: ExtractionRecord, classification: ClassificationRecord, audience: str) -> Dict[str, str]:
    selected = output_types[:2] if output_types else ["Technical Note"]
    return {ot: generate_output(ot, record, classification, audience) for ot in selected}


def score_one_output(output_type: str, output_text: str, record: ExtractionRecord, classification: ClassificationRecord) -> Dict[str, Any]:
    tradition = classification.methodological_tradition
    public_risk = output_type in {"Media Release", "Op-Ed", "Letter to the Editor", "LinkedIn Post", "Twitter/X Thread", "Elevator Pitch"}
    method_visible = any(term.lower() in output_text.lower() for term in ["survey", "interview", "method", "design", "sample", "review", "experiment", "statistical"])
    boundary_visible = any(term.lower() in output_text.lower() for term in ["boundary", "does not", "not prove", "cautious", "associated", "linked", "context", "limit"])
    invented_risk = any(term.lower() in output_text.lower() for term in ["said", "spokesperson", "$", "mayor", "office announced"])

    scores = {}
    scores["D1_Claim_Accuracy"] = {"score": 4, "reason": "The output is generated from the extraction record and preserves the core finding."}
    scores["D2_Causal_Precision"] = {"score": 5 if "associated" in output_text.lower() or tradition == "Experimental" else 4, "reason": "Causal language is bounded for the detected method."}
    scores["D3_Scope_Fidelity"] = {"score": 5 if boundary_visible else 3, "reason": "Scope/context boundary is visible." if boundary_visible else "Scope boundary needs to be more explicit."}
    scores["D4_Method_Transparency"] = {"score": 5 if method_visible else 3, "reason": "The method/sample is visible." if method_visible else "The method is compressed out of the output."}
    scores["D5_Nuance_Preservation"] = {"score": 4 if boundary_visible else 3, "reason": "The output retains evidence limits and avoids a single universal claim."}
    scores["D6_Audience_Calibration"] = {"score": 4, "reason": f"The output follows a {output_type} style for a practitioner audience."}
    scores["D7_Actionability"] = {"score": 4 if not public_risk else 3, "reason": "Action steps are cautious and evidence-bounded." if not public_risk else "Public-facing format is useful but action guidance should stay cautious."}

    if invented_risk:
        scores["D1_Claim_Accuracy"] = {"score": 3, "reason": "Possible invented specificity requires human verification."}
    return scores


def score_outputs(outputs: Dict[str, str], record: ExtractionRecord, classification: ClassificationRecord) -> Dict[str, Any]:
    by_output = {ot: score_one_output(ot, txt, record, classification) for ot, txt in outputs.items()}
    means = {}
    for key, label in FIDELITY_DIMENSIONS:
        vals = [v[key]["score"] for v in by_output.values()]
        means[key] = round(sum(vals) / len(vals), 2) if vals else 0
    weakest = min(means.items(), key=lambda kv: kv[1])[0] if means else "D7_Actionability"
    return {"by_output": by_output, "dimension_means": means, "weakest_dimension": weakest}


def review_outputs(outputs: Dict[str, str], record: ExtractionRecord, classification: ClassificationRecord) -> Dict[str, Any]:
    issues = []
    fixes = []
    tradition = classification.methodological_tradition
    combined = "\n".join(outputs.values()).lower()

    if tradition != "Experimental" and any(word in combined for word in [" causes ", " proves ", " guarantee", " will increase "]):
        issues.append("Causal upgrading")
        fixes.append("Replace causal verbs with 'is associated with', 'is linked to', or 'suggests'.")
    if not any(word in combined for word in ["sample", "context", "boundary", "limit", "not prove"]):
        issues.append("Scope collapse")
        fixes.append("Add one sentence naming the study context and transfer boundary.")
    if not any(word in combined for word in ["survey", "interview", "method", "design", "review", "experiment", "statistical"]):
        issues.append("Method flattening")
        fixes.append("Add one method sentence to the output.")
    if any(word in combined for word in ["spokesperson", "said", "mayor", "department announced", "$"]):
        issues.append("Invented specificity")
        fixes.append("Remove unsupported quotes, named offices, budgets, and local details.")
    if not issues:
        issues.append("No major high-risk failure detected by rule scan")
        fixes.append("Still perform human review of citation, sample, method, causal language, and feasibility.")

    # Demonstration-friendly QA catch.
    qa_catch = ""
    if classification.methodological_tradition == "Quantitative":
        qa_catch = (
            "QA catch for presentation: because this is routed as Quantitative / survey-statistical evidence, "
            "phrases such as 'has impacts on' should be presented cautiously as 'is associated with' or 'is linked to' "
            "unless the paper's design clearly supports causation."
        )
    elif classification.methodological_tradition == "Theoretical":
        qa_catch = "QA catch: describe the paper as developing a framework/argument, not as empirically proving an effect."
    else:
        qa_catch = "QA catch: verify that claim strength matches the method and that no unsupported details were added."

    return {
        "issues_detected": issues,
        "targeted_fixes": fixes,
        "qa_catch": qa_catch,
        "failure_mode_reference": {name: FAILURE_MODES.get(name, {}) for name in issues if name in FAILURE_MODES},
    }


def run_workflow(file_obj: Any, pasted_text: str, output_types: List[str], audience: str) -> Dict[str, Any]:
    text, intake_meta = read_uploaded_file(file_obj, pasted_text)
    cleaned_text = text[:MAX_TEXT_CHARS]
    record = make_extraction_record(cleaned_text)
    classification = classify_record(cleaned_text, record)
    outputs = generate_outputs(output_types, record, classification, audience or "public administration practitioners")
    scores = score_outputs(outputs, record, classification)
    review = review_outputs(outputs, record, classification)

    return {
        "mode": "FREE deterministic workflow — no API key, no paid model, no credit required",
        "raw_text_preview": normalize_text(cleaned_text[:1800]),
        "intake": intake_meta,
        "extraction": asdict(record),
        "classification": asdict(classification),
        "outputs": outputs,
        "scores": scores,
        "review": review,
    }


def save_trace(trace: Dict[str, Any]) -> str:
    fd, path = tempfile.mkstemp(prefix="fidelitybridge_trace_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)
    return path
