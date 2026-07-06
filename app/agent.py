import os
import re
import json
import sys
import logging
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.workflow import Workflow, node
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.adk.tools import AgentTool, request_input
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.adk.apps import App, ResumabilityConfig
from google.genai import types
from google.adk.models import Gemini

from .config import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gemini-interviewer")

# Robust Gemini client with automatic retries for rate limits / 503 errors
agent_model = Gemini(
    model=config.model,
    retry_options=types.HttpRetryOptions(attempts=5)
)

# ─── MCP Toolset ────────────────────────────────────────────────────────────
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"],
        )
    )
)

# ─── Specialized Sub-Agents ─────────────────────────────────────────────────
# IMPORTANT: Agents that use tools must NOT have output_schema
#            (output_schema disables tool calling in ADK).

resume_analyzer = LlmAgent(
    name="resume_analyzer",
    model=agent_model,
    description="Analyzes resumes to extract technical skills, experience, strengths, and skill gaps for a target role.",
    instruction="""You are a professional Resume Analyzer.
Given a resume and target role, extract and present:
- Technical skills found
- Key strengths and achievements
- Experience summary
- Skills missing for the target role
Be concise and structured.""",
)

interview_planner = LlmAgent(
    name="interview_planner",
    model=agent_model,
    description="Creates personalized interview plans with exactly 3 questions based on resume analysis and target role.",
    instruction="""You are an Interview Planner.
Based on the candidate's resume analysis and target role, create a structured plan with exactly 3 questions:
1. One behavioral/HR question (test communication, teamwork, leadership)
2. One technical question (test domain knowledge for the target role)
3. One coding problem (a specific programming task to solve)
Label each with its type and difficulty (easy/medium/hard).""",
)

coding_evaluator = LlmAgent(
    name="coding_evaluator",
    model=agent_model,
    description="Evaluates code submissions for correctness, efficiency, and style. Uses validate_python_syntax tool to check syntax.",
    instruction="""You are a Coding Evaluator.
Evaluate the submitted code for:
- Correctness of logic
- Time and space complexity
- Coding style and best practices
Use the validate_python_syntax tool to verify syntax correctness.
Provide constructive hints instead of revealing the full solution.
Give an overall coding score out of 10.""",
    tools=[mcp_toolset],
)

feedback_agent = LlmAgent(
    name="feedback_agent",
    model=agent_model,
    description="Evaluates interview answers for technical accuracy, communication clarity, and STAR framework usage.",
    instruction="""You are a Communication and Feedback Coach.
Evaluate the answer for:
- Technical accuracy (score 1-10)
- Communication clarity (score 1-10)
- STAR framework usage (for behavioral questions: Situation, Task, Action, Result)
Provide specific, actionable improvement suggestions.""",
)

roadmap_agent = LlmAgent(
    name="roadmap_agent",
    model=agent_model,
    description="Generates comprehensive interview reports with scores, learning roadmaps, and curated study resources.",
    instruction="""You are a Career Coach and Technical Mentor.
Analyze the complete interview performance and generate a comprehensive report:
- Overall Interview Score (0-100)
- Technical Skills Score (0-100)
- HR/Behavioral Skills Score (0-100)
- Communication Feedback
- Key Strengths (bullet list)
- Areas for Improvement (bullet list)
- Readiness Level: "Not Ready", "Needs Practice", or "Ready"
- Personalized Learning Roadmap (step-by-step)
Use the get_study_resources tool to find learning materials for weak areas.
Use the suggest_practice_challenges tool to recommend coding problems.""",
    tools=[mcp_toolset],
)

# ─── Orchestrator Agent ─────────────────────────────────────────────────────
# Uses AgentTool for delegation and request_input for human-in-the-loop.
# No output_schema so tools work correctly.

orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    model=agent_model,
    instruction="""You are the GeminiInterviewer — an AI interview preparation coordinator.

Follow these steps exactly:

STEP 1 — ANALYZE RESUME
When you receive text containing a resume and target role, use the resume_analyzer tool to analyze it.
Present the analysis to the user.

STEP 2 — PLAN INTERVIEW
Use the interview_planner tool to create a 3-question interview plan.
Present the plan to the user, then proceed to ask questions.

STEP 3 — CONDUCT INTERVIEW
Ask questions ONE AT A TIME using the adk_request_input tool.
After each answer:
- For behavioral/technical questions: use the feedback_agent tool to evaluate
- For coding questions: use the coding_evaluator tool to evaluate
Present the feedback to the user before moving to the next question.

STEP 4 — FINAL REPORT
After all 3 questions are answered and evaluated, compile all the interview data
(questions, answers, and evaluations) and use the roadmap_agent tool to generate
a comprehensive readiness report with learning roadmap.
Present the full report to the user.

Be encouraging, professional, and thorough throughout the interview.""",
    tools=[
        AgentTool(resume_analyzer),
        AgentTool(interview_planner),
        AgentTool(coding_evaluator),
        AgentTool(feedback_agent),
        AgentTool(roadmap_agent),
        request_input,
    ],
)

# ─── Security ───────────────────────────────────────────────────────────────
PII_PATTERNS = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
}

INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "ignore instructions",
    "system prompt",
    "jailbreak",
    "override",
    "you are now",
    "dan mode",
]


@node(rerun_on_resume=True)
def security_checkpoint(ctx: Context, node_input: Any) -> Event:
    """Scrubs PII and detects prompt injection before passing to the orchestrator."""
    user_text = ""
    if isinstance(node_input, types.Content):
        user_text = "".join(part.text for part in node_input.parts if part.text)
    elif isinstance(node_input, str):
        user_text = node_input

    # Prompt injection check
    for kw in INJECTION_KEYWORDS:
        if kw in user_text.lower():
            audit = {"event": "security_violation", "reason": "prompt_injection_detected", "keyword": kw, "severity": "CRITICAL"}
            logger.warning(f"AUDIT LOG: {json.dumps(audit)}")
            return Event(output="Security violation: Prompt injection detected.", route="SECURITY_EVENT")

    # PII scrubbing
    scrubbed_text = user_text
    for pii_type, pattern in PII_PATTERNS.items():
        if re.findall(pattern, scrubbed_text):
            scrubbed_text = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", scrubbed_text)
            logger.info(f"AUDIT LOG: {json.dumps({'event': 'pii_scrubbed', 'type': pii_type, 'severity': 'INFO'})}")

    logger.info(f"AUDIT LOG: {json.dumps({'event': 'input_passed_security', 'severity': 'INFO'})}")
    ctx.state["user_input"] = scrubbed_text
    return Event(output=scrubbed_text, route="PASSED")


@node
def security_violation_handler(node_input: str) -> Event:
    """Blocks the request and returns a security warning to the user."""
    msg = f"⚠️ [Security Event] Request blocked: {node_input}"
    return Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=msg)]),
        output={"error": msg},
    )


# ─── Workflow Graph ─────────────────────────────────────────────────────────
root_agent = Workflow(
    name="gemini_interviewer",
    edges=[
        ("START", security_checkpoint),
        (security_checkpoint, {
            "SECURITY_EVENT": security_violation_handler,
            "PASSED": orchestrator_agent,
        }),
    ],
    description="An AI-powered adaptive interview preparation platform.",
)

# ─── App Container ──────────────────────────────────────────────────────────
app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True),
)
