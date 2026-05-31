import os
import json
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, callback_context

# Load and reload charts module so changes pick up
import charts

# Constants imported from charts for column names
FERT = charts.FERT
NET  = charts.NET
EDU  = charts.EDU
GDP  = charts.GDP
URB  = charts.URB
MORT = charts.MORT
AGE  = charts.AGE

# Read data files (same approach as the notebook)
_df = pd.read_excel("data/WorldBank_Combined_Final.xlsx")
for col in ["Time", FERT, NET, EDU, GDP, URB, MORT, AGE]:
    _df[col] = pd.to_numeric(_df[col], errors="coerce")
_df = _df[_df["Time"] <= 2024]
_df = _df.dropna(subset=["Country Code", "Country Name"])

df = _df

# trend and scatter base
_df_trend = df[(df["Time"] >= 2000) & (df["Time"] <= 2024)]

df_scatter_base = (
    df.dropna(subset=[FERT, NET, "Income Group", "Region"]) 
      .sort_values(["Country Name", "Time"]) 
      .groupby("Country Name", as_index=False)
      .last()
)

# contraceptive data
df_contra = pd.read_excel(
    "data/World Contraceptive Use.xlsx",
    sheet_name="By methods",
    header=7
)

df_contra = df_contra.replace("..", pd.NA)

COUNTRY_COL = next(c for c in df_contra.columns if "Country or area" in str(c))
SURVEY_COL  = next(c for c in df_contra.columns if "Survey" in str(c) and "start year" in str(c).lower())
UNMET_COL   = next(c for c in df_contra.columns if "Unmet need for family planning" in str(c))

_df_contra = df_contra.copy()
_df_contra[SURVEY_COL] = pd.to_numeric(_df_contra[SURVEY_COL], errors="coerce")
_df_contra[UNMET_COL]  = pd.to_numeric(_df_contra[UNMET_COL], errors="coerce")
_df_contra = _df_contra.dropna(subset=[UNMET_COL])
_df_contra = (
    _df_contra.sort_values(SURVEY_COL)
              .groupby(COUNTRY_COL, as_index=False)
              .last()
)

# country metadata
df_meta = df[["Country Name", "Region", "Income Group"]].drop_duplicates()

# centroids
_centroid_path = "data/country_centroids.json"
if os.path.exists(_centroid_path):
    with open(_centroid_path) as _f:
        COUNTRY_CENTROIDS = json.load(_f)
else:
    COUNTRY_CENTROIDS = {}

merged_contra = df_contra.merge(df_meta, left_on=COUNTRY_COL, right_on="Country Name", how="left")

# methods processing (lightweight mirroring of notebook)
_raw = pd.read_excel("data/World Contraceptive Use.xlsx", sheet_name="By methods", header=7)
_raw = _raw.replace("..", pd.NA)
_subheader_row = _raw.iloc[0]
_subheader_rename = {}
for _c in _raw.columns:
    _v = _subheader_row.get(_c)
    _subheader_rename[_c] = _v.strip() if isinstance(_v, str) and _v.strip() else _c
_raw = _raw.iloc[1:].reset_index(drop=True)
_raw = _raw.rename(columns=_subheader_rename)
_SURVEY = next((c for c in _raw.columns if "survey" in str(c).lower() and "start year" in str(c).lower()), next((c for c in _raw.columns if "survey" in str(c).lower()), None))
_COUNTRY = next((c for c in _raw.columns if "country or area" in str(c).lower() or "country" in str(c).lower()), _raw.columns[0])
if _SURVEY is None:
    _SURVEY = _COUNTRY
_raw[_SURVEY] = pd.to_numeric(_raw[_SURVEY], errors="coerce")
_raw[_SURVEY] = _raw[_SURVEY].round().astype("Int64")
_raw = _raw.sort_values(_SURVEY).groupby(_COUNTRY, as_index=False).last()

