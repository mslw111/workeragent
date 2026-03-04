"""
orchestrator.py
Controls the full workflow: plan → collect → evaluate → summarize → verify → write → email.

Improvement 1: evaluate_evidence() is called after collection; results influence
               the pipeline (gap warnings, halt on zero coverage).
Improvement 3: Quality gates halt or warn at each stage before proceeding.
Improvement 6: plan.focus_areas are threaded through to summarizer and writer.
"""

import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from planner import create_plan, evaluate_evidence
from workers import web_collector, summarizer, verifier, writer
from store import sqlite_store as store
from emailer import send_report, EMAIL_TO


# ── Environment check ──────────────────────────────────────────────────────────

REQUIRED_VARS = ["OPENAI_API_KEY"]


def check_environment():
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if not missing:
        return

    print()
    print("=" * 60)
    print("  SETUP REQUIRED — Missing Environment Variables")
    print("=" * 60)
    print()
    print("The following required variables are not set:")
    for v in missing:
        print(f"  - {v}")
    print()
    print("To fix this:")
    print()
    print("  1. Copy .env.example to a new file named .env")
    print("     (in the same folder as orchestrator.py)")
    print()
    print("  2. Open .env and fill in your values, for example:")
    print()
    print("       OPENAI_API_KEY=sk-...")
    print("       SMTP_USER=you@gmail.com")
    print("       SMTP_APP_PASSWORD=xxxx xxxx xxxx xxxx")
    print("       EMAIL_TO=recipient@example.com")
    print()
    print("  3. Save the file and run the program again.")
    print()
    print("See README.md  ›  STEP: ADD YOUR API KEY  for full instructions.")
    print()
    sys.exit(1)


# ── Quality gate helpers ───────────────────────────────────────────────────────

MIN_ARTICLES = 2   # fewer than this → halt (cross-verification impossible)


def _gate_collection(articles, run_id):
    """
    Improvement 3: halt if not enough articles were collected.
    Returns True if the pipeline should continue, False to abort.
    """
    if len(articles) >= MIN_ARTICLES:
        return True

    if len(articles) == 0:
        print(
            "\n  No articles were collected.\n"
            "  Check that sources.txt contains valid URLs and that you have "
            "an internet connection."
        )
    else:
        print(
            f"\n  Only {len(articles)} article was collected.\n"
            f"  At least {MIN_ARTICLES} are required so that claims can be\n"
            "  verified against independent sources.\n"
            "  Add more URLs to sources.txt and run again."
        )

    store.update_run_status(run_id, "failed")
    return False


def _gate_evidence(topic, focus_areas, articles):
    """
    Improvement 1 + 3: call the planner's evidence evaluator; warn on gaps.
    Never halts — gaps are reported so the user can add sources, but the
    pipeline continues to produce a partial report.
    """
    sufficient, reason, missing = evaluate_evidence(topic, focus_areas, articles)

    if sufficient:
        print("  Evidence coverage looks good.\n")
        return

    print(f"  Warning: {reason}")
    if missing:
        print("  The following research angles have limited coverage:")
        for area in missing:
            print(f"    - {area}")
        print(
            "  Consider adding more targeted URLs to sources.txt.\n"
            "  The report will proceed but may have gaps.\n"
        )
    else:
        print("  The report will proceed but may be incomplete.\n")


def _gate_verification(verifications):
    """
    Improvement 3: warn when all claims are unverifiable.
    Does not halt — writer already injects a caution note in that case.
    """
    if not verifications:
        return
    total        = len(verifications)
    unverifiable = sum(1 for v in verifications if v["verdict"] == "Unverifiable")
    if unverifiable == total:
        print(
            "\n  Warning: No claims could be independently verified.\n"
            "  This may mean the sources lack corroborating detail, or that\n"
            "  the topic requires more diverse sources.\n"
            "  The report will include a caution note.\n"
        )


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run(topic, email_to=None, verbose=True):
    """
    Execute the full research-and-briefing pipeline for *topic*.

    Parameters
    ----------
    topic    : str  — research subject
    email_to : str  — recipient address (None = skip email)
    verbose  : bool — print progress messages
    """
    check_environment()
    store.initialize_db()

    print()
    print("=" * 60)
    print("  INTELLIGENCE BRIEFING SYSTEM")
    print("=" * 60)
    print(f"\n  Topic: {topic}\n")

    # ── Step 1: Plan ───────────────────────────────────────────────────────────
    print("[1/6] Creating research plan...")
    plan = create_plan(topic)
    plan.display()                          # shows focus_areas and steps

    run_id = store.create_run(topic)

    # ── Step 2: Collect ────────────────────────────────────────────────────────
    print("[2/6] Collecting articles from sources.txt...")
    try:
        articles = web_collector.collect_all(run_id, store, verbose=verbose)
    except FileNotFoundError as exc:
        print(f"\n  Error: {exc}")
        store.update_run_status(run_id, "failed")
        return None

    print(f"\n  Collected {len(articles)} article(s).\n")

    # Quality gate — minimum article count
    if not _gate_collection(articles, run_id):
        return None

    # ── Step 3: Evaluate evidence coverage ────────────────────────────────────
    print("[3/6] Evaluating evidence coverage against research plan...")
    _gate_evidence(topic, plan.focus_areas, articles)

    # ── Step 4: Summarize ──────────────────────────────────────────────────────
    print("[4/6] Summarizing articles...")
    summaries = summarizer.summarize_all(
        articles, topic, plan.focus_areas, run_id, store, verbose=verbose
    )
    print(f"\n  Created {len(summaries)} summary/summaries.\n")

    # ── Step 5: Verify ─────────────────────────────────────────────────────────
    print("[5/6] Verifying key claims against independent sources...")
    verifications = verifier.extract_and_verify_claims(
        summaries, topic, run_id, store, verbose=verbose
    )
    print(f"\n  Verified {len(verifications)} claim(s).\n")

    # Quality gate — warn if nothing could be verified
    _gate_verification(verifications)

    # ── Step 6: Write ──────────────────────────────────────────────────────────
    print("[6/6] Writing briefing report...")
    report = writer.write_briefing(
        topic, summaries, verifications, plan.focus_areas, run_id, store, verbose=verbose
    )
    store.update_run_status(run_id, "complete")

    # ── Display ────────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  BRIEFING REPORT")
    print("=" * 60)
    print()
    print(report)
    print()
    print("=" * 60)

    # ── Email (optional) ───────────────────────────────────────────────────────
    recipient = email_to or EMAIL_TO
    if recipient:
        print(f"\nSending report to {recipient}...")
        success, msg = send_report(
            to_address=recipient,
            subject=f"Intelligence Briefing: {topic}",
            body=report,
        )
        if success:
            print("  Report sent successfully.")
        else:
            print(f"  Email could not be sent:\n  {msg}")
    else:
        print(
            "\n  Tip: set EMAIL_TO in your .env file to have the report "
            "emailed automatically."
        )

    print()
    return report


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Intelligence Briefing System — research, summarise, verify, report."
    )
    parser.add_argument("topic", help="The research topic for the briefing.")
    parser.add_argument(
        "--email",
        metavar="ADDRESS",
        default=None,
        help="Email address to send the finished report to.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress step-by-step progress output.",
    )

    args = parser.parse_args()
    run(args.topic, email_to=args.email, verbose=not args.quiet)
