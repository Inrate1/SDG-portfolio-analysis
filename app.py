import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SDG Portfolio Analyser",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
div[data-testid="metric-container"] {
    background: #f7f6f2;
    border: 1px solid rgba(0,0,0,0.07);
    border-radius: 10px;
    padding: 14px 18px !important;
}
div[data-testid="metric-container"] label {
    font-size: 11px !important; color: #5a6b58 !important;
    text-transform: uppercase; letter-spacing: .04em;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-size: 22px !important; font-weight: 600 !important;
}
.nav-header {
    background: #0d2818; color: white;
    padding: 14px 24px; border-radius: 12px; margin-bottom: 1.5rem;
    display: flex; align-items: center; gap: 14px;
}
.nav-title { font-family: 'DM Serif Display', serif; font-size: 22px; margin: 0; }
.nav-sub   { font-size: 11px; color: rgba(255,255,255,0.5); margin: 0; }
.format-hint {
    background: #f7f6f2; border: 1px solid rgba(0,0,0,0.07);
    border-radius: 8px; padding: 12px 16px;
    font-size: 12px; color: #5a6b58; line-height: 1.9;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
SDG_NAMES = [
    "No Poverty","Zero Hunger","Good Health & Well-being","Quality Education",
    "Gender Equality","Clean Water & Sanitation","Affordable & Clean Energy",
    "Decent Work & Growth","Industry & Innovation","Reduced Inequalities",
    "Sustainable Cities","Responsible Consumption","Climate Action",
    "Life Below Water","Life on Land","Peace & Justice","Partnerships",
]
SDG_LABELS = [f"SDG {i+1}" for i in range(17)]

CA, CB, CC, CD       = "#1B5E20", "#66BB6A", "#FFA726", "#B71C1C"
CBA, CBB, CBC, CBD   = "#004D40", "#80CBC4", "#FFCC02", "#7B1FA2"

# ── Data helpers ──────────────────────────────────────────────────────────────
def clean_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise columns and drop non-holding rows (sector summaries etc.)."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce")
    df = df.dropna(subset=["Weight"])
    df = df[df["Weight"] > 0].reset_index(drop=True)
    # Coerce all SDG columns to numeric
    for s in range(1, 18):
        for lv in ["A", "B", "C", "D"]:
            col = f"{s}_{lv}"
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def compute_weighted(df: pd.DataFrame) -> dict:
    total_w = df["Weight"].sum()
    res = {}
    for s in range(1, 18):
        res[s] = {}
        for lv in ["A", "B", "C", "D"]:
            col = f"{s}_{lv}"
            vals = df[col] if col in df.columns else pd.Series(0.0, index=df.index)
            res[s][lv] = float((vals * df["Weight"] / total_w).sum())
    return res


def get_summary(w: dict) -> dict:
    vp  = sum(w[s]["A"] for s in range(1, 18)) / 17
    pos = sum(w[s]["B"] for s in range(1, 18)) / 17
    neg = sum(w[s]["C"] for s in range(1, 18)) / 17
    vn  = sum(w[s]["D"] for s in range(1, 18)) / 17
    return {"vp": vp, "pos": pos, "neg": neg, "vn": vn}


def build_holdings(df: pd.DataFrame) -> pd.DataFrame:
    name_col = "Security Name" if "Security Name" in df.columns else "Company Name"
    total_w  = df["Weight"].sum()
    rows = []
    for _, row in df.iterrows():
        ap = sum(row.get(f"{s}_A", 0) + row.get(f"{s}_B", 0) for s in range(1, 18)) / 17
        an = sum(row.get(f"{s}_C", 0) + row.get(f"{s}_D", 0) for s in range(1, 18)) / 17
        rows.append({
            "Name":      row[name_col],
            "Sector":    row.get("Inrate Sector", ""),
            "Weight %":  round(row["Weight"] / total_w * 100, 2),
            "Avg pos %": round(ap, 2),
            "Avg neg %": round(an, 2),
        })
    return pd.DataFrame(rows).sort_values("Weight %", ascending=False).reset_index(drop=True)


# ── Chart builders ────────────────────────────────────────────────────────────
def profile_chart(pf_w: dict) -> go.Figure:
    fig = go.Figure()
    for name, color, key, sign in [
        ("Very positive (A)", CA, "A",  1),
        ("Positive (B)",      CB, "B",  1),
        ("Negative (C)",      CC, "C", -1),
        ("Very negative (D)", CD, "D", -1),
    ]:
        vals = [sign * pf_w[s][key] for s in range(1, 18)]
        fig.add_trace(go.Bar(
            name=name, x=SDG_LABELS, y=vals, marker_color=color,
            customdata=[abs(v) for v in vals],
            hovertemplate="%{x} — " + name + "<br>%{customdata:.2f}%<extra></extra>",
        ))
    _common_layout(fig)
    return fig


