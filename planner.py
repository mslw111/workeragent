"""
planner.py
Generates a structured research plan and evaluates whether collected articles
provide sufficient evidence to support it.

Improvement 1: The planner now does two real jobs —
  create_plan()       → produces focus areas used by every downstream worker
  evaluate_evidence() → checks coverage after collection and signals gaps
"""

import os
from openai import OpenAI
from utils.retry import call_with_retry

MODEL    = "gpt-4o"
_client  = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


# ── Plan container ─────────────────────────────────────────────────────────────

class TaskPlan:
    """Holds the research plan produced by create_plan()."""

    def __init__(self, topic, focus_areas, steps):
        self.topic       = topic
        self.focus_areas = focus_areas   # passed to summarizer and writer
        self.steps       = steps

    def display(self):
        print(f"  Topic       : {self.topic}")
        print()
        print("  Focus Areas:")
        for area in self.focus_areas:
            print(f"    - {area}")
        print()
        print("  Execution Steps:")
        for i, step in enumerate(self.steps, 1):
            print(f"    {i}. {step}")
        print()


# ── Plan creation ──────────────────────────────────────────────────────────────

def create_plan(topic):
    """
    Ask the model to produce a research plan and return a TaskPlan.
    The focus_areas are real constraints passed to summarizer and writer.
    """
    prompt = (
        f'Create a brief research plan for gathering information on: "{topic}"\n\n'
        "Provide two sections:\n\n"
        "FOCUS AREAS:\n"
        "List 3 to 4 specific research angles to investigate, one per line, "
        "each starting with a dash and a space.\n\n"
        "STEPS:\n"
        "List the execution steps in order, one per line, "
        'each starting with "STEP: ".\n\n'
        "Use plain text only. Do not use JSON."
    )

    response = call_with_retry(
        _get_client().chat.completions.create,
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.3,
    )
    text = response.choices[0].message.content.strip()

    focus_areas, steps = [], []
    in_focus = in_steps = False

    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        u = s.upper()
        if u.startswith("FOCUS"):
            in_focus, in_steps = True, False
            continue
        if u.startswith("STEP") and u.endswith(":"):
            in_focus, in_steps = False, True
            continue
        if in_focus and s.startswith("-"):
            area = s.lstrip("- ").strip()
            if area:
                focus_areas.append(area)
        if s.upper().startswith("STEP:"):
            steps.append(s[5:].strip())
        elif in_steps and s and s[0].isdigit() and "." in s:
            steps.append(s.split(".", 1)[1].strip())

    if not focus_areas:
        focus_areas = [topic]
    if not steps:
        steps = [
            "Collect articles from sources.txt",
            "Evaluate evidence coverage",
            "Summarize articles with focus areas as context",
            "Extract and cross-verify key claims",
            "Write final briefing report",
            "Send report by email (optional)",
        ]

    return TaskPlan(topic=topic, focus_areas=focus_areas, steps=steps)


# ── Evidence evaluation ────────────────────────────────────────────────────────

def evaluate_evidence(topic, focus_areas, articles):
    """
    Check whether the collected articles cover the planned focus areas.

    Called by the orchestrator after collection, before summarisation.
    Returns (sufficient: bool, reason: str, missing_areas: list[str]).
    """
    if not articles:
        return False, "No articles were collected.", list(focus_areas)

    snippets = "\n".join(
        f"- {a['title']}: {a['content'][:250]}..."
        for a in articles
    )
    focus_str = "\n".join(f"  - {area}" for area in focus_areas)

    prompt = (
        f'You are evaluating research coverage for a briefing on: "{topic}"\n\n'
        f"Planned focus areas:\n{focus_str}\n\n"
        f"Collected article titles and opening text:\n{snippets}\n\n"
        "Answer in plain text using exactly this format:\n"
        "SUFFICIENT: yes or no\n"
        "REASON: one sentence\n"
        "MISSING: list any uncovered focus areas, one per line starting with -, "
        "or write 'none' if all are covered"
    )

    response = call_with_retry(
        _get_client().chat.completions.create,
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.1,
    )
    text = response.choices[0].message.content.strip()

    sufficient    = True
    reason        = "Evidence appears sufficient."
    missing_areas = []
    in_missing    = False

    for line in text.splitlines():
        s = line.strip()
        if s.upper().startswith("SUFFICIENT:"):
            val = s.split(":", 1)[1].strip().lower()
            sufficient = val.startswith("y")
            in_missing = False
        elif s.upper().startswith("REASON:"):
            reason = s.split(":", 1)[1].strip()
            in_missing = False
        elif s.upper().startswith("MISSING:"):
            tail = s.split(":", 1)[1].strip()
            in_missing = True
            if tail and tail.lower() != "none" and tail.startswith("-"):
                missing_areas.append(tail.lstrip("- ").strip())
        elif in_missing and s.startswith("-"):
            area = s.lstrip("- ").strip()
            if area and area.lower() != "none":
                missing_areas.append(area)

    return sufficient, reason, missing_areas
