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

CA, CB, CC, CD       = "#1B5E20", "#66BB6A", "#f4a0a0", "#B71C1C"
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


def compute_sector_weighted(df: pd.DataFrame) -> dict:
    """Returns {sector: {sdg: {A,B,C,D}}} weighted by holding weight within sector."""
    df = df.copy()
    sectors = df["Inrate Sector"].dropna().unique()
    result = {}
    for sector in sectors:
        s_df = df[df["Inrate Sector"] == sector]
        result[sector] = compute_weighted(s_df)
    return result


def build_sector_summary(sector_w: dict) -> pd.DataFrame:
    """Returns a DataFrame with sector-level net pos/neg averaged across 17 SDGs."""
    rows = []
    for sector, w in sector_w.items():
        net_pos = sum(w[s]["A"] + w[s]["B"] for s in range(1, 18)) / 17
        net_neg = sum(w[s]["C"] + w[s]["D"] for s in range(1, 18)) / 17
        rows.append({"Sector": sector, "Net pos %": round(net_pos, 2), "Net neg %": round(net_neg, 2)})
    return pd.DataFrame(rows).sort_values("Net pos %", ascending=False).reset_index(drop=True)


def compute_sector_weights(df: pd.DataFrame) -> dict:
    """Returns {sector: weight_pct} as % of total portfolio."""
    total_w = df["Weight"].sum()
    result = {}
    for sector, grp in df.groupby("Inrate Sector"):
        result[sector] = round(grp["Weight"].sum() / total_w * 100, 1)
    return result


