"""
workers/writer.py
Composes the final intelligence briefing report.

Improvement 5: API calls wrapped with exponential-backoff retry.
Improvement 6: focus_areas from the planner shape the report structure so the
               analyst addresses the angles the plan decided to investigate.
               A confidence signal is injected when verification results are weak.
"""

import os
from datetime import datetime
from openai import OpenAI
from utils.retry import call_with_retry

MODEL   = "gpt-4o"
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def _confidence_note(verifications):
    """Return a plain-text caution line when verification results are weak."""
    if not verifications:
        return ""
    total        = len(verifications)
    unverifiable = sum(1 for v in verifications if v["verdict"] == "Unverifiable")
    supported    = sum(1 for v in verifications if "Supported" in v["verdict"])

    if unverifiable == total:
        return (
            "\nCAUTION: Every claim in this briefing is unverifiable from the "
            "available sources. Treat all findings with caution.\n"
        )
    if unverifiable > supported:
        return (
            "\nCAUTION: More claims are unverifiable than supported by independent "
            "sources. Confidence in findings is limited.\n"
        )
    return ""


def write_briefing(topic, summaries, verifications, focus_areas, run_id, store, verbose=True):
    """
    Write a complete plain-text briefing report, persist it, and return it.

    Parameters
    ----------
    focus_areas : list[str]  — from the planner; used to frame the analysis.
    """
    date_str = datetime.now().strftime("%B %d, %Y")

    focus_str = ""
    if focus_areas:
        areas = "\n".join(f"  - {a}" for a in focus_areas)
        focus_str = f"\nResearch angles to address:\n{areas}\n"

    summaries_block = "\n\n".join(
        f"SOURCE: {s['title']}\nURL: {s['url']}\nSUMMARY: {s['summary']}"
        for s in summaries
    )

    verifications_block = "\n".join(
        f"  - {v['claim']}\n"
        f"    Origin : {v.get('source_title', '')}\n"
        f"    Verdict: {v['verdict']} — {v['reasoning']}"
        for v in verifications
    )

    caution = _confidence_note(verifications)

    prompt = (
        "You are an intelligence analyst writing a professional briefing report.\n\n"
        f"Topic : {topic}\n"
        f"Date  : {date_str}\n"
        f"{focus_str}"
        f"{caution}\n"
        "ARTICLE SUMMARIES:\n"
        f"{summaries_block}\n\n"
        "FACT-CHECKED CLAIMS (verified against independent sources):\n"
        f"{verifications_block}\n\n"
        "Write a complete briefing report with these clearly labelled sections:\n\n"
        "EXECUTIVE SUMMARY\n"
        "  Two or three sentences on the single most important finding.\n\n"
        "KEY FINDINGS\n"
        "  Three to five bullet points.\n\n"
        "DETAILED ANALYSIS\n"
        "  Two or three paragraphs. Address each research angle listed above.\n\n"
        "VERIFIED CLAIMS\n"
        "  List each claim, its origin source, and its cross-verification verdict.\n\n"
        "SOURCES\n"
        "  List each article title and its URL.\n\n"
        "Rules:\n"
        "- Write in professional prose.\n"
        "- Use plain-text section headings (no # symbols).\n"
        "- Do not use JSON or code blocks.\n"
        "- The report must be readable as plain text."
    )

    if verbose:
        print("  Composing briefing report...")

    response = call_with_retry(
        _get_client().chat.completions.create,
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.4,
    )

    report = response.choices[0].message.content.strip()
    store.save_report(run_id, report)
    return report
