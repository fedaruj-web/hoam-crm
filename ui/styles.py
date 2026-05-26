import base64
from pathlib import Path

import streamlit as st

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "hoam_capital_logo.png"


def image_to_base64(path):
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode()


def apply_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --hoam-black: #050505;
        --hoam-graphite: #111111;
        --hoam-gold: #b99545;
        --hoam-gold-light: #d7bd76;
        --hoam-cream: #f7f4ed;
        --hoam-border: #e8e2d6;
        --hoam-muted: #6b665f;
    }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: linear-gradient(135deg, #faf8f3 0%, #ffffff 42%, #f5efe2 100%); }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #000000 0%, #090909 58%, #15120a 100%);
        border-right: 1px solid rgba(185,149,69,0.30);
    }

    section[data-testid="stSidebar"] > div { padding: 1rem .95rem 1.25rem .95rem; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color: #ffffff !important; }
    .hoam-logo { width: 168px; margin: .15rem auto 1rem auto; display: block; }

    .hoam-sidebar-title {
        color: #ffffff;
        font-size: 0.76rem;
        letter-spacing: .12em;
        text-transform: uppercase;
        margin: 1.4rem 0 .4rem 0;
        opacity: .55;
    }

    .hoam-user-card {
        color: #fff;
        border: 1px solid rgba(185,149,69,.45);
        border-radius: 12px;
        padding: .72rem .78rem;
        margin: 0 0 1rem 0;
        background: rgba(255,255,255,.035);
    }

    .hoam-user-name {
        font-weight: 800;
        font-size: .9rem;
        line-height: 1.2;
    }

    .hoam-user-role {
        color: rgba(255,255,255,.62);
        font-size: .73rem;
        margin-top: .12rem;
    }

    .hoam-sidebar-nav { margin-top: .2rem; }
    .hoam-nav-group {
        color: rgba(255,255,255,.52);
        font-size: .66rem;
        letter-spacing: .16em;
        text-transform: uppercase;
        font-weight: 800;
        margin: 1rem 0 .34rem .2rem;
    }

    .hoam-nav-active {
        background: linear-gradient(135deg, rgba(185,149,69,.28), rgba(185,149,69,.10));
        border: 1px solid rgba(215,189,118,.75);
        border-radius: 10px;
        color: #fff;
        font-size: .9rem;
        font-weight: 800;
        line-height: 1.15;
        padding: .54rem .72rem;
        margin: .12rem 0 .16rem 0;
        box-shadow: inset 3px 0 0 var(--hoam-gold);
    }

    .hoam-sidebar-footer {
        border-top: 1px solid rgba(255,255,255,.10);
        margin-top: 1rem;
        padding-top: .85rem;
    }

    section[data-testid="stSidebar"] .stButton { margin: 0 0 .16rem 0; }
    section[data-testid="stSidebar"] .stButton button {
        background: transparent;
        border: 1px solid transparent;
        border-radius: 10px;
        box-shadow: none;
        color: rgba(255,255,255,.86);
        justify-content: flex-start;
        min-height: 2.15rem;
        padding: .48rem .72rem;
        text-align: left;
        font-size: .9rem;
        font-weight: 650;
    }

    section[data-testid="stSidebar"] .stButton button:hover {
        background: rgba(185,149,69,.14);
        border-color: rgba(185,149,69,.32);
        box-shadow: none;
        color: #fff;
    }

    div[role="radiogroup"] label {
        border-radius: 14px;
        padding: .55rem .75rem;
        margin-bottom: .28rem;
        transition: all .15s ease-in-out;
    }

    div[role="radiogroup"] label:hover { background: rgba(185,149,69,0.18); }
    div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child { display: none; }

    .stButton button, .stDownloadButton button {
        background: linear-gradient(135deg, #050505 0%, #1d1a15 100%);
        color: #fff;
        border: 1px solid rgba(185,149,69,0.65);
        border-radius: 13px;
        padding: .55rem 1rem;
        font-weight: 700;
    }

    .stButton button:hover, .stDownloadButton button:hover {
        color: #fff;
        border-color: #d7bd76;
        box-shadow: 0 8px 24px rgba(185,149,69,.18);
    }

    .hoam-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 1.2rem;
        padding: 1.1rem 1.25rem;
        border: 1px solid var(--hoam-border);
        border-radius: 20px;
        background: rgba(255,255,255,.82);
        box-shadow: 0 12px 36px rgba(10,10,10,.05);
    }

    .hoam-title { font-size: 1.55rem; font-weight: 800; color: #060606; margin-bottom: .2rem; }
    .hoam-subtitle { color: var(--hoam-muted); font-size: .95rem; }

    .hoam-pill {
        background: #050505;
        color: #fff;
        border: 1px solid var(--hoam-gold);
        border-radius: 999px;
        padding: .55rem .9rem;
        font-weight: 700;
        font-size: .84rem;
        white-space: nowrap;
    }

    .metric-card, .hoam-card, [data-testid="stMetric"] {
        background: rgba(255,255,255,.9);
        border: 1px solid var(--hoam-border);
        border-radius: 18px;
        box-shadow: 0 12px 32px rgba(0,0,0,.055);
    }

    .metric-card { padding: 1.15rem 1.18rem; min-height: 132px; }
    .metric-label { color: #1a1714; font-size: .87rem; font-weight: 700; margin-bottom: .65rem; }
    .metric-value { color: #050505; font-size: clamp(1.35rem, 2.3vw, 2rem); font-weight: 800; line-height: 1; overflow-wrap: anywhere; }
    .metric-foot { color: var(--hoam-gold); font-size: .78rem; font-weight: 700; margin-top: .7rem; }

    .hoam-card { padding: 1.25rem; margin-bottom: 1rem; }
    .hoam-card.compact-action {
        padding: .75rem .9rem;
        margin: .75rem 0 1rem 0;
        border-left: 4px solid var(--hoam-gold);
    }
    .hoam-card h3 { margin-top: 0; font-size: 1.05rem; }

    .funnel-step {
        background: #fff;
        border: 1px solid var(--hoam-border);
        border-left: 5px solid var(--hoam-gold);
        border-radius: 14px;
        padding: .95rem;
        min-height: 112px;
        box-shadow: 0 10px 22px rgba(0,0,0,.045);
    }

    .funnel-stage { font-weight: 800; color: #090909; font-size: .95rem; min-height: 42px; }
    .funnel-count { font-weight: 800; font-size: 1.55rem; color: #050505; }
    .funnel-value { color: var(--hoam-muted); font-size: .82rem; font-weight: 700; }

    hr { border-color: var(--hoam-border); }
    [data-testid="stMetric"] { padding: 1rem; }
    [data-testid="stMetricValue"] { color: #050505; font-weight: 800; }
    [data-testid="stMetricLabel"] { color: #211d17; font-weight: 700; }
    div[data-testid="stDataFrame"] { border: 1px solid var(--hoam-border); border-radius: 16px; overflow: hidden; }
    div[data-baseweb="input"], div[data-baseweb="select"] { border-radius: 13px; }
    section.main > div { padding-top: 1.5rem; }
    h1, h2, h3 { color: #070707; }

    @media (max-width: 760px) {
        .hoam-header { align-items: flex-start; flex-direction: column; border-radius: 16px; }
        .hoam-title { font-size: 1.3rem; }
        .hoam-pill { white-space: normal; }
    }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar_brand(user=None):
    logo_b64 = image_to_base64(LOGO_PATH)
    if logo_b64:
        st.sidebar.markdown(f'<img class="hoam-logo" src="data:image/png;base64,{logo_b64}">', unsafe_allow_html=True)
    else:
        st.sidebar.markdown("## Hoam Capital")

    if user:
        st.sidebar.markdown(f"""
        <div class="hoam-user-card">
            <div class="hoam-user-name">{user['name']}</div>
            <div class="hoam-user-role">{user['role']}</div>
        </div>
        """, unsafe_allow_html=True)


def header(title, subtitle):
    st.markdown(f"""
    <div class="hoam-header">
        <div>
            <div class="hoam-title">{title}</div>
            <div class="hoam-subtitle">{subtitle}</div>
        </div>
        <div class="hoam-pill">Hoam Capital</div>
    </div>
    """, unsafe_allow_html=True)


def metric_card(label, value, foot):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-foot">{foot}</div>
    </div>
    """, unsafe_allow_html=True)