# ── Chart builders ────────────────────────────────────────────────────────────
def profile_chart(pf_w: dict) -> go.Figure:
    fig = go.Figure()
    for name, color, key, sign in [
        ("Positive (B)",      CB, "B",  1),
        ("Very positive (A)", CA, "A",  1),
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
    n = 17

    # Same colors as SDG Profile chart
    COLOR_VP = CA    # very positive — dark green
    COLOR_P  = CB    # positive — light green
    COLOR_N  = CC    # negative — orange/salmon
    COLOR_VN = CD    # very negative — dark red

    # y positions: PF top row, BM bottom row per SDG group
    # Groups spaced 3 apart, PF/BM 0.55 apart within group
    y_pf    = [(n - i) * 3 + 0.55 for i in range(n)]
    y_bm    = [(n - i) * 3 - 0.55 for i in range(n)]
    y_ticks = [(n - i) * 3        for i in range(n)]
    y_labels = [f"{i+1}  {SDG_NAMES[i]}" for i in range(n)]

    first_shown = set()
    for label, color, source, ys, key, sign in [
        ("Positive (B)",      COLOR_P,  pf_w, y_pf, "B",  1),
        ("Very positive (A)", COLOR_VP, pf_w, y_pf, "A",  1),
        ("Negative (C)",      COLOR_N,  pf_w, y_pf, "C", -1),
        ("Very negative (D)", COLOR_VN, pf_w, y_pf, "D", -1),
        ("Positive (B)",      COLOR_P,  bm_w, y_bm, "B",  1),
        ("Very positive (A)", COLOR_VP, bm_w, y_bm, "A",  1),
        ("Negative (C)",      COLOR_N,  bm_w, y_bm, "C", -1),
        ("Very negative (D)", COLOR_VN, bm_w, y_bm, "D", -1),
    ]:
        vals = [sign * source[s][key] for s in range(1, 18)]
        text_vals = [f"{abs(v):.1f}%" if abs(v) >= 1.5 else "" for v in vals]
        is_pf = ys is y_pf
        row = "PF" if is_pf else "BM"
        show_legend = label not in first_shown
        if show_legend:
            first_shown.add(label)
        txt_color = "white" if color in [COLOR_VP, COLOR_VN] else "white"
        fig.add_trace(go.Bar(
            name=label,
            x=vals,
            y=ys,
            orientation="h",
            marker_color=color,
            marker_line_width=0,
            width=0.9,
            text=text_vals,
            textposition="inside",
            textfont=dict(size=11, color=txt_color),
            customdata=[[abs(v), f"SDG {i+1}", row] for i, v in enumerate(vals)],
            hovertemplate="%{customdata[1]} %{customdata[2]} — " + label +
                          "<br>%{customdata[0]:.2f}%<extra></extra>",
            legendgroup=label,
            showlegend=show_legend,
        ))

    # PF / BM labels repeated for every SDG row
    for i in range(n):
        fig.add_annotation(
            x=-26, y=y_pf[i], text="<b>PF</b>", showarrow=False,
            font=dict(size=9, color="#888"), xanchor="right", xref="x", yref="y"
        )
        fig.add_annotation(
            x=-26, y=y_bm[i], text="<b>BM</b>", showarrow=False,
            font=dict(size=9, color="#666"), xanchor="right", xref="x", yref="y"
        )

    fig.update_layout(
        barmode="relative",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=max(700, n * 72),
        margin=dict(l=20, r=20, t=30, b=100),
        xaxis=dict(
            title="Weighted Revenue Share (%)",
            ticksuffix="%",
            gridcolor="rgba(128,128,128,0.15)",
            zeroline=True,
            zerolinecolor="#888",
            zerolinewidth=1.5,
            range=[-27, 52],
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=y_ticks,
            ticktext=y_labels,
            gridcolor="rgba(128,128,128,0.08)",
            tickfont=dict(size=12),
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.05,
            xanchor="center",
            x=0.5,
            font_size=12,
            traceorder="normal",
            itemsizing="constant",
        ),
    )
    return fig


def _common_layout(fig: go.Figure):
    fig.update_layout(
        barmode="relative",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Revenue share (%)", ticksuffix="%",
                   gridcolor="rgba(128,128,128,0.15)", zeroline=True, zerolinecolor="#888"),
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

    # File uploader — on main page, always visible
    uploaded = st.file_uploader(
        "📂 Upload your portfolio Excel file (.xlsx)",
        type=["xlsx", "xls"],
        help='Needs sheets "Portfolio" and "SPI" with columns Weight, Security Name / Company Name, Inrate Sector, and 1_A … 17_D.',
    )

    # Landing
    if uploaded is None:
        st.markdown("<br/>", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("### What you'll see")
            for icon, title, desc in [
                ("📊", "SDG Profile",    "Weighted revenue share per SDG — A/B/C/D stacked"),
                ("⚖️", "vs Benchmark",   "Side-by-side comparison (portfolio vs SPI)"),
                ("🔍", "Gap Analysis",   "Table of out- and underperformance per SDG"),
                ("🏢", "Holdings",       "All constituents ranked by weight"),
            ]:
                st.markdown(f"**{icon} {title}** — {desc}")
        with c2:
            st.markdown("""
            <div class="format-hint">
            <strong>Required file format</strong><br/>
            Sheets: <code>Portfolio</code> and <code>SPI</code><br/>
            Columns: <code>Weight</code>, <code>Security Name</code>,
            <code>Inrate Sector</code>,<br/>
            then <code>1_A</code> <code>1_B</code> <code>1_C</code> <code>1_D</code>
            … <code>17_D</code><br/>
            A = very positive &nbsp;·&nbsp; B = positive<br/>
            C = negative &nbsp;·&nbsp; D = very negative
            </div>
            """, unsafe_allow_html=True)
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
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊  SDG Profile", "⚖️  vs Benchmark", "🔍  Gap Analysis",
        "🏢  Portfolio Holdings", "📋  Benchmark Holdings",
        "🏭  Sector Analysis", "ℹ️  Methodology"
    ])

    with tab1:
        st.caption("Bars above zero = positive contribution. Bars below zero = negative. Hover for exact values.")
        st.plotly_chart(profile_chart(pf_w), use_container_width=True)

    with tab2:
        st.caption("Top bar = portfolio (PF), bottom bar = SPI benchmark (BM). Positive values extend right, negative left. Hover for exact values.")
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

        styler = gap_df.style
        try:
            styled = (
                styler
                .map(_clr_pos, subset=["Δ pos"])
                .map(_clr_neg, subset=["Δ neg"])
                .format({"PF pos %": "{:.2f}%", "BM pos %": "{:.2f}%", "Δ pos": "{:+.2f}%",
                         "PF neg %": "{:.2f}%", "BM neg %": "{:.2f}%", "Δ neg": "{:+.2f}%"})
            )
        except AttributeError:
            styled = (
                styler
                .applymap(_clr_pos, subset=["Δ pos"])
                .applymap(_clr_neg, subset=["Δ neg"])
                .format({"PF pos %": "{:.2f}%", "BM pos %": "{:.2f}%", "Δ pos": "{:+.2f}%",
                         "PF neg %": "{:.2f}%", "BM neg %": "{:.2f}%", "Δ neg": "{:+.2f}%"})
            )
        st.dataframe(styled, use_container_width=True, height=640)

    def _holdings_table(df, label, key_suffix):
        def _cp(v): return "color:#1b5e20;font-weight:500" if v > 0 else "color:#9aaa98"
        def _cn(v): return "color:#b71c1c;font-weight:500" if v > 0 else "color:#9aaa98"
        try:
            styled_h = (
                df.style
                .map(_cp, subset=["Avg pos %"])
                .map(_cn, subset=["Avg neg %"])
                .format({"Weight %": "{:.1f}%", "Avg pos %": "{:.2f}%", "Avg neg %": "{:.2f}%"})
                .bar(subset=["Weight %"], color="#c8e6c9", vmin=0)
            )
        except AttributeError:
            styled_h = (
                df.style
                .applymap(_cp, subset=["Avg pos %"])
                .applymap(_cn, subset=["Avg neg %"])
                .format({"Weight %": "{:.1f}%", "Avg pos %": "{:.2f}%", "Avg neg %": "{:.2f}%"})
                .bar(subset=["Weight %"], color="#c8e6c9", vmin=0)
            )
        st.dataframe(styled_h, use_container_width=True, height=700)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(f"⬇ Download {label} CSV", csv, f"{label.lower().replace(' ','_')}.csv",
                           "text/csv", key=key_suffix)

    with tab4:
        st.caption("Ranked by portfolio weight. Avg pos/neg = weighted average revenue share across all 17 SDGs.")
        h_df = build_holdings(pf_raw)
        _holdings_table(h_df, "Portfolio Holdings", "dl_pf")

    with tab5:
        st.caption("Ranked by benchmark weight. Avg pos/neg = weighted average revenue share across all 17 SDGs.")
        bm_df = build_holdings(spi_raw)
        _holdings_table(bm_df, "Benchmark Holdings", "dl_bm")

    with tab6:
        st.markdown("#### Sector-level SDG analysis — portfolio vs benchmark")
        st.caption("All sector scores are weighted averages within each sector, then compared to the same sector in the benchmark.")

        pf_sectors  = compute_sector_weighted(pf_raw)
        bm_sectors  = compute_sector_weighted(spi_raw)
        all_sectors = sorted(set(list(pf_sectors.keys()) + list(bm_sectors.keys())))
        pf_weights  = compute_sector_weights(pf_raw)
        bm_weights  = compute_sector_weights(spi_raw)

        # Sector weights summary
        weight_rows = []
        for s in all_sectors:
            weight_rows.append({
                "Sector": s,
                "PF weight %": pf_weights.get(s, 0.0),
                "BM weight %": bm_weights.get(s, 0.0),
                "Δ weight":    round(pf_weights.get(s, 0.0) - bm_weights.get(s, 0.0), 1),
            })
        w_df = pd.DataFrame(weight_rows).sort_values("PF weight %", ascending=False).reset_index(drop=True)

        with st.expander("📊 Sector weights — portfolio vs benchmark", expanded=False):
            def _clr_delta(v):
                return "color:#1b5e20;font-weight:600" if v > 0 else ("color:#b71c1c;font-weight:600" if v < 0 else "")
            try:
                sw_styled = (
                    w_df.style
                    .map(_clr_delta, subset=["Δ weight"])
                    .format({"PF weight %": "{:.1f}%", "BM weight %": "{:.1f}%", "Δ weight": "{:+.1f}%"})
                    .bar(subset=["PF weight %"], color="#c8e6c9", vmin=0)
                    .bar(subset=["BM weight %"], color="#b2dfdb", vmin=0)
                )
            except AttributeError:
                sw_styled = (
                    w_df.style
                    .applymap(_clr_delta, subset=["Δ weight"])
                    .format({"PF weight %": "{:.1f}%", "BM weight %": "{:.1f}%", "Δ weight": "{:+.1f}%"})
                    .bar(subset=["PF weight %"], color="#c8e6c9", vmin=0)
                    .bar(subset=["BM weight %"], color="#b2dfdb", vmin=0)
                )
            st.dataframe(sw_styled, use_container_width=True, height=min(600, len(w_df)*38 + 40))

        sub1, sub2, sub3, sub4 = st.tabs([
            "📊 SDG profile per sector",
            "📈 All sectors overview",
            "🗂 Heatmap table",
            "🔍 Sector drivers per SDG",
        ])

        # ── Sub-tab 1: SDG profile per sector ────────────────────────────────
        with sub1:
            pf_sector_names = [s for s in all_sectors if s in pf_sectors]
            pf_sector_labels = [f"{s}  (PF: {pf_weights.get(s,0):.1f}%  |  BM: {bm_weights.get(s,0):.1f}%)" for s in pf_sector_names]
            sel_idx = st.selectbox("Select sector", range(len(pf_sector_names)),
                                   format_func=lambda i: pf_sector_labels[i], key="sel_sector_profile")
            sel_sector = pf_sector_names[sel_idx]
            col1, col2 = st.columns(2)
            # Compute shared y-axis range across both portfolio and benchmark
            def get_yrange(w):
                pos_max = max((w[s]["A"] + w[s]["B"]) for s in range(1, 18))
                neg_max = max((w[s]["C"] + w[s]["D"]) for s in range(1, 18))
                return pos_max, neg_max

            pf_pos_max, pf_neg_max = get_yrange(pf_sectors[sel_sector]) if sel_sector in pf_sectors else (0, 0)
            bm_pos_max, bm_neg_max = get_yrange(bm_sectors[sel_sector]) if sel_sector in bm_sectors else (0, 0)
            shared_max =  max(pf_pos_max, bm_pos_max) * 1.15 or 10
            shared_min = -max(pf_neg_max, bm_neg_max) * 1.15

            pf_w_sel = pf_weights.get(sel_sector, 0)
            bm_w_sel = bm_weights.get(sel_sector, 0)
            st.caption(
                f"These charts show the SDG score **within** the selected sector — what % of that sector's own revenue "
                f"aligns with each SDG, regardless of how large the sector is in the portfolio. "
                f"For example, a bar of 88% for {sel_sector} / SDG 3 means 88% of {sel_sector} companies' revenue "
                f"contributes positively to SDG 3. To get the actual contribution to the overall portfolio, "
                f"multiply by the sector weight (currently PF: {pf_w_sel:.1f}% | BM: {bm_w_sel:.1f}%)."
            )
            with col1:
                st.markdown(f"**Portfolio — {sel_sector}**")
                if sel_sector in pf_sectors:
                    w = pf_sectors[sel_sector]
                    fig = profile_chart(w)
                    fig.update_layout(height=350, margin=dict(t=20, b=20, l=10, r=10),
                                      yaxis=dict(range=[shared_min, shared_max]))
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.markdown(f"**Benchmark — {sel_sector}**")
                if sel_sector in bm_sectors:
                    w = bm_sectors[sel_sector]
                    fig = profile_chart(w)
                    fig.update_layout(height=350, margin=dict(t=20, b=20, l=10, r=10),
                                      yaxis=dict(range=[shared_min, shared_max]))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("This sector is not present in the benchmark.")

        # ── Sub-tab 2: All sectors overview ──────────────────────────────────
        with sub2:
            view_mode = st.radio(
                "View",
                ["Within-sector score", "Portfolio contribution (weighted)"],
                horizontal=True, key="sub2_view",
                help="Within-sector: % of sector's own revenue aligned with SDGs. "
                     "Portfolio contribution: multiplied by sector's weight in portfolio/benchmark."
            )
            weighted_view = view_mode == "Portfolio contribution (weighted)"

            pf_sum_df  = build_sector_summary(pf_sectors)
            bm_sum_df  = build_sector_summary(bm_sectors)
            merged = pf_sum_df.merge(bm_sum_df, on="Sector", suffixes=(" PF", " BM"), how="outer").fillna(0)

            if weighted_view:
                # Multiply each sector score by its portfolio weight
                merged["Net pos % PF"] = merged.apply(lambda r: round(r["Net pos % PF"] * pf_weights.get(r["Sector"], 0) / 100, 2), axis=1)
                merged["Net neg % PF"] = merged.apply(lambda r: round(r["Net neg % PF"] * pf_weights.get(r["Sector"], 0) / 100, 2), axis=1)
                merged["Net pos % BM"] = merged.apply(lambda r: round(r["Net pos % BM"] * bm_weights.get(r["Sector"], 0) / 100, 2), axis=1)
                merged["Net neg % BM"] = merged.apply(lambda r: round(r["Net neg % BM"] * bm_weights.get(r["Sector"], 0) / 100, 2), axis=1)
                x_title = "Contribution to portfolio SDG score (sector score × sector weight, %)"
                st.caption("Each bar = within-sector SDG score × sector portfolio weight. Shows the sector's actual impact on the overall portfolio SDG score.")
            else:
                x_title = "Average net SDG score within sector (%)"
                st.caption("Each bar = average net positive/negative across all 17 SDGs, calculated within the sector only — independent of sector weight.")

            merged = merged.sort_values("Net pos % PF", ascending=True)

            n_sectors = len(merged)
            # y positions: PF on top (+0.22), BM below (-0.22) per sector — same logic as vs Benchmark tab
            y_pf2 = [(n_sectors - i) * 3 + 0.55 for i in range(n_sectors)]
            y_bm2 = [(n_sectors - i) * 3 - 0.55 for i in range(n_sectors)]
            y_ticks2 = [(n_sectors - i) * 3 for i in range(n_sectors)]

            fig2 = go.Figure()
            # Use explicit y positions like vs Benchmark tab — no offsetgroup needed
            for lname, col, color, sign, ys in [
                ("PF positive", "Net pos % PF", "#66BB6A",  1, y_pf2),
                ("PF negative", "Net neg % PF", "#f4a0a0", -1, y_pf2),
                ("BM positive", "Net pos % BM", "#1B5E20",  1, y_bm2),
                ("BM negative", "Net neg % BM", "#B71C1C", -1, y_bm2),
            ]:
                vals = merged[col] * sign
                text_vals = [f"{abs(v):.1f}%" if abs(v) >= 1 else "" for v in vals]
                stack = "pf" if "PF" in lname else "bm"
                fig2.add_trace(go.Bar(
                    name=lname, x=vals, y=ys,
                    orientation="h", marker_color=color,
                    marker_line_width=0, width=0.85,
                    text=text_vals, textposition="inside",
                    textfont=dict(size=10, color="white"),
                    customdata=[[merged["Sector"].iloc[i], merged[col].iloc[i]] for i in range(len(merged))],
                    hovertemplate="%{customdata[0]} — " + lname + "<br>%{customdata[1]:.2f}%<extra></extra>",
                    legendgroup=lname.split()[1],
                    showlegend="PF" in lname,
                ))

            # PF/BM labels for each sector
            for i in range(n_sectors):
                fig2.add_annotation(x=-0.5, y=y_pf2[i], text="<b>PF</b>", showarrow=False,
                    font=dict(size=9, color="#888"), xanchor="right", xref="x", yref="y")
                fig2.add_annotation(x=-0.5, y=y_bm2[i], text="<b>BM</b>", showarrow=False,
                    font=dict(size=9, color="#666"), xanchor="right", xref="x", yref="y")

            fig2.update_layout(
                barmode="relative",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                height=max(500, n_sectors * 72),
                margin=dict(l=20, r=20, t=20, b=80),
                xaxis=dict(title=x_title, ticksuffix="%",
                           gridcolor="rgba(128,128,128,0.15)", zeroline=True, zerolinecolor="#888"),
                yaxis=dict(tickmode="array", tickvals=y_ticks2, ticktext=list(merged["Sector"]),
                           gridcolor="rgba(128,128,128,0.08)", tickfont=dict(size=11)),
                legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center", font_size=11),
            )
            st.plotly_chart(fig2, use_container_width=True)

        # ── Sub-tab 3: Heatmap table ──────────────────────────────────────────
        with sub3:
            st.caption(
                "Each cell shows what % of that sector's own revenue aligns with the SDG — "
                "independent of how large the sector is in the portfolio. "
                "Example: Health (PF) SDG 3 = 88.8% means 88.8% of the Health sector's revenue "
                "contributes positively to SDG 3, regardless of Health being 21% of the portfolio."
            )
            view_type = st.radio("Show", ["Net positive (A+B)", "Net negative (C+D)"], horizontal=True, key="hm_view")
            is_pos = view_type == "Net positive (A+B)"
            key_a, key_b = ("A","B") if is_pos else ("C","D")

            sdg_cols = [f"SDG {s}" for s in range(1, 18)]

            # Build separate PF and BM dataframes
            rows_pf, rows_bm = [], []
            for sector in all_sectors:
                row_pf = {"Sector": sector, "Weight %": pf_weights.get(sector, 0.0)}
                row_bm = {"Sector": sector, "Weight %": bm_weights.get(sector, 0.0)}
                for s in range(1, 18):
                    row_pf[f"SDG {s}"] = round((pf_sectors[sector][s][key_a] + pf_sectors[sector][s][key_b]) if sector in pf_sectors else 0, 1)
                    row_bm[f"SDG {s}"] = round((bm_sectors[sector][s][key_a] + bm_sectors[sector][s][key_b]) if sector in bm_sectors else 0, 1)
                rows_pf.append(row_pf)
                rows_bm.append(row_bm)

            pf_hm = pd.DataFrame(rows_pf).set_index("Sector")
            bm_hm = pd.DataFrame(rows_bm).set_index("Sector")

            # Shared max across both for consistent color scale
            max_val = max(pf_hm[sdg_cols].max().max(), bm_hm[sdg_cols].max().max()) or 1
            max_w   = max(pf_hm["Weight %"].max(), bm_hm["Weight %"].max()) or 1

            color_lo = ("#e8f5e9", "#1B5E20") if is_pos else ("#fff3f3", "#B71C1C")

            def make_color_fn(lo, hi):
                def color_cell(v):
                    if v == 0:
                        return "color: #aaa"
                    alpha = min(v / max_val, 1.0)
                    # interpolate from light to dark
                    r0,g0,b0 = int(lo[1:3],16),int(lo[3:5],16),int(lo[5:7],16)
                    r1,g1,b1 = int(hi[1:3],16),int(hi[3:5],16),int(hi[5:7],16)
                    r = int(r0 + (r1-r0)*alpha)
                    g = int(g0 + (g1-g0)*alpha)
                    b = int(b0 + (b1-b0)*alpha)
                    txt = "white" if alpha > 0.55 else hi
                    return f"background-color: rgb({r},{g},{b}); color: {txt}; font-weight: 500"
                return color_cell

            color_fn = make_color_fn(color_lo[0], color_lo[1])
            fmt_dict = {"Weight %": "{:.1f}%"}
            fmt_dict.update({c: "{:.1f}%" for c in sdg_cols})

            # Color legend
            legend_color = "#1B5E20" if is_pos else "#B71C1C"
            legend_label = "net positive (A+B)" if is_pos else "net negative (C+D)"
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:12px;color:var(--color-text-secondary)">'
                f'<span>Color intensity:</span>'
                f'<span style="display:inline-flex;align-items:center;gap:4px">'
                f'<span style="width:16px;height:16px;border-radius:3px;background:{color_lo[0]};border:1px solid #ccc;display:inline-block"></span> 0%'
                f'</span>'
                f'<span>→</span>'
                f'<span style="display:inline-flex;align-items:center;gap:4px">'
                f'<span style="width:16px;height:16px;border-radius:3px;background:{legend_color};display:inline-block"></span> 100% {legend_label}'
                f'</span>'
                f'<span style="margin-left:12px">Weight %: <span style="background:#c8e6c9;padding:1px 6px;border-radius:3px">green bar</span></span>'
                f'</div>',
                unsafe_allow_html=True
            )

            def apply_style(df):
                try:
                    return (df.style
                        .map(color_fn, subset=sdg_cols)
                        .bar(subset=["Weight %"], color="#c8e6c9", vmin=0, vmax=max_w)
                        .format(fmt_dict))
                except AttributeError:
                    return (df.style
                        .applymap(color_fn, subset=sdg_cols)
                        .bar(subset=["Weight %"], color="#c8e6c9", vmin=0, vmax=max_w)
                        .format(fmt_dict))

            row_h = max(400, len(all_sectors) * 38 + 50)
            st.markdown("**Portfolio (PF)**")
            st.dataframe(apply_style(pf_hm), use_container_width=True, height=row_h)
            st.markdown("**Benchmark (BM)**")
            st.dataframe(apply_style(bm_hm), use_container_width=True, height=row_h)

        # ── Sub-tab 4: Sector drivers per SDG ────────────────────────────────
        with sub4:
            sdg_options = [f"SDG {i+1} — {SDG_NAMES[i]}" for i in range(17)]
            sel_sdg_str = st.selectbox("Select SDG", sdg_options, key="sel_sdg_drivers")
            sel_sdg_num = int(sel_sdg_str.split(" ")[1])

            drv_rows = []
            for sector in all_sectors:
                pf_pos = (pf_sectors[sector][sel_sdg_num]["A"] + pf_sectors[sector][sel_sdg_num]["B"]) if sector in pf_sectors else 0
                pf_neg = (pf_sectors[sector][sel_sdg_num]["C"] + pf_sectors[sector][sel_sdg_num]["D"]) if sector in pf_sectors else 0
                bm_pos = (bm_sectors[sector][sel_sdg_num]["A"] + bm_sectors[sector][sel_sdg_num]["B"]) if sector in bm_sectors else 0
                bm_neg = (bm_sectors[sector][sel_sdg_num]["C"] + bm_sectors[sector][sel_sdg_num]["D"]) if sector in bm_sectors else 0
                drv_rows.append({"Sector": sector, "PF pos": pf_pos, "PF neg": pf_neg, "BM pos": bm_pos, "BM neg": bm_neg})

            drv_df = pd.DataFrame(drv_rows)
            drv_df = drv_df[drv_df[["PF pos","PF neg","BM pos","BM neg"]].sum(axis=1) > 0]
            drv_df = drv_df.sort_values("PF pos", ascending=True)

            fig4 = go.Figure()
            for label, col, color, sign in [
                ("PF positive",  "PF pos", "#66BB6A",  1),
                ("PF negative",  "PF neg", "#f4a0a0", -1),
                ("BM positive",  "BM pos", "#1B5E20",  1),
                ("BM negative",  "BM neg", "#B71C1C", -1),
            ]:
                vals = drv_df[col] * sign
                fig4.add_trace(go.Bar(
                    name=label, x=vals, y=drv_df["Sector"],
                    orientation="h", marker_color=color,
                    marker_line_width=0, width=0.35,
                    offsetgroup="PF" if "PF" in label else "BM",
                    customdata=drv_df[col],
                    hovertemplate="%{y} — " + label + "<br>%{customdata:.2f}%<extra></extra>",
                ))
            fig4.update_layout(
                barmode="relative",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                height=max(350, len(drv_df) * 55),
                margin=dict(l=10, r=20, t=20, b=60),
                xaxis=dict(title=f"Revenue share for {sel_sdg_str.split(' — ')[1]} (%)",
                           ticksuffix="%", gridcolor="rgba(128,128,128,0.15)",
                           zeroline=True, zerolinecolor="#888"),
                yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=11)),
                legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center", font_size=11),
            )
            st.plotly_chart(fig4, use_container_width=True)

    with tab7:
        st.markdown("### How the scores are calculated")
        st.markdown("""
**Data source**

Each holding in the portfolio and benchmark is assigned SDG impact scores by Inrate.
For every holding and every SDG (1–17), four revenue share values are provided:

| Rating | Label | Meaning |
|--------|-------|---------|
| **A** | Very positive | Revenue strongly aligned with the SDG |
| **B** | Positive | Revenue moderately aligned with the SDG |
| **C** | Negative | Revenue moderately harmful to the SDG |
| **D** | Very negative | Revenue strongly harmful to the SDG |

Values represent the **percentage of a company's revenue** that contributes to each category (0–100%).

---

**Portfolio-level aggregation**

For each SDG and each rating level, the portfolio score is computed as a **weighted average** across all holdings:

Portfolio score (SDG, level) = sum over all holdings i of: weight_i x score(i, SDG, level)

where $w_i$ is the normalised weight of holding $i$ (i.e. weight divided by total portfolio weight).

---

**Summary metrics**

| Metric | Formula |
|--------|---------|
| **Net positive** | Average of (A + B) across all 17 SDGs |
| **Net negative** | Average of (C + D) across all 17 SDGs |
| **Gap vs benchmark** | Portfolio net positive/negative minus benchmark net positive/negative |

---

**Benchmark**

The benchmark used is the **SPI (Swiss Performance Index)**, sourced from the SPI sheet of the uploaded file and computed identically to the portfolio.
        """)


if __name__ == "__main__":
    main()