_METHOD_PATTERNS = {
    "Pill":                   ["pill", "oral contraceptive"],
    "IUD":                    ["iud", "intrauterine"],
    "Injectable":             ["inject"],
    "Male condom":            ["male condom"],
    "Female sterilization":   ["female steril"],
    "Any traditional method": ["traditional"],
}
_col_map = {}
for _m, _patterns in _METHOD_PATTERNS.items():
    _match = next(
        (c for c in _raw.columns
         if any(p in str(c).lower().replace("\n", " ") for p in _patterns)),
        None
    )
    if _match:
        _col_map[_match] = _m
        _raw[_match] = pd.to_numeric(_raw[_match], errors="coerce")
_raw = _raw.rename(columns=_col_map)
METHOD_COLS = [m for m in _METHOD_PATTERNS.keys() if m in _raw.columns]
try:
    df_method = _raw[[_COUNTRY, _SURVEY] + METHOD_COLS].merge(
        df_meta, left_on=_COUNTRY, right_on="Country Name", how="left"
    )
    df_method = df_method.rename(columns={_SURVEY: "Survey Year"})
except Exception:
    df_method = pd.DataFrame(columns=[_COUNTRY, "Survey Year"] + METHOD_COLS + ["Country Name", "Region", "Income Group"])

ALL_REGIONS  = sorted(df["Region"].dropna().unique().tolist())
ALL_INCOME   = [i for i in ["Low income", "Lower middle income", "Upper middle income", "High income"]
                if i in df["Income Group"].dropna().unique()]
INCOME_ORDER = [i for i in ["Low income", "Lower middle income", "Upper middle income", "High income"]
                if i in merged_contra["Income Group"].dropna().unique()]

YEAR_MIN     = int(df["Time"].min())
YEAR_MAX     = int(df["Time"].max())
YEAR_DEFAULT = 2023

# Inject into charts module
charts.df                = df
charts.df_trend          = _df_trend
charts.df_scatter_base   = df_scatter_base
charts.merged_contra     = merged_contra
charts.df_method         = df_method
charts.METHOD_COLS       = METHOD_COLS
charts.INCOME_ORDER      = INCOME_ORDER
charts.ALL_INCOME        = ALL_INCOME
charts.YEAR_DEFAULT      = YEAR_DEFAULT
charts.UNMET_COL         = UNMET_COL
charts.COUNTRY_CENTROIDS = COUNTRY_CENTROIDS

from charts import build_map, build_method_bar, build_scatter, build_trend

# Create Dash app
app = Dash(__name__)
server = app.server

# Layout variables
CARD = {
    "backgroundColor": "white",
    "borderRadius": "3px",
    "boxShadow": "0 1px 1px rgba(0,0,0,0.08)",
    "padding": "5px",
    "margin": "5px"
}

CAP = {
    "fontSize": "13px",
    "color": "#555",
    "fontStyle": "italic",
    "lineHeight": "1.45",
    "marginTop": "8px"
}

