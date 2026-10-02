# BrandForge AI: PS-02 AI Content Studio for Brands & Creators

Turns one brief into ready-to-review posts for Instagram, LinkedIn and X in the brand's voice.

## Run
```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key        # Windows PowerShell: $env:GEMINI_API_KEY="your_key"
streamlit run app.py
pytest -q
```
Without a key the app runs in clearly labelled **demo mode** (template output, not AI-written).
Override the model with `GEMINI_MODEL`.

## Features (matches the idea deck)
1. **Brand Voice Engine**: saves past posts; TF-IDF retrieval of the most relevant examples per brief (RAG over the style guide) plus a measurable style fingerprint (sentence length, emoji, exclamations, hashtags).
2. **Multi-platform repurposing**: per-platform prompt rules; code enforces limits (X is hard-capped at 280 characters including hashtags).
3. **Visual prompt generator**: each post comes with an image prompt.
4. **Content calendar**: approved posts get weekday best-time slots; export as CSV.
5. **Human review queue**: every post is edited/approved/rejected by a person before it is scheduled.
6. **Evaluation metrics**: time-to-pack, edit ratio per approved post, human voice rating, matching the baseline in the deck.

## Limitations
- No auto-publishing to social platforms; the calendar is exported for manual or tool-based posting.
- Visual prompts are text for an image model; no images are generated.
- Voice retrieval is keyword-based, not embedding-based.

## Layout
`app.py` UI · `brandforge/voice.py` voice engine · `generator.py` LLM + validation · `scheduler.py` calendar · `db.py` SQLite · `tests/`
