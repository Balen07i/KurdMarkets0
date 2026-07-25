"""AI daily summary prompt — version 1.

Prompts are versioned (this file, plus any future `v2.py`, etc.) rather
than edited in place, and the version string used for a given summary is
stored on `AISummary.prompt_version` — so summary quality can be compared
across prompt revisions later instead of silently losing the history of
what prompt produced what output.

Only ever import `PROMPT_VERSION` and `build_prompt` from
`history/ai_summary.py` — the currently-active version is selected there,
in one place, rather than scattered across call sites.
"""

from __future__ import annotations

PROMPT_VERSION = "v1"

_SYSTEM_PROMPT = """\
You are a financial news summarizer for a Telegram bot serving Iraq and \
the Kurdistan Region. You write ONE short daily market summary in Central \
Kurdish (Sorani, script: کوردیی ناوەندی).

CRITICAL RULES — violating any of these makes your output unusable:
1. You may ONLY use the exact numbers given to you in the data block below.
2. NEVER invent, estimate, guess, round in a misleading way, or reference \
any price, percentage, or fact not explicitly present in the data.
3. If the data for a category is missing, do not mention that category — \
do not guess a plausible-sounding placeholder.
4. Do not fabricate news headlines or events. Only mention news if it is \
explicitly provided to you as "additional_context" — otherwise omit the \
"news" section entirely.
5. Keep the tone neutral, factual, and readable by a general audience \
(not financial-analyst jargon).
6. Output ONLY the Kurdish summary text — no preamble, no headers, no \
markdown, no explanation of what you're doing.

Structure the summary as short natural paragraphs covering, in order (skip \
any section whose data is missing rather than inventing content for it):
  - Overview of today's market
  - Dollar (USD/IQD) movement — mention both official and local market \
rates if both are present, and be explicit that they can differ
  - Gold movement
  - Silver movement
  - Notable Iraqi/Kurdistan financial news (ONLY if explicitly provided)
"""


def build_prompt(rates_summary: str, date_str: str, additional_context: str | None = None) -> tuple[str, str]:
    """Build the (system_prompt, user_prompt) pair for one day's summary.

    `rates_summary` must already be a plain-text rendering of verified
    published rates only (see `history/ai_summary.py::_format_rates_block`)
    — this function does not touch the database and has no way to verify
    that on its own, so callers MUST ensure it.
    """
    user_prompt = f"""\
Date: {date_str}

Verified market data (the ONLY numbers you may reference):
{rates_summary}
"""
    if additional_context:
        user_prompt += f"\nAdditional verified context (news etc.):\n{additional_context}\n"
    else:
        user_prompt += "\nNo additional news context was provided — omit the news section.\n"

    return _SYSTEM_PROMPT, user_prompt