app.layout = html.Div(
    style={"backgroundColor": "#eef3f8", "padding": "10px", "fontFamily": "Arial, sans-serif"},
    children=[
        dcc.Store(id="store-highlighted"),
        dcc.Store(id="store-heatmap-click"),
        dcc.Store(id="store-play", data=False),
        dcc.Interval(id="play-interval", interval=900, n_intervals=0, disabled=True),

        html.Div(
            style={"backgroundColor": "white", "borderRadius": "2px", "boxShadow": "0 2px 6px rgba(0,0,0,0.08)", "padding": "10px", "marginBottom": "10px", "textAlign": "center"},
            children=[
                html.H1("Global Fertility Decline: Demographic Drivers & Regional Patterns", style={"margin": "0", "color": "#1a2f4a", "fontSize": "26px"}),
                html.P("Explore how fertility rate relates to child mortality, internet access, age dependency, female tertiary enrollment, and contraceptive method mix across countries and income groups.", style={"margin": "8px 0 6px 0", "fontSize": "14px", "color": "#333"}),
                html.Hr(style={"border": "0", "borderTop": "1px solid #d8e0ea"}),
                html.P("Data: World Bank Open Data · UN DESA World Contraceptive Use 2024", style={"fontSize": "11px", "color": "#999", "margin": "0"})
            ]
        ),

        html.Div(
            style={"backgroundColor": "white", "borderRadius": "2px", "boxShadow": "0 2px 6px rgba(0,0,0,0.08)", "padding": "10px", "marginBottom": "10px", "display": "flex", "gap": "20px", "alignItems": "end", "flexWrap": "wrap"},
            children=[
                html.Div(style={"width": "260px"}, children=[
                    html.Label("🌎 Region", style={"fontWeight": "bold", "fontSize": "13px"}),
                    dcc.Dropdown(id="filter-region", options=[{"label": r, "value": r} for r in ALL_REGIONS], value=[], multi=True, placeholder="All regions...")
                ]),
                html.Div(style={"width": "300px"}, children=[
                    html.Label("💰 Income Group", style={"fontWeight": "bold", "fontSize": "13px"}),
                    dcc.Dropdown(id="filter-income", options=[{"label": i, "value": i} for i in ALL_INCOME], value=[], multi=True, placeholder="All income groups...")
                ]),
                html.Div(children=[
                    html.Label("🎓 Bubble size", style={"fontWeight": "bold", "fontSize": "13px"}),
                    dcc.RadioItems(id="toggle-edu", options=[{"label": "Female tertiary enrollment", "value": "edu"}, {"label": "Uniform", "value": "uniform"}], value="edu", inline=True, style={"fontSize": "12px", "marginTop": "8px"})
                ]),
                html.Button("↺ Reset", id="btn-reset", n_clicks=0, style={"backgroundColor": "#1a2f4a", "color": "white", "border": "none", "borderRadius": "6px", "padding": "9px 18px", "fontWeight": "bold", "cursor": "pointer"})
            ]
        ),

        html.Div(id="detail-panel", style={"display": "none", "position": "fixed", "top": "10%", "left": "10%", "width": "80%", "height": "80%", "marginBottom": "8px"}, children=[html.Button("✕", id="btn-close-detail", n_clicks=0, style={"display": "none"})]),

        html.Div(style={"display": "grid", "gridTemplateColumns": "50% 50%", "gap": "2px"}, children=[
            html.Div(style=CARD, children=[
                html.Div(id="selected-country-badge", style={"minHeight": "22px", "marginBottom": "4px"}, children=[]),
                dcc.Graph(id="chart-map", figure=build_map(), style={"height": "450px"}),
                html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginTop": "0px", "paddingLeft": "4px", "paddingRight": "4px"}, children=[
                    html.Button("▶", id="btn-play", n_clicks=0, style={"backgroundColor": "#f2f2f2", "color": "#555", "border": "none", "borderRadius": "6px", "width": "30px", "height": "30px", "cursor": "pointer", "fontSize": "16px", "flexShrink": "0", "display": "flex", "alignItems": "center", "justifyContent": "center"}),
                    html.Div(str(YEAR_MIN), style={"color": "#555", "fontSize": "14px", "fontWeight": "500"}),
                    html.Div(style={"flex": "1"}, children=[dcc.Slider(id="filter-year", min=YEAR_MIN, max=YEAR_MAX, value=YEAR_DEFAULT, step=1, marks=None, tooltip={"placement": "top", "always_visible": False}, updatemode="drag")])
                ])
            ]),
            html.Div(style=CARD, children=[
                dcc.Graph(id="chart-trend", figure=build_trend(), style={"height": "450px"}),
                dcc.Checklist(id="toggle-trend-indicators", options=[{"label": "Female Tertiary Enrollment", "value": "edu"}, {"label": "Child Mortality", "value": "mort"}], value=["edu"], inline=True, style={"textAlign": "center", "marginBottom": "8px", "fontSize": "11px"}, labelStyle={"display": "inline-block", "marginRight": "16px"})
            ])
        ]),

        html.Div(style={"display": "grid", "gridTemplateColumns": "62% 38%", "gap": "2px"}, children=[
            html.Div(style=CARD, children=[
                dcc.Graph(id="chart-scatter", figure=build_scatter(selected_year=YEAR_DEFAULT), style={"height": "520px"}),
                dcc.RadioItems(id="toggle-scatter-x", options=[{"label": "Internet Access", "value": "net"}, {"label": "Child Mortality", "value": "mort"}, {"label": "Age Dependency Ratio", "value": "age"}], value="net", inline=True, style={"textAlign": "center", "marginBottom": "8px", "fontSize": "11px"}, labelStyle={"display": "inline-block", "marginRight": "16px"})
            ]),
            html.Div(style=CARD, children=[
                dcc.Graph(id="chart-heatmap", figure=build_method_bar(selected_year=YEAR_DEFAULT), style={"height": "520px"})
            ])
        ])
    ]
)

