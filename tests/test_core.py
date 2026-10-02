import json
from datetime import date

from brandforge import db, generator, scheduler, voice

SAMPLES = ["Coffee and plants, the cozy corner! ☕ #Brew", "Rainy day, warm cup. ☔ #Cozy",
           "Hand-painted terracotta pots from a local studio. 🌵 #Local"]


def test_retrieval_picks_relevant_sample():
    assert "terracotta" in voice.top_samples("new terracotta pots arrived", SAMPLES, k=1)[0]


def test_retrieval_falls_back_when_no_overlap():
    assert len(voice.top_samples("zzz qqq", SAMPLES, k=2)) == 2


def test_profile_counts():
    p = voice.profile(SAMPLES)
    assert p["emoji_per_post"] == 1.0 and p["hashtags_per_post"] == 1.0


def test_enforce_x_limit_including_hashtags():
    out = generator.enforce("X", {"copy": "a" * 400, "hashtags": ["x", "#y", "z"]})
    assert len(generator.full_text(out)) <= 280 and all(t.startswith("#") for t in out["hashtags"])


def test_parse_json_with_fences():
    assert generator.parse_json('```json\n[{"platform":"X"}]\n```') == [{"platform": "X"}]


def test_demo_pack_shape(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    posts, mode, note = generator.generate_pack("Brew", "Monsoon menu", SAMPLES, ["Instagram", "X"], 2)
    assert mode == "demo" and len(posts) == 4 and note
    assert all(len(generator.full_text(p)) <= generator.PLATFORMS[p["platform"]]["max"] for p in posts)


def test_gemini_path_with_fake_client():
    class R:
        text = json.dumps([{"platform": "LinkedIn", "copy": "Hi", "hashtags": ["a"], "visual_prompt": "v"}])

    class C:
        class models:
            @staticmethod
            def generate_content(**kw):
                return R()

    posts, mode, _ = generator.generate_pack("B", "brief", SAMPLES, ["LinkedIn"], client=C())
    assert mode == "gemini" and posts[0]["hashtags"] == ["#a"]


def test_gemini_path_supports_candidate_payloads():
    class R:
        @property
        def text(self):
            raise AttributeError("not on this SDK response")

        candidates = [{"content": {"parts": [{"text": "```json\n[{\"platform\": \"X\", \"copy\": \"Hi\", \"hashtags\": [\"a\"], \"visual_prompt\": \"v\"}]\n```"}]}}]

    class C:
        class models:
            @staticmethod
            def generate_content(**kw):
                return R()

    posts, mode, _ = generator.generate_pack("B", "brief", SAMPLES, ["X"], client=C())
    assert mode == "gemini" and posts[0]["hashtags"] == ["#a"]


def test_default_model_uses_supported_gemini_name():
    assert generator.MODEL == "gemini-3.8-flash"


def test_scheduler_skips_weekends_and_uses_slots():
    sat = date(2026, 10, 3)
    d = scheduler.slot_for("LinkedIn", 0, sat)
    assert d.weekday() == 0 and d.hour == 9
    assert scheduler.slot_for("Instagram", 1, sat).weekday() == 1


def test_db_roundtrip_and_metrics(tmp_path):
    p = str(tmp_path / "t.db")
    db.add_samples("B", SAMPLES, p)
    assert db.get_samples("B", p) == SAMPLES
    db.add_posts("B", "brief", [{"platform": "X", "copy": "hi", "hashtags": ["#a"], "visual_prompt": "v"}], p)
    pid = db.list_posts("B", path=p)[0]["id"]
    db.update_post(pid, p, status="approved", edit_ratio=0.0, voice_rating=4)
    db.log_run("B", 3.0, 1, "demo", p)
    m = db.metrics("B", p)
    assert m["approved"] == 1 and m["approved_unedited"] == 1 and m["avg_seconds_per_pack"] == 3.0
