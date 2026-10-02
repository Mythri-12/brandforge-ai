"""Brand Voice Engine: retrieve the most relevant past posts (lightweight RAG) and
compute a measurable style fingerprint from them."""
import math
import re
from collections import Counter

EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def tokens(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def top_samples(brief, samples, k=3):
    """TF-IDF-weighted overlap between the brief and each sample; falls back to latest samples."""
    if not samples:
        return []
    docs = [Counter(tokens(s)) for s in samples]
    df = Counter(w for d in docs for w in d)
    q = Counter(tokens(brief))
    n = len(docs)

    def score(d):
        return sum(q[w] * d[w] * math.log(1 + n / df[w]) for w in q if w in d)

    ranked = sorted(range(n), key=lambda i: score(docs[i]), reverse=True)
    if score(docs[ranked[0]]) == 0:
        ranked = list(range(n))[::-1]
    return [samples[i] for i in ranked[:k]]


def profile(samples):
    """Style fingerprint injected into the prompt."""
    if not samples:
        return {"avg_words_per_sentence": 0, "emoji_per_post": 0,
                "exclamations_per_post": 0, "hashtags_per_post": 0}
    n = len(samples)
    sentences = [s for t in samples for s in re.split(r"[.!?]+\s", t) if s.strip()]
    words = sum(len(tokens(s)) for s in sentences)
    return {
        "avg_words_per_sentence": round(words / max(len(sentences), 1), 1),
        "emoji_per_post": round(sum(len(EMOJI.findall(t)) for t in samples) / n, 1),
        "exclamations_per_post": round(sum(t.count("!") for t in samples) / n, 1),
        "hashtags_per_post": round(sum(t.count("#") for t in samples) / n, 1),
    }


def describe(p):
    return (f"about {p['avg_words_per_sentence']} words per sentence, "
            f"{p['emoji_per_post']} emoji and {p['exclamations_per_post']} exclamation marks "
            f"per post on average")
