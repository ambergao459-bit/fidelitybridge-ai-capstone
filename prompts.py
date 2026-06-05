"""Prompt/rule library for FidelityBridge AI Free Mode.
No paid API is used. The app uses deterministic extraction, routing, templates, and QA checks.
"""

APP_TITLE = "FidelityBridge AI — Free Workflow Demo"

STAGES = [
    ("intake", "1 Intake"),
    ("extract", "2 Extract"),
    ("classify", "3 Classify"),
    ("generate", "4 Generate"),
    ("score", "5 Score D1-D7"),
    ("review", "6 Review / QA Fix"),
]

FIDELITY_DIMENSIONS = [
    ("D1_Claim_Accuracy", "Claim Accuracy"),
    ("D2_Causal_Precision", "Causal Precision"),
    ("D3_Scope_Fidelity", "Scope Fidelity"),
    ("D4_Method_Transparency", "Method Transparency"),
    ("D5_Nuance_Preservation", "Nuance Preservation"),
    ("D6_Audience_Calibration", "Audience Calibration"),
    ("D7_Actionability", "Actionability"),
]

OUTPUT_TYPES = [
    "Policy Brief",
    "Technical Note",
    "Executive Summary",
    "Op-Ed",
    "LinkedIn Post",
    "Twitter/X Thread",
    "Briefing Memo",
    "Elevator Pitch",
    "Infographic Text",
    "Mechanism Map",
    "Research Summary",
    "Literature Review Entry",
    "Practitioner Guide",
    "Training Module Outline",
    "Grant Concept Note",
    "Media Release",
    "Letter to the Editor",
    "Conference Abstract",
]

SCHEMAS = {
    "Policy Brief": "Issue statement; evidence base; what it does not show; options; recommendation; caveats.",
    "Technical Note": "Research design; data; operationalization; analytical approach; findings; limitations.",
    "Executive Summary": "Purpose; problem; methodology overview; bottom-line results; confidence; next steps.",
    "Op-Ed": "Hook; problem framing; evidence; counterargument; call to action.",
    "LinkedIn Post": "Hook; context; key finding; implication; call to action; concise professional tone.",
    "Twitter/X Thread": "Numbered thread; study type; findings; implication; guardrail.",
    "Briefing Memo": "To/from/subject; context; decision question; evidence; recommendation; unknowns.",
    "Elevator Pitch": "Hook; problem; solution; ask; method guardrail.",
    "Infographic Text": "Main header; three data callouts; bottom note; practical takeaway.",
    "Mechanism Map": "Central variable; arrows; logic explanation; boundary note.",
    "Research Summary": "Overview; design; main findings; why it matters; limits.",
    "Literature Review Entry": "APA citation; research focus; method; core contribution; methodological fit; translation caution.",
    "Practitioner Guide": "Audience; when to use evidence; what the paper shows; application steps; what not to claim.",
    "Training Module Outline": "Learning goals; key concept; activity; discussion prompt; implementation warning.",
    "Grant Concept Note": "Problem; evidence base; proposed intervention; evaluation logic; limits.",
    "Media Release": "Headline; dateline; lead; findings; method/scope boundary; media contact; no invented quotes.",
    "Letter to the Editor": "Short public claim; evidence; local relevance; bounded action.",
    "Conference Abstract": "Background; method; findings; contribution; limitations.",
}

STAGE_PROMPTS = {
    "intake": "Intake prompt: parse the uploaded paper, identify visible citation clues, abstract, section headings, file size, and source text quality. Do not generate outputs yet.",
    "extract": "Extraction prompt: create a source-bound record with title, authors, year, venue, DOI/citation clues, research objective, method/design, sample/context, key findings, limits, and what the paper does not prove.",
    "classify": "Classification prompt: classify methodological tradition and route the paper to method-aware generation and QA rules.",
    "generate": "Generation prompt: generate only 1-2 requested output types from the extraction record and output schema. Preserve method, scope, and evidence boundaries.",
    "score": "Scoring prompt: score each output across D1-D7 with a 1-5 score, concise reason, weakest dimension, and targeted revision rule.",
    "review": "Review prompt: run QA scans for causal upgrading, scope collapse, method flattening, invented specificity, and actionability drift; then show the fix.",
}

FAILURE_MODES = {
    "Causal upgrading": {
        "trigger": "Survey, correlational, theoretical, review, or SEM evidence in persuasive/public-facing outputs.",
        "example": "associated with -> causes / proves / will increase",
        "fix": "Use bounded verbs: is associated with, is linked to, suggests, may support.",
    },
    "Scope collapse": {
        "trigger": "One context, country, sample, or institution becomes a universal recommendation.",
        "example": "one Chongqing sample -> all governments should adopt this everywhere",
        "fix": "Add context and transferability boundary.",
    },
    "Method flattening": {
        "trigger": "Short outputs compress out survey/interview/review design details.",
        "example": "The output states the finding but hides the method.",
        "fix": "Require one method sentence in every output.",
    },
    "Invented specificity": {
        "trigger": "Media releases, memos, or public posts invent quotes, offices, dates, costs, or local actors.",
        "example": "An invented agency quote appears in a media release.",
        "fix": "Ban unsupported names, quotes, statistics, and local details.",
    },
    "Actionability drift": {
        "trigger": "A practical format turns a cautious finding into a strong intervention recommendation.",
        "example": "Launch a citywide reform immediately based on one observational study.",
        "fix": "Use pilot, review, monitor, or adapt language instead of universal commands.",
    },
}
