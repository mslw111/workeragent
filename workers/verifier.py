"""
workers/verifier.py
Extracts key claims and verifies each one against independent sources.

Improvement 2: Cross-source verification.
  - Each claim is tagged with the source summary it came from.
  - That source is excluded from the evidence block used to verify the claim.
  - A claim is no longer checked against the summary that generated it,
    breaking the self-confirmation loop identified in the reflection.
  - Falls back gracefully when only one source is available.

Improvement 5: API calls wrapped with exponential-backoff retry.
"""

import os
from openai import OpenAI
from utils.retry import call_with_retry

MODEL   = "gpt-4o"
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


# ── Claim extraction ───────────────────────────────────────────────────────────

def extract_claims(summaries, topic):
    """
    Ask the model to identify 3-5 key claims and tag each with the source
    number it primarily came from.

    Returns list of (claim: str, source_idx: int) where source_idx is
    0-based into the summaries list.
    """
    numbered_evidence = "\n\n".join(
        f"[SOURCE {i + 1}] {s['title']}\n{s['summary']}"
        for i, s in enumerate(summaries)
    )

    prompt = (
        f'From the following numbered research summaries about "{topic}", '
        "identify the 3 to 5 most important factual claims.\n\n"
        f"Summaries:\n{numbered_evidence}\n\n"
        "For each claim, record which source number it primarily comes from.\n"
        "Format every line exactly as:\n"
        "CLAIM: <claim as one sentence> | SOURCE: <number>\n\n"
        "Use plain text only. No other text."
    )

    response = call_with_retry(
        _get_client().chat.completions.create,
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.2,
    )
    text = response.choices[0].message.content.strip()

    claims = []
    for line in text.splitlines():
        s = line.strip()
        if not s.upper().startswith("CLAIM:"):
            continue
        parts = s.split("|")
        claim_text = parts[0].replace("CLAIM:", "").strip()
        source_idx = 0
        if len(parts) > 1:
            src = parts[1].strip()
            if src.upper().startswith("SOURCE:"):
                try:
                    num = int(src.split(":", 1)[1].strip())
                    source_idx = max(0, min(num - 1, len(summaries) - 1))
                except (ValueError, IndexError):
                    pass
        if claim_text:
            claims.append((claim_text, source_idx))

    # Fallback: numbered list without source tags
    if not claims:
        for line in text.splitlines():
            s = line.strip()
            if s and s[0].isdigit() and "." in s:
                claim_text = s.split(".", 1)[1].strip()
                if claim_text:
                    claims.append((claim_text, 0))

    return claims if claims else [(text, 0)]


# ── Claim verification ─────────────────────────────────────────────────────────

def verify_claim(claim, source_idx, summaries):
    """
    Verify *claim* using every summary EXCEPT the one at source_idx.

    When only one summary exists there is no independent source; the function
    proceeds but notes the limitation in the verdict.

    Returns (verdict: str, reasoning: str).
    """
    independent = [s for i, s in enumerate(summaries) if i != source_idx]

    if not independent:
        # Single-source edge case — can't verify independently
        return (
            "Unverifiable",
            "Only one source was collected; independent cross-verification "
            "was not possible.",
        )

    evidence_text = "\n\n".join(
        f"Source: {s['title']}\n{s['summary']}" for s in independent
    )

    prompt = (
        "You are a fact-checker. Evaluate the claim below using ONLY the "
        "independent evidence provided. The source the claim came from is "
        "deliberately excluded.\n\n"
        f"CLAIM: {claim}\n\n"
        f"INDEPENDENT EVIDENCE:\n{evidence_text}\n\n"
        "Reply in this exact format (plain text, no JSON):\n"
        "VERDICT: <Supported | Partially Supported | Not Supported | Unverifiable>\n"
        "REASONING: <one or two sentences citing specific evidence>"
    )

    response = call_with_retry(
        _get_client().chat.completions.create,
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.1,
    )
    text = response.choices[0].message.content.strip()

    verdict   = "Unverifiable"
    reasoning = text

    for line in text.splitlines():
        if line.startswith("VERDICT:"):
            verdict = line.replace("VERDICT:", "").strip()
        elif line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()

    return verdict, reasoning


# ── Orchestration ──────────────────────────────────────────────────────────────

def extract_and_verify_claims(summaries, topic, run_id, store, verbose=True):
    """
    Extract key claims (with source attribution), verify each against
    independent sources, persist results, and return a list of dicts.
    """
    if verbose:
        print("  Extracting key claims with source attribution...")

    claim_pairs = extract_claims(summaries, topic)  # [(claim, source_idx), ...]

    verifications = []
    for claim, source_idx in claim_pairs:
        source_title = (
            summaries[source_idx]["title"]
            if source_idx < len(summaries)
            else "unknown"
        )
        if verbose:
            print(f"  Verifying: {claim[:70]}...")
            print(f"    Origin : {source_title}")
            print(f"    Against: {len(summaries) - 1} other source(s)")

        verdict, reasoning = verify_claim(claim, source_idx, summaries)
        store.save_verification(run_id, claim, verdict, reasoning)

        verifications.append(
            {
                "claim": claim,
                "verdict": verdict,
                "reasoning": reasoning,
                "source_title": source_title,
            }
        )

        if verbose:
            print(f"    Verdict: {verdict}")

    return verifications
