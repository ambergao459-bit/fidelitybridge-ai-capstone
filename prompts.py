"""Prompt library and output schemas for FidelityBridge AI.

This file is intentionally separate from app.py so presenters can open it during
Slide 4 / backend-code explanation and show that the demo is staged prompts, not
one mega-prompt.
"""

from __future__ import annotations

from typing import Dict, List

METHOD_TRADITIONS: List[str] = [
    "Quantitative",
    "Qualitative",
    "Mixed Methods",
    "Theoretical",
    "Experimental",
    "Meta-analysis",
    "Systematic Review",
]

FIDELITY_DIMENSIONS: Dict[str, str] = {
    "D1_Claim_Accuracy": "Does the output preserve the paper's actual claims and findings?",
    "D2_Causal_Precision": "Does it avoid causal language unless the design supports causation?",
    "D3_Scope_Fidelity": "Does it preserve context, population, setting, and transfer limits?",
    "D4_Method_Transparency": "Does it keep the method/design visible enough for the audience?",
    "D5_Nuance_Preservation": "Does it preserve caveats, uncertainty, and competing explanations?",
    "D6_Audience_Calibration": "Does it match the requested audience, tone, and format?",
    "D7_Actionability": "Are recommendations specific, useful, and evidence-bounded?",
}

OUTPUT_SCHEMAS: Dict[str, str] = {
    "Policy Brief": "Issue statement; evidence base; what it does not show; options; recommendation; caveats.",
    "Technical Note": "Research design; data; operationalization; analytical approach; findings; limitations.",
    "Executive Summary": "Purpose; problem; methodology overview; bottom-line results; confidence; next steps.",
    "Op-Ed": "Hook; problem framing; evidence; counterargument; call to action.",
    "LinkedIn Post": "Hook; context; key finding; implication; call to action; concise professional tone.",
    "Twitter/X Thread": "Numbered thread; study type; findings; implication; guardrail.",
    "Briefing Memo": "To/from/subject; context; decision question; evidence; recommendation; unknowns.",
    "Elevator Pitch": "Hook; problem; solution; ask; method guardrail.",
    "Infographic Text": "Main header; three data callouts; bottom note; practical takeaway.",
    "Mechanism Map": "Central variable; labeled arrows; logic explanation; boundary note.",
    "Research Summary": "Overview; design; main findings; why it matters; limits.",
    "Literature Review Entry": "APA citation; research focus; method; core contribution; methodological fit; translation caution.",
    "Practitioner Guide": "Audience; when to use evidence; what the paper shows; application steps; what not to claim.",
    "Training Module Outline": "Learning goals; key concept; activity; discussion prompt; implementation warning.",
    "Grant Concept Note": "Problem; evidence base; proposed intervention; evaluation logic; limits.",
    "Media Release": "Headline; dateline; lead; findings; method/scope boundary; media contact; no invented quotes.",
    "Letter to the Editor": "Short public claim; evidence; local relevance; bounded action.",
    "Conference Abstract": "Background; method; findings; contribution; limitations.",
}

FAILURE_MODES: Dict[str, str] = {
    "Causal upgrading": "Association, correlation, or conceptual argument is rewritten as proof or direct causation.",
    "Invented specificity": "The output adds unsupported quotes, local offices, budgets, dates, people, or statistics.",
    "Scope collapse": "A bounded sample, country, method, or setting becomes a universal prescription.",
    "Method flattening": "The output hides or oversimplifies the study design, sample, or evidence type.",
    "Actionability drift": "Recommendations become stronger, broader, or more operational than the evidence supports.",
    "Citation drift": "A finding or cited claim is attributed to the focal paper when it came from background literature.",
    "Jargon echo": "Technical terms remain unexplained in public or practitioner-facing formats.",
}

SYSTEM_MESSAGE = """You are FidelityBridge AI, a public-administration research translation workflow.
Your job is to preserve fidelity to method, scope, claims, and evidence limits while creating practitioner-ready outputs.
You must never invent statistics, quotations, local agencies, dates, author claims, or policy effects not present in the source.
Show caution around causation. If a study is cross-sectional, correlational, theoretical, qualitative, systematic review, or meta-analysis, do not use 'causes', 'proves', or 'will lead to' unless the paper's design and text clearly support it.
"""

EXTRACTION_PROMPT = """STAGE 2: EXTRACT TO STRUCTURED RECORD
Read the research paper text below and create a source-bound extraction sheet before any writing begins.
Return valid JSON only, with these keys:
- apa_citation_best_effort
- title
- authors
- year
- research_question_or_objective
- public_administration_topic
- data_sample_context
- research_design
- methodological_tradition_candidate
- variables_or_constructs
- key_findings
- limitations_stated_or_inferred
- what_the_paper_does_not_prove
- causal_language_boundary
- direct_evidence_quotes_short
- translation_guardrails

Paper text:
{paper_text}
"""

CLASSIFICATION_PROMPT = """STAGE 3: CLASSIFY + ROUTE
Using the extraction sheet below, classify the paper into exactly one of these traditions:
Quantitative, Qualitative, Mixed Methods, Theoretical, Experimental, Meta-analysis, Systematic Review.
Return valid JSON only, with keys:
- tradition
- confidence_1_to_5
- rationale
- evidence_boundary
- routing_rules
- risky_language_to_avoid
- recommended_outputs_for_demo

Extraction sheet:
{extraction_json}
"""

GENERATION_PROMPT = """STAGE 5: GENERATE 1-2 OUTPUTS FROM THE EXTRACTION SHEET ONLY
Generate the requested output type(s) for the target audience. Use the schema for each output type.
Do not generate all 18 outputs. This live demo should generate only the requested 1-2 representative outputs.
Preserve method, scope, and evidence limits. Include at least one method/scope/caution sentence when the output is public-facing or persuasive.
Do not invent local facts, quotes, people, costs, dates, institutions, or policy effects.

Target audience: {target_audience}
Requested output types and schemas:
{selected_schemas}

Classification and routing:
{classification_json}

Extraction sheet:
{extraction_json}

Return Markdown with clear headings for each output.
"""

SCORING_PROMPT = """STAGE 6: SCORE ON 7 FIDELITY DIMENSIONS
Score the generated output against the extraction sheet and classification route.
Return valid JSON only, with:
- scores: object with D1_Claim_Accuracy, D2_Causal_Precision, D3_Scope_Fidelity, D4_Method_Transparency, D5_Nuance_Preservation, D6_Audience_Calibration, D7_Actionability. Each dimension must include two fields named score and reason.
- weakest_dimension
- strongest_dimension
- likely_failure_modes
- targeted_revision_needed
- one_sentence_presenter_takeaway

Scale: 1 = weak, 3 = acceptable but needs revision, 5 = strong.

Fidelity dimensions:
{dimensions}

Extraction sheet:
{extraction_json}

Classification:
{classification_json}

Generated output:
{generated_output}
"""

QA_FIX_PROMPT = """STAGE 7: QA CATCH + TARGETED FIX
Find one real fidelity risk in the generated output and repair it. Prioritize causal overstatement, invented specificity, scope collapse, method flattening, or actionability drift.
Return Markdown with these headings:
1. QA Catch
2. Failure Mode Name
3. Why It Matters
4. Before -> After Fix
5. Revised Output Section Only
6. Presenter Line

Failure mode catalog:
{failure_modes}

Extraction sheet:
{extraction_json}

Classification:
{classification_json}

Scores:
{scores_json}

Generated output:
{generated_output}
"""