def compare_chart(pf_w: dict, bm_w: dict) -> go.Figure:
    fig = go.Figure()
    n   = 17
    x_pf = list(range(n))
    x_bm = [x + 0.4 for x in x_pf]
    tick_x = [x + 0.2 for x in x_pf]
    for name, color, source, xs, sign in [
        ("PF — very positive (A)", CA,  pf_w, x_pf,  1),
        ("PF — positive (B)",      CB,  pf_w, x_pf,  1),
        ("PF — negative (C)",      CC,  pf_w, x_pf, -1),
        ("PF — very negative (D)", CD,  pf_w, x_pf, -1),
        ("BM — very positive (A)", CBA, bm_w, x_bm,  1),
        ("BM — positive (B)",      CBB, bm_w, x_bm,  1),
        ("BM — negative (C)",      CBC, bm_w, x_bm, -1),
        ("BM — very negative (D)", CBD, bm_w, x_bm, -1),
    ]:
        key   = name.split("(")[-1].rstrip(")")
        vals  = [sign * source[s][key] for s in range(1, 18)]
        stack = "pf" if xs is x_pf else "bm"
        fig.add_trace(go.Bar(
            name=name, x=xs, y=vals, marker_color=color,
            offsetgroup=stack, width=0.38,
            customdata=[abs(v) for v in vals],
            text=[f"SDG {i+1}" for i in range(n)],
            hovertemplate="%{text} — " + name + "<br>%{customdata:.2f}%<extra></extra>",
        ))
    _common_layout(fig)
    fig.update_layout(
        xaxis=dict(tickmode="array", tickvals=tick_x, ticktext=SDG_LABELS, gridcolor="rgba(0,0,0,0)"),
        height=430,
    )
    return fig


