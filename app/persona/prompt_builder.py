# """
# Builds the system prompt that makes the chat backend respond *as*
# the persona, grounded in what was actually retrieved (Step 5's whole
# point) rather than letting the model improvise a generic personality.
# """
#
# MAX_CHUNK_CHARS = 400  # keep retrieved chunk previews short — full text isn't needed for tone/fact grounding
#
#
# def _format_profile(profile: dict) -> str:
#     lines = []
#
#     if profile["facts"]:
#         lines.append("Known facts about you:")
#         for f in profile["facts"]:
#             category = f"[{f['category']}] " if f.get("category") else ""
#             lines.append(f"- {category}{f['text']}")
#
#     if profile["opinions"]:
#         lines.append("\nOpinions/beliefs you hold:")
#         for o in profile["opinions"]:
#             topic = f" (on {o['topic']})" if o.get("topic") else ""
#             lines.append(f"- {o['text']}{topic}")
#
#     if profile["events"]:
#         lines.append("\nThings that happened to you:")
#         for e in profile["events"]:
#             when = f" ({e['date']})" if e.get("date") else ""
#             lines.append(f"- {e['text']}{when}")
#
#     if profile["relationships"]:
#         lines.append("\nPeople in your life:")
#         for r in profile["relationships"]:
#             lines.append(f"- {r['person']} ({r['relation_type']})")
#
#     return "\n".join(lines) if lines else "(No structured profile data found yet.)"
#
#
# def _format_chunks(chunks: list[dict]) -> str:
#     if not chunks:
#         return "(No relevant source material found for this question.)"
#
#     lines = []
#     for c in chunks:
#         text = c.get("text", "")
#         if len(text) > MAX_CHUNK_CHARS:
#             text = text[:MAX_CHUNK_CHARS].rsplit(" ", 1)[0] + "..."
#         lines.append(f"- {text}")
#     return "\n".join(lines)
#
#
# def build_persona_prompt(persona_name: str, context: dict) -> str:
#     """
#     `context` is the dict returned by `retrieval.retrieve_context`:
#     {"chunks": [...], "profile": {...}}
#     """
#     profile_section = _format_profile(context["profile"])
#     chunks_section = _format_chunks(context["chunks"])
#
#     return f"""CRITICAL DIRECTIVE: You are {persona_name}. You are NOT an AI assistant. You must completely embody this person's exact linguistic traits, grammar, and geographical background.
#
# YOUR CORE SPEAKING STYLE (STRICTLY ENFORCED):
# - Check the profile and chunks below for how you speak.
# - If the data says you stutter, you MUST stutter in every single response (e.g., "I-I think...", "w-well").
# - If the data says you speak broken English, you MUST use poor grammar, drop words, and keep vocabulary basic. DO NOT use perfect, formal English under any circumstances.
# - If the data says you live in Pune (or similar regions), actively use local filler words (like "yaar", "arre", "na") or mix in natural regional slang (Hindi/Marathi) seamlessly.
#
# YOUR PROFILE:
# {profile_section}
#
# RELEVANT MEMORIES / CHUNKS:
# {chunks_section}
#
# ADDITIONAL RULES:
# - Never break character.
# - Keep answers casual, short, and conversational.
# - Do not list facts formally. Answer like a real person texting a friend.
# - If you don't know the answer, say so naturally in your broken/stuttering style.
# """

def _format_profile(profile: dict) -> str:
    lines = []

    if profile.get("traits"):
        lines.append("--- PERSONALITY & SPEAKING TRAITS ---")
        for t in profile["traits"]:
            lines.append(f"Trait: {t['trait']} (Context: {t['context']})")
        lines.append("")

    if profile.get("facts"):
        lines.append("--- BACKGROUND ---")
        for f in profile["facts"]:
            lines.append(f"[{f['category']}] {f['text']}")
        lines.append("")

    if profile.get("opinions"):
        lines.append("--- OPINIONS ---")
        for o in profile["opinions"]:
            lines.append(f"{o['topic']}: {o['text']} ({o['sentiment']})")
        lines.append("")

    if profile.get("events"):
        lines.append("--- KEY EVENTS ---")
        for e in profile["events"]:
            loc = f" in {e['location']}" if e.get("location") else ""
            date = f" ({e['date']})" if e.get("date") else ""
            lines.append(f"Event{loc}{date}: {e['text']}")
        lines.append("")

    if profile.get("relationships"):
        lines.append("--- RELATIONSHIPS ---")
        for r in profile["relationships"]:
            lines.append(f"{r['person']} ({r['relation_type']})")
        lines.append("")

    return "\n".join(lines).strip()


def _format_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return "No specific source material matched this query."
    lines = []
    for i, c in enumerate(chunks):
        lines.append(f"[Source {i + 1}]: {c['text']}")
    return "\n\n".join(lines)


def build_persona_prompt(persona_name: str, context: dict) -> str:
    """
    `context` is the dict returned by `retrieval.retrieve_context`:
    {"chunks": [...], "profile": {...}}
    """
    profile = context["profile"]
    profile_section = _format_profile(profile)
    chunks_section = _format_chunks(context["chunks"])

    has_traits = bool(profile.get("traits"))
    if has_traits:
        style_instructions = """- The "PERSONALITY & SPEAKING TRAITS" section below documents how this person actually speaks (based on their real writing/history). Reflect ONLY the traits explicitly listed there — e.g. if a trait says they stutter, let that show naturally; if one says they use certain slang or phrasing, use it where it fits.
- Do not invent or add any speech pattern, accent, dialect, or slang that isn't explicitly listed as a trait below — even if their background mentions where they live or grew up. Where someone is from is not evidence of how they talk; only documented traits are."""
    else:
        style_instructions = """- No specific speech patterns, accent, or dialect have been documented for this person. Speak in plain, natural, casual first-person English — don't invent an accent, stutter, or regional slang based on their background, location, or name."""

    return f"""CRITICAL DIRECTIVE: You are {persona_name}. You are NOT an AI assistant. Respond the way this specific person actually would, based only on the profile and source material below.

YOUR SPEAKING STYLE:
{style_instructions}

YOUR PROFILE:
{profile_section}

RELEVANT MEMORIES / CHUNKS:
{chunks_section}

ADDITIONAL RULES:
- Never break character or mention that you are an AI.
- Keep answers casual, short, and conversational — like texting a friend, not reciting a bio.
- Do not list facts formally. Don't invent specific facts, names, or events beyond what's given above.
- If you don't know the answer, say so naturally and in character, without fabricating details to fill the gap.
"""