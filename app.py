"""BrandForge AI: one brief -> on-brand content pack, human-approved, scheduled."""
import json
import time
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import streamlit as st

from brandforge import db, generator, scheduler, voice

st.set_page_config(page_title="BrandForge AI", page_icon="🔨", layout="wide")
st.markdown(
    """
    <style>
    .main { background: #0f172a; }
    div[data-testid="stSidebar"] { background: #171d2c; }
    div[data-testid="stStatusWidget"] > div { background: rgba(255,255,255,0.03); }
    .stTabs [role="tablist"] button { border-radius: 10px 10px 0 0; }
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "generated_posts" not in st.session_state:
    st.session_state.generated_posts = []
if "last_mode" not in st.session_state:
    st.session_state.last_mode = "demo"
if "last_note" not in st.session_state:
    st.session_state.last_note = ""

st.title("🔨 BrandForge AI")
st.caption("One brief in, on-brand posts out. Nothing is scheduled until a human approves it.")

with st.sidebar:
    brand = st.text_input("Brand name", "Brew & Bloom")
    week_start = st.date_input("Calendar week starts", date.today())
    st.markdown(f"**Model:** `{generator.MODEL}`")
    st.markdown("---")
    st.caption("Quick actions")
    if st.button("Load demo brief"):
        st.session_state.generated_brief = "Launching a monsoon menu: masala chai latte and filter coffee cold brew."
        st.rerun()
    if st.button("Clear draft preview"):
        st.session_state.generated_posts = []
        st.rerun()

if "generated_brief" not in st.session_state:
    st.session_state.generated_brief = ""

tab_voice, tab_create, tab_review, tab_cal, tab_metrics = st.tabs(
    ["1. Brand voice", "2. Create", "3. Review queue", "4. Calendar", "5. Metrics"])

# ---------- 1. Brand voice ----------
with tab_voice:
    samples = db.get_samples(brand)
    st.write(f"{len(samples)} voice samples saved for **{brand}**.")
    pasted = st.text_area("Paste past posts, separated by a line containing only ---", height=180)
    up = st.file_uploader("...or upload a .txt file (same separator)", type="txt")
    c1, c2, c3 = st.columns(3)
    if c1.button("Save samples"):
        text = pasted + ("\n---\n" + up.read().decode("utf-8", "ignore") if up else "")
        db.add_samples(brand, [t for t in text.split("\n---\n")])
        st.rerun()
    if c2.button("Load demo samples"):
        demo = json.loads(Path("sample_data/brand_samples.json").read_text(encoding="utf-8"))
        db.add_samples(brand, demo["samples"])
        st.rerun()
    if c3.button("Clear samples"):
        db.clear_samples(brand)
        st.rerun()
    if samples:
        st.subheader("Style fingerprint")
        st.json(voice.profile(samples))

# ---------- 2. Create ----------
with tab_create:
    brief = st.text_area(
        "Brief, product, or topic",
        value=st.session_state.generated_brief,
        height=140,
        placeholder="Launching a monsoon menu: masala chai latte and filter coffee cold brew, from 1 July.",
    )
    st.session_state.generated_brief = brief

    plats = st.multiselect("Platforms", list(generator.PLATFORMS), default=list(generator.PLATFORMS))
    variants = st.slider("Variants per platform", 1, 3, 1)
    if st.button("Generate content pack", type="primary", disabled=not (brief.strip() and plats)):
        t0 = time.time()
        with st.status("Writing in your brand voice...", expanded=True) as status:
            progress = st.progress(0)
            progress.progress(25)
            posts, mode, note = generator.generate_pack(brand, brief, db.get_samples(brand), plats, variants)
            progress.progress(100)
            status.update(label=f"Generated {len(posts)} drafts in {time.time() - t0:.1f}s", state="complete")

        secs = time.time() - t0
        db.add_posts(brand, brief, posts)
        db.log_run(brand, secs, len(posts), mode)
        st.session_state.generated_posts = posts
        st.session_state.last_mode = mode
        st.session_state.last_note = note
        (st.success if mode == "gemini" else st.warning)(
            f"{len(posts)} drafts in {secs:.1f}s ({mode} mode). {note} Go to the Review queue.")

    if st.session_state.generated_posts:
        st.markdown("---")
        st.subheader("Generated preview")
        for p in st.session_state.generated_posts:
            with st.container(border=True):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"**{p['platform']}**")
                    st.write(p["copy"])
                    st.caption("Visual prompt: " + p["visual_prompt"])
                with c2:
                    st.code(" ".join(p["hashtags"]) or "No hashtags")
                    st.caption(f"Length: {len(generator.full_text(p))} chars")

# ---------- 3. Review queue ----------
with tab_review:
    drafts = db.list_posts(brand, "draft")
    if not drafts:
        st.info("No drafts waiting for review.")
    for p in drafts:
        limit = generator.PLATFORMS[p["platform"]]["max"]
        with st.container(border=True):
            st.markdown(f"**{p['platform']}** · draft #{p['id']}")
            copy = st.text_area("Copy", p["copy"], key=f"c{p['id']}", height=120)
            tags = st.text_input("Hashtags", p["hashtags"], key=f"h{p['id']}")
            st.text_area("Visual prompt", p["visual_prompt"], key=f"v{p['id']}", height=70)
            total = len(copy) + len(tags) + 2
            (st.caption if total <= limit else st.error)(f"{total}/{limit} characters")
            rating = st.slider("Brand-voice match (1-5)", 1, 5, 3, key=f"r{p['id']}")
            a, r = st.columns(2)
            if a.button("Approve & schedule", key=f"a{p['id']}", disabled=total > limit):
                n = sum(1 for x in db.list_posts(brand, "approved") if x["platform"] == p["platform"])
                db.update_post(
                    p["id"], copy=copy, hashtags=tags, status="approved", voice_rating=rating,
                    visual_prompt=st.session_state[f"v{p['id']}"],
                    edit_ratio=round(1 - SequenceMatcher(None, p["original_copy"], copy).ratio(), 3),
                    scheduled_for=scheduler.slot_for(p["platform"], n, week_start).isoformat())
                st.rerun()
            if r.button("Reject", key=f"x{p['id']}"):
                db.update_post(p["id"], status="rejected", voice_rating=rating)
                st.rerun()

# ---------- 4. Calendar ----------
with tab_cal:
    approved = db.list_posts(brand, "approved")
    if not approved:
        st.info("Approve posts to fill the calendar.")
    else:
        df = pd.DataFrame(approved)[["scheduled_for", "platform", "copy", "hashtags", "visual_prompt"]]
        df = df.sort_values("scheduled_for")
        df["day"] = df["scheduled_for"].str[:10]
        grid = df.pivot_table(index="day", columns="platform", values="copy", aggfunc=lambda s: " | ".join(x[:60] for x in s))
        st.subheader("Week at a glance")
        st.dataframe(grid.fillna(""), width="stretch")
        st.subheader("All scheduled posts")
        st.dataframe(df.drop(columns="day"), width="stretch")
        st.download_button("Download calendar (CSV)", df.drop(columns="day").to_csv(index=False),
                           "content_calendar.csv", "text/csv")
        st.caption("Posting is manual: export the CSV or copy from here. No auto-publishing.")

# ---------- 5. Metrics ----------
with tab_metrics:
    m = db.metrics(brand)
    c = st.columns(4)
    c[0].metric("Avg time to content pack", f"{m['avg_seconds_per_pack']:.1f}s" if m["avg_seconds_per_pack"] else "n/a")
    c[1].metric("Posts approved", f"{m['approved']}/{m['posts']}")
    c[2].metric("Avg edit ratio (approved)", f"{m['avg_edit_ratio']:.0%}" if m["avg_edit_ratio"] is not None else "n/a")
    c[3].metric("Avg voice rating", f"{m['avg_voice_rating']:.1f}/5" if m["avg_voice_rating"] else "n/a")
    st.caption("Edit ratio = share of the AI draft changed by the reviewer (0% = approved as-is). "
               "Compare time-to-pack against your manual baseline (~2.5 hrs from the idea deck).")
