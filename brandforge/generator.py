"""One brief -> on-brand, platform-ready posts. Gemini when a key is set, offline demo mode otherwise."""
import json
import os
import re
import time

from . import voice

PLATFORMS = {
    "Instagram": {"max": 2200, "tags": (5, 10), "style": "visual, warm, line breaks, a call to action"},
    "LinkedIn": {"max": 3000, "tags": (3, 5), "style": "professional, insight-led, short paragraphs"},
    "X": {"max": 280, "tags": (1, 2), "style": "punchy, one idea, under 280 characters including hashtags"},
}
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def full_text(post):
    return post["copy"] + ("\n\n" + " ".join(post["hashtags"]) if post["hashtags"] else "")


def enforce(platform, post):
    """Normalise model output and guarantee platform limits."""
    hi = PLATFORMS[platform]["tags"][1]
    tags = [t if t.startswith("#") else "#" + t.lstrip("#")
            for t in map(str, post.get("hashtags", [])) if t.strip("# ")][:hi]
    out = {"platform": platform, "copy": str(post.get("copy", "")).strip(),
           "hashtags": tags, "visual_prompt": str(post.get("visual_prompt", "")).strip()}
    limit = PLATFORMS[platform]["max"]
    while len(full_text(out)) > limit and out["hashtags"]:
        out["hashtags"].pop()
    if len(full_text(out)) > limit:
        out["copy"] = out["copy"][: limit - 1].rstrip() + "…"
    return out


def _response_text(resp):
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp

    for attr in ("text", "output_text"):
        try:
            value = getattr(resp, attr)
        except (AttributeError, TypeError):
            continue
        if value:
            return str(value)

    try:
        parsed = resp.parsed
    except AttributeError:
        parsed = None
    if parsed is not None:
        return json.dumps(parsed, ensure_ascii=False)

    candidates = getattr(resp, "candidates", None) or []
    for candidate in candidates:
        if isinstance(candidate, dict):
            content = candidate.get("content") or {}
        else:
            content = getattr(candidate, "content", None) or {}

        if isinstance(content, dict):
            parts = content.get("parts") or []
        else:
            parts = getattr(content, "parts", None) or []

        for part in parts:
            if isinstance(part, dict):
                text = part.get("text")
            else:
                text = getattr(part, "text", None)
            if text:
                return str(text)

    return ""


def parse_json(text):
    if not text:
        raise ValueError("No response content to parse")
    if isinstance(text, (list, dict)):
        return text

    text = str(text).strip()
    text = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()

    for candidate in (text, re.sub(r"^[^\[]+", "", text), re.sub(r"[^\]]+$", "", text)):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        for match in re.finditer(r"(\[[\s\S]*\]|\{[\s\S]*\})", candidate):
            snippet = match.group(1)
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                continue

    raise ValueError("No JSON array/object found in model output")


def build_prompt(brand, brief, examples, prof, platforms, variants):
    shots = "\n---\n".join(examples) or "(no samples provided)"
    rules = "\n".join(f"- {p}: {PLATFORMS[p]['style']}; max {PLATFORMS[p]['max']} chars; "
                      f"{PLATFORMS[p]['tags'][0]}-{PLATFORMS[p]['tags'][1]} hashtags" for p in platforms)
    return f"""You are the social media writer for the brand "{brand}".
Write in the brand's voice. Past posts that show the voice:
{shots}
Style fingerprint: {voice.describe(prof)}.

Brief:
{brief}

Create {variants} post(s) for each platform:
{rules}
Do not invent facts, prices, discounts or claims that are not in the brief.
Return ONLY a JSON array. Each item: {{"platform": str, "copy": str, "hashtags": [str], "visual_prompt": str}}.
visual_prompt describes a matching image in one or two sentences."""


def _demo(brand, brief, platforms, variants, prof):
    topic = brief.strip().splitlines()[0][:140].rstrip(".")
    spark = " ✨" if prof["emoji_per_post"] >= 1 else ""
    bang = "!" if prof["exclamations_per_post"] >= 1 else "."
    posts = []
    for plat in platforms:
        for v in range(variants):
            posts.append({
                "platform": plat,
                "copy": f"{brand}: {topic}{bang}{spark} (variant {v + 1}, demo mode)",
                "hashtags": ["#" + re.sub(r"\W", "", brand), "#new", "#community"][: PLATFORMS[plat]["tags"][1]],
                "visual_prompt": f"Clean on-brand graphic for {brand} featuring: {topic}.",
            })
    return posts


def generate_pack(brand, brief, samples, platforms, variants=1, client=None):
    """Returns (posts, mode, note). mode is 'gemini' or 'demo'."""
    prof = voice.profile(samples)
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    note = ""
    posts, mode = None, "demo"
    if client or key:
        try:
            if client is None:
                from google import genai
                client = genai.Client(api_key=key)
            prompt = build_prompt(brand, brief, voice.top_samples(brief, samples), prof, platforms, variants)
            for _ in range(2):  # one retry on malformed JSON
                try:
                    resp = client.models.generate_content(
                        model=MODEL, contents=prompt,
                        config={"response_mime_type": "application/json"})
                    payload = parse_json(_response_text(resp))
                    if isinstance(payload, dict):
                        payload = payload.get("posts", [payload])
                    posts, mode = payload, "gemini"
                    break
                except (AttributeError, TypeError, ValueError, KeyError):
                    time.sleep(0.5)
            if posts is None:
                note = "Model returned invalid JSON twice; used demo mode."
        except Exception as e:  # network/auth/quota
            note = f"Gemini call failed ({type(e).__name__}); used demo mode."
    else:
        note = "No GEMINI_API_KEY set; running in demo mode (template output, not AI-written)."
    if posts is None:
        posts = _demo(brand, brief, platforms, variants, prof)
    clean = [enforce(p["platform"], p) for p in posts if p.get("platform") in PLATFORMS]
    return clean, mode, note