def _common_layout(fig: go.Figure):
    fig.update_layout(
        barmode="relative",
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Revenue share (%)", ticksuffix="%",
                   gridcolor="#ececec", zeroline=True, zerolinecolor="#ccc"),
        xaxis=dict(gridcolor="rgba(0,0,0,0)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0, font_size=11),
        margin=dict(l=10, r=10, t=48, b=10),
        height=400,
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    st.markdown("""
    <div class="nav-header">
        <div style="font-size:30px">🌍</div>
        <div>
            <p class="nav-title">SDG Portfolio Analyser</p>
            <p class="nav-sub">Sustainable Development Goals · Impact Analysis</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("### 📂 Upload portfolio")
        uploaded = st.file_uploader(
            "Excel file (.xlsx)",
            type=["xlsx", "xls"],
            help='Needs sheets "Portfolio" and "SPI" with columns Weight, Security Name / Company Name, Inrate Sector, and 1_A … 17_D.',
        )
        st.markdown("""
        <div class="format-hint">
        <strong>Required format</strong><br/>
        Sheets: <code>Portfolio</code> and <code>SPI</code><br/>
        Columns: <code>Weight</code>, <code>Security Name</code>,
        <code>Inrate Sector</code>,<br/>
        then <code>1_A</code> <code>1_B</code> <code>1_C</code> <code>1_D</code>
        … <code>17_D</code><br/>
        A = very positive &nbsp;·&nbsp; B = positive<br/>
        C = negative &nbsp;·&nbsp; D = very negative<br/>
        Values = revenue share (0–100%) per holding
        </div>
        """, unsafe_allow_html=True)

    # Landing
    if uploaded is None:
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("### Get started")
            st.info("Upload your Inrate-format Excel file from the sidebar to analyse SDG contributions across all 17 goals and compare against your benchmark.", icon="⬅️")
        with c2:
            st.markdown("### What you'll see")
            for icon, title, desc in [
                ("📊", "SDG Profile",    "Weighted revenue share per SDG — A/B/C/D stacked"),
                ("⚖️", "vs Benchmark",   "Side-by-side comparison (portfolio vs SPI)"),
                ("🔍", "Gap Analysis",   "Table of out- and underperformance per SDG"),
                ("🏢", "Holdings",       "All constituents ranked by weight"),
            ]:
                st.markdown(f"**{icon} {title}** — {desc}")
        return

    # Parse
    try:
        xls = pd.ExcelFile(uploaded)
    except Exception as e:
        st.error(f"Cannot open file: {e}")
        return

    for sheet in ["Portfolio", "SPI"]:
        if sheet not in xls.sheet_names:
            st.error(f'Sheet "{sheet}" not found. Available sheets: {", ".join(xls.sheet_names)}')
            return

    try:
        pf_raw  = clean_sheet(pd.read_excel(xls, "Portfolio"))
        spi_raw = clean_sheet(pd.read_excel(xls, "SPI"))
        for df in [pf_raw, spi_raw]:
            if "Company Name" in df.columns and "Security Name" not in df.columns:
                df.rename(columns={"Company Name": "Security Name"}, inplace=True)

        pf_w   = compute_weighted(pf_raw)
        bm_w   = compute_weighted(spi_raw)
        pf_sum = get_summary(pf_w)
        bm_sum = get_summary(bm_w)

    except Exception as e:
        st.error(f"Could not parse data: {e}")
        return

    # Summary metrics
    pf_pos   = pf_sum["vp"] + pf_sum["pos"]
    pf_neg   = pf_sum["neg"] + pf_sum["vn"]
    bm_pos   = bm_sum["vp"] + bm_sum["pos"]
    bm_neg   = bm_sum["neg"] + bm_sum["vn"]
    diff_pos = pf_pos - bm_pos
    diff_neg = pf_neg - bm_neg

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total positive impact",   f"{pf_pos:.2f}%",
              f"VP {pf_sum['vp']:.2f}%  ·  P {pf_sum['pos']:.2f}%")
    c2.metric("Total negative impact",   f"{pf_neg:.2f}%",
              f"N {pf_sum['neg']:.2f}%  ·  VN {pf_sum['vn']:.2f}%",
              delta_color="inverse")
    c3.metric("vs Benchmark — positive", f"{diff_pos:+.2f}%",
              f"Benchmark: {bm_pos:.2f}%",
              delta_color="normal" if diff_pos >= 0 else "inverse")
    c4.metric("vs Benchmark — negative", f"{diff_neg:+.2f}%",
              f"Benchmark: {bm_neg:.2f}%",
              delta_color="inverse" if diff_neg > 0 else "normal")

    st.markdown("<br/>", unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊  SDG Profile", "⚖️  vs Benchmark", "🔍  Gap Analysis", "🏢  Holdings"
    ])

    with tab1:
        st.caption("Bars above zero = positive contribution. Bars below zero = negative. Hover for exact values.")
        st.plotly_chart(profile_chart(pf_w), use_container_width=True)

    with tab2:
        st.caption("Left bar = portfolio, right bar = SPI benchmark. Stacked A/B positive above, C/D negative below.")
        st.plotly_chart(compare_chart(pf_w, bm_w), use_container_width=True)

    with tab3:
        st.caption("Net pos = A+B. Net neg = C+D. Green gap = portfolio outperforming benchmark.")
        rows = []
        for i, name in enumerate(SDG_NAMES):
            s  = i + 1
            pp = pf_w[s]["A"] + pf_w[s]["B"]
            bp = bm_w[s]["A"] + bm_w[s]["B"]
            pn = pf_w[s]["C"] + pf_w[s]["D"]
            bn = bm_w[s]["C"] + bm_w[s]["D"]
            rows.append({
                "SDG":        f"SDG {s}",
                "Goal":       name,
                "PF pos %":   round(pp, 2),
                "BM pos %":   round(bp, 2),
                "Δ pos":      round(pp - bp, 2),
                "PF neg %":   round(pn, 2),
                "BM neg %":   round(bn, 2),
                "Δ neg":      round(pn - bn, 2),
            })
        gap_df = pd.DataFrame(rows)

        def _clr_pos(v):
            return "color:#1b5e20;font-weight:600" if v > 0 else ("color:#b71c1c;font-weight:600" if v < 0 else "")
        def _clr_neg(v):
            return "color:#1b5e20;font-weight:600" if v < 0 else ("color:#b71c1c;font-weight:600" if v > 0 else "")

        styled = (
            gap_df.style
            .applymap(_clr_pos, subset=["Δ pos"])
            .applymap(_clr_neg, subset=["Δ neg"])
            .format({"PF pos %": "{:.2f}%", "BM pos %": "{:.2f}%", "Δ pos": "{:+.2f}%",
                     "PF neg %": "{:.2f}%", "BM neg %": "{:.2f}%", "Δ neg": "{:+.2f}%"})
        )
        st.dataframe(styled, use_container_width=True, height=640)

    with tab4:
        st.caption("Ranked by portfolio weight. Avg pos/neg = average across all 17 SDGs.")
        h_df = build_holdings(pf_raw)

        def _cp(v): return "color:#1b5e20;font-weight:500" if v > 0 else "color:#9aaa98"
        def _cn(v): return "color:#b71c1c;font-weight:500" if v > 0 else "color:#9aaa98"

        styled_h = (
            h_df.style
            .applymap(_cp, subset=["Avg pos %"])
            .applymap(_cn, subset=["Avg neg %"])
            .format({"Weight %": "{:.1f}%", "Avg pos %": "{:.2f}%", "Avg neg %": "{:.2f}%"})
            .bar(subset=["Weight %"], color="#c8e6c9", vmin=0)
        )
        st.dataframe(styled_h, use_container_width=True, height=700)
        csv = h_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download holdings CSV", csv, "holdings.csv", "text/csv")


if __name__ == "__main__":
    main()