# Callbacks (ported from notebook)
@app.callback(
    Output("filter-region", "value"),
    Output("filter-income", "value"),
    Output("filter-year", "value"),
    Output("toggle-edu", "value"),
    Output("toggle-scatter-x", "value"),
    Output("toggle-trend-indicators", "value"),
    Input("btn-reset", "n_clicks"),
    prevent_initial_call=True
)
def reset_ui_components(n_reset):
    return [], [], YEAR_DEFAULT, "edu", "net", ["edu"]


@app.callback(
    Output("store-highlighted", "data"),
    Input("chart-map",        "clickData"),
    Input("chart-scatter",    "clickData"),
    Input("btn-reset",        "n_clicks"),
    Input("btn-close-detail", "n_clicks"),
    prevent_initial_call=True
)
def update_highlighted(map_click, scatter_click, _reset, _close):
    ctx = callback_context
    if not ctx.triggered:
        return None
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if triggered_id in ("btn-reset", "btn-close-detail"):
        return None

    if triggered_id == "chart-map" and map_click:
        pt = map_click["points"][0]
        code = pt.get("location")
        if code:
            return [code]

    if triggered_id == "chart-scatter" and scatter_click:
        pt = scatter_click["points"][0]
        cdata = pt.get("customdata")
        if cdata and len(cdata) > 1:
            code = cdata[1]
            if code:
                return [code]

    return None


@app.callback(
    Output("store-heatmap-click", "data"),
    Input("chart-heatmap", "clickData"),
    Input("btn-reset", "n_clicks"),
    prevent_initial_call=True
)
def update_heatmap_click(click_data, _reset):
    ctx = callback_context

    if not ctx.triggered:
        return None

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if triggered_id == "btn-reset":
        return None

    if click_data:
        pt = click_data["points"][0]
        return {"region": pt.get("x")}

    return None


@app.callback(
    Output("chart-map", "figure"),
    Output("chart-scatter", "figure"),
    Output("chart-trend", "figure"),
    Output("chart-heatmap", "figure"),
    Input("filter-year", "value"),
    Input("filter-region", "value"),
    Input("filter-income", "value"),
    Input("toggle-edu", "value"),
    Input("toggle-scatter-x", "value"),
    Input("toggle-trend-indicators", "value"),
    Input("store-highlighted", "data"),
    Input("store-heatmap-click", "data"),
    Input("btn-reset", "n_clicks")
)
def render_all(
    selected_year, regions, income, edu_toggle,
    scatter_x_mode, trend_indicators,
    highlighted, heatmap_click, _reset
):
    ctx = callback_context
    triggered_ids = [t["prop_id"].split(".")[0] for t in ctx.triggered]

    if "btn-reset" in triggered_ids:
        highlighted   = None
        heatmap_click = None

    show_edu = (edu_toggle == "edu")
    hm_region = heatmap_click.get("region") if heatmap_click else None
    hm_income = heatmap_click.get("income") if heatmap_click else None
    highlighted_set = set(highlighted) if highlighted else None

    fig_map = build_map(
        selected_year=selected_year,
        selected_regions=regions,
        selected_income=income,
        highlighted_codes=highlighted_set,
        method_filter_region=hm_region
    )
    fig_scatter = build_scatter(
        selected_year=selected_year,
        selected_regions=regions,
        selected_income=income,
        highlighted_codes=highlighted_set,
        show_edu_bubble=show_edu,
        heatmap_filter_region=hm_region,
        heatmap_filter_income=hm_income,
        x_mode=scatter_x_mode
    )
    fig_trend = build_trend(
        selected_regions=regions,
        selected_income=income,
        highlighted_codes=highlighted_set,
        show_indicators=trend_indicators,
        method_filter_region=hm_region,
        selected_year=selected_year
    )
    fig_heatmap = build_method_bar(
        selected_year=selected_year,
        selected_regions=regions,
        selected_income=income,
        clicked_region=hm_region
    )
    return fig_map, fig_scatter, fig_trend, fig_heatmap


