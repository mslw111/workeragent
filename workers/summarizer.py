"""
workers/summarizer.py
Creates plain-text article summaries using OpenAI.

Improvement 5: API calls wrapped with exponential-backoff retry.
Improvement 6: focus_areas from the plan are injected into every prompt so
               each summary explicitly addresses the planned research angles.
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


def summarize_article(title, content, topic, focus_areas=None):
    """
    Return a concise plain-text summary of one article.
    focus_areas (list[str]) — from the planner; steer the summary toward
    the angles the plan decided to investigate.
    """
    focus_str = ""
    if focus_areas:
        areas = "\n".join(f"  - {a}" for a in focus_areas)
        focus_str = f"\n\nPay particular attention to these research angles:\n{areas}"

    prompt = (
        f"You are a research assistant preparing a briefing on: {topic}{focus_str}\n\n"
        f"Article title: {title}\n\n"
        f"Article content:\n{content}\n\n"
        "Write a concise summary of 3-5 sentences covering:\n"
        "- The main point or finding\n"
        "- Key facts, figures, or quotes\n"
        "- Why this is relevant to the topic and the research angles above\n\n"
        "Write in plain prose. Do not use bullet points, JSON, or markdown."
    )

    response = call_with_retry(
        _get_client().chat.completions.create,
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def summarize_all(articles, topic, focus_areas, run_id, store, verbose=True):
    """
    Summarize each article with focus_areas as context, persist to store,
    and return a list of summary dicts.
    """
    summaries = []

    for article in articles:
        if verbose:
            print(f"  Summarizing: {article['title']}")

        summary = summarize_article(
            article["title"], article["content"], topic, focus_areas
        )
        store.save_summary(article["article_id"], run_id, summary)

        summaries.append(
            {
                "url": article["url"],
                "title": article["title"],
                "summary": summary,
            }
        )

        if verbose:
            print("    Done.")

    return summaries