@app.callback(
    Output("map-title-display", "children"),
    Input("filter-year", "value")
)
def update_map_title(year):
    return f"Global Fertility Rate - {year}"


@app.callback(
    Output("store-play", "data"),
    Output("btn-play", "children"),
    Output("play-interval", "disabled"),
    Input("btn-play", "n_clicks"),
    Input("btn-reset", "n_clicks"),
    State("store-play", "data"),
    prevent_initial_call=True
)
def toggle_play(n_play, n_reset, is_playing):
    ctx = callback_context
    triggered = ctx.triggered[0]["prop_id"].split(".")[0]
    if triggered == "btn-reset":
        return False, "▶", True
    new_state = not is_playing
    return new_state, "⏸" if new_state else "▶", not new_state


@app.callback(
    Output("filter-year", "value"),
    Input("play-interval", "n_intervals"),
    State("filter-year", "value"),
    State("store-play", "data"),
    prevent_initial_call=True
)
def advance_year(n, current_year, is_playing):
    if not is_playing:
        return current_year
    next_year = current_year + 1
    if next_year > YEAR_MAX:
        next_year = YEAR_MIN
    return next_year


@app.callback(
    Output("selected-country-badge", "children"),
    Input("store-highlighted", "data"),
    Input("btn-reset", "n_clicks"),
    Input("btn-close-detail", "n_clicks"),
    prevent_initial_call=False
)
def update_country_badge(highlighted, _reset, _close):
    ctx = callback_context
    triggered = [t["prop_id"].split(".")[0] for t in ctx.triggered] if ctx.triggered else []
    if not highlighted or "btn-reset" in triggered or "btn-close-detail" in triggered:
        return []

    code = highlighted[0]
    row  = df[df["Country Code"] == code]
    if row.empty:
        return []

    r      = row.iloc[-1]
    name   = r.get("Country Name", code)
    income = r.get("Income Group", "")
    badge_color = charts.INCOME_COLOR.get(income, "#888")

    return [
        html.Span("📍 ", style={"fontSize": "12px"}),
        html.Span(name, style={"fontWeight": "bold", "fontSize": "13px", "color": "#1a2f4a", "marginRight": "6px"}),
        html.Span(income, style={"fontSize": "11px", "backgroundColor": badge_color, "color": "white", "padding": "1px 7px", "borderRadius": "10px", "marginRight": "6px"}),
        html.Span("  ✕", id="badge-clear", style={"fontSize": "11px", "color": "#aaa", "cursor": "pointer", "marginLeft": "8px"})
    ]


@app.callback(
    Output("detail-panel", "children"),
    Output("detail-panel", "style"),
    Input("store-highlighted", "data"),
    Input("filter-year", "value"),
    Input("btn-reset", "n_clicks"),
    Input("btn-close-detail", "n_clicks"),
    prevent_initial_call=True
)
def update_detail_panel(highlighted, selected_year, _reset, _close):
    ctx = callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    hidden_close = html.Button("✕", id="btn-close-detail", n_clicks=0, style={"display": "none"})

    if triggered_id in ("btn-reset", "btn-close-detail") or not highlighted:
        return [hidden_close], {"display": "none"}

    code = highlighted[0]
    row = df[(df["Country Code"] == code) & (df["Time"] == selected_year)]
    if row.empty or row.iloc[0][[FERT, NET, MORT]].isna().all():
        row = df[df["Country Code"] == code].dropna(subset=[FERT])
        if row.empty:
            return [hidden_close], {"display": "none"}
        row = row.sort_values("Time").iloc[[-1]]

    r            = row.iloc[0]
    country_name = r["Country Name"]
    region       = r.get("Region", "—")
    income       = r.get("Income Group", "—")
    year_used    = int(r["Time"])
    badge_color  = charts.INCOME_COLOR.get(income, "#888888")

    def fmt_val(val, decimals=1, prefix="", suffix=""):
        if pd.isna(val):
            return "—"
        if prefix == "$":
            return f"${val:,.0f}"
        return f"{prefix}{val:.{decimals}f}{suffix}"

    contra_row = merged_contra[merged_contra["Country Name"] == country_name]
    unmet_val  = fmt_val(contra_row.iloc[0][UNMET_COL] if not contra_row.empty else float("nan"), decimals=1, suffix="%")

    global_yr = df[df["Time"] == selected_year]
    g_fert    = global_yr[FERT].mean()
    g_mort    = global_yr[MORT].mean()

    metrics = [
        ("Fertility Rate",             fmt_val(r[FERT], 2, suffix=" births/woman")),
        ("Child Mortality",            fmt_val(r[MORT], 1, suffix=" per 1,000")),
        ("Internet Access",            fmt_val(r[NET],  1, suffix="%")),
        ("Female Tertiary Enrollment", fmt_val(r[EDU],  1, suffix="%")),
        ("GDP per Capita",             fmt_val(r[GDP],  0, prefix="$")),
        ("Unmet Contraceptive Need",   unmet_val),
    ]

    tiles = [
        html.Div(style={"minWidth": "130px", "flex": "1", "backgroundColor": "#f8f9fa", "borderRadius": "8px", "padding": "10px 14px", "textAlign": "center"}, children=[
            html.Div(label, style={"fontSize": "11px", "color": "#777", "marginBottom": "4px"}),
            html.Div(value, style={"fontSize": "19px", "fontWeight": "bold", "color": "#1a2f4a"})
        ])
        for label, value in metrics
    ]

    fert_ok = pd.notna(r[FERT]) and pd.notna(g_fert)
    mort_ok = pd.notna(r[MORT]) and pd.notna(g_mort)
    context_note = (
        f"Compared to {selected_year} global averages: "
        + (f"fertility {r[FERT]:.2f} vs {g_fert:.2f} global" if fert_ok else "")
        + (" · " if fert_ok and mort_ok else "")
        + (f"child mortality {r[MORT]:.0f} vs {g_mort:.0f} global." if mort_ok else "")
    ) if fert_ok or mort_ok else ""

    panel_children = [
        html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px"}, children=[
            html.Div([
                html.Span(country_name, style={"fontSize": "18px", "fontWeight": "bold", "color": "#1a2f4a", "marginRight": "10px"}),
                html.Span(region, style={"fontSize": "12px", "backgroundColor": "#eef3f8", "padding": "2px 8px", "borderRadius": "12px", "color": "#555", "marginRight": "6px"}),
                html.Span(income, style={"fontSize": "12px", "backgroundColor": badge_color, "padding": "2px 8px", "borderRadius": "12px", "color": "white", "marginRight": "6px"}),
                html.Span(f"Data year: {year_used}", style={"fontSize": "12px", "color": "#999"}),
            ]),
            html.Button("✕", id="btn-close-detail", n_clicks=0, style={"border": "none", "background": "none", "fontSize": "16px", "cursor": "pointer", "color": "#999"})
        ]),
        html.Div(style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginBottom": "10px"}, children=tiles),
        html.P(context_note, style={"fontSize": "12px", "color": "#888", "margin": "0", "fontStyle": "italic"}) if context_note else html.Div()
    ]

    panel_style = {"display": "block", "backgroundColor": "white", "borderRadius": "2px", "boxShadow": "0 2px 6px rgba(0,0,0,0.08)", "padding": "10px", "marginBottom": "10px", "borderLeft": f"4px solid {badge_color}"}

    return panel_children, panel_style


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run_server(host="0.0.0.0", port=port, debug=False)
