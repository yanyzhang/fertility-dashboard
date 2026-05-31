import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── Column name constants ──────────────────────────────────────────────────────
FERT = "Fertility rate, total (births per woman) [SP.DYN.TFRT.IN]"
NET  = "Individuals using the Internet (% of population) [IT.NET.USER.ZS]"
EDU  = "School enrollment, tertiary, female (% gross) [SE.TER.ENRR.FE]"
GDP  = "GDP per capita (current US$) [NY.GDP.PCAP.CD]"
URB  = "Urban population (% of total population) [SP.URB.TOTL.IN.ZS]"
MORT = "Mortality rate, under-5 (per 1,000 live births) [SH.DYN.MORT]"
AGE  = "Age dependency ratio (% of working-age population) [SP.POP.DPND]"

# ── Visual constants ───────────────────────────────────────────────────────────
FERT_COLORSCALE = [
    [0.000, "#94a3b8"], 
    [0.167, "#64748b"],
    [0.333, "#475569"], 
    [0.500, "#7c5a6b"], 
    [0.667, "#9f5f80"],
    [0.833, "#833e5c"],
    [1.000, "#582a3d"], 
]

INCOME_COLOR = {
    "Low income":           "#8091A8",  
    "Lower middle income":  "#475569",  
    "Upper middle income":  "#C49B66",  
    "High income":          "#2D2D2D", 
}

METHOD_COLOR = {
    "Pill":                   "#4A6785", 
    "IUD":                    "#B36A3E",  
    "Injectable":             "#9C4C4C",  
    "Male condom":            "#527D77", 
    "Female sterilization":   "#5C6E46",  
    "Any traditional method": "#7B5C7E", 
}

# ── Data references – injected by notebook after loading ──────────────────────
df               = None
df_trend         = None
df_scatter_base  = None
merged_contra    = None
df_method        = None
INCOME_ORDER     = []
ALL_INCOME       = []
METHOD_COLS      = []
YEAR_DEFAULT     = 2023
UNMET_COL        = None
COUNTRY_CENTROIDS = {}


# ── Chart builders ─────────────────────────────────────────────────────────────

def build_map(selected_year=None, selected_regions=None, selected_income=None,
              highlighted_codes=None, method_filter_region=None,
              geo_center_lat=None, geo_center_lon=None, zoom_scale=None):
    if selected_year is None:
        selected_year = YEAR_DEFAULT

    effective_year = selected_year
    temp_check = df[df["Time"] == selected_year].dropna(subset=[FERT])
    if temp_check.empty and selected_year == 2024:
        effective_year = 2023

    d = df[df["Time"] == effective_year].dropna(subset=[FERT]).copy()
    if selected_regions:
        d = d[d["Region"].isin(selected_regions)]
    if selected_income:
        d = d[d["Income Group"].isin(selected_income)]
    if d.empty:
        return go.Figure().update_layout(title="No data for selected year/filter")

    fig = px.choropleth(
        d,
        locations="Country Code",
        color=FERT,
        hover_name="Country Name",
        color_continuous_scale=FERT_COLORSCALE,
        projection="natural earth",
        range_color=[1.0, 7.5],
        labels={FERT: "Fertility Rate", "Time": "Year", NET: "Internet %", "Income Group": "Income"},
        custom_data=["Country Name", "Region", "Income Group", NET]
    )

    fig.update_layout(
        title=dict(
            text=f"Global Fertility Rate - {selected_year}",
            x=0.5, xanchor="center", font=dict(size=16, color="#1a2f4a")
        ),
        margin=dict(t=55, b=55, l=0, r=0),
        geo=dict(
            showframe=False,
            showcoastlines=True, coastlinecolor="#a8bfd0",
            showland=True,       landcolor="#f0ece4",
            showocean=True,      oceancolor="#ffffff",
            showlakes=True,      lakecolor="#ffffff",
            showcountries=True,  countrycolor="#d4cfc9",
            projection_type="natural earth",
            bgcolor="rgba(0,0,0,0)",
            lataxis=dict(range=[-60, 85]),
            lonaxis=dict(range=[-180, 180]),
        ),
        coloraxis_colorbar=dict(
            title=dict(text="Births per Woman", font=dict(size=10), side="top"),
            orientation="h", x=0.5, xanchor="center", y=-0.06,
            len=0.55, thickness=10,
            tickvals=[1, 2, 3, 4, 5, 6, 7],
            ticktext=["1", "2", "3", "4", "5", "6", "7+"],
            tickfont=dict(size=9), outlinewidth=0
        ),
        paper_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", size=12),
        uirevision="map"
    )
    fig.update_traces(
        marker_line_color="#e0dbd4",
        marker_line_width=0.4,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Region: %{customdata[1]}<br>"
            "Income: %{customdata[2]}<br>"
            "Fertility: %{z:.2f}<br>"
            "Internet Access: %{customdata[3]:.1f}%<extra></extra>"
        )
    )
    # Apply per-country border styling
    codes_list = list(d["Country Code"])
    region_set = set(d[d["Region"] == method_filter_region]["Country Code"]) \
                 if method_filter_region else set()
    hl_set     = set(highlighted_codes) if highlighted_codes else set()

    line_colors = []
    line_widths = []
    for c in codes_list:
        if c in hl_set:
            line_colors.append("#FF8C00")
            line_widths.append(3.0)
        elif c in region_set:
            line_colors.append("#E69F00")
            line_widths.append(2.0)
        else:
            line_colors.append("#e0dbd4")
            line_widths.append(0.4)

    if hl_set or region_set:
        fig.update_traces(
            marker_line_color=line_colors,
            marker_line_width=line_widths
        )
    if geo_center_lat is not None:
        fig.update_geos(
            center=dict(lat=geo_center_lat, lon=geo_center_lon),
            projection_scale=zoom_scale or 3.5
        )
    return fig


def build_method_bar(selected_year=None, selected_regions=None, selected_income=None, clicked_region=None):
    if not METHOD_COLS:
        return go.Figure().update_layout(title="No contraceptive method columns matched in source data")

    d = df_method.dropna(subset=["Region"]).copy()

    if selected_year is not None and "Survey Year" in d.columns:
        d = d.dropna(subset=["Survey Year"]).copy()
        available_years = sorted(d["Survey Year"].dropna().astype(int).unique().tolist())
        if available_years:
            effective_year = min(available_years, key=lambda y: abs(y - selected_year))
            d = d[d["Survey Year"] == effective_year]
        else:
            effective_year = selected_year
    else:
        effective_year = selected_year if selected_year is not None else YEAR_DEFAULT

    if selected_regions:
        d = d[d["Region"].isin(selected_regions)]
    if selected_income:
        d = d[d["Income Group"].isin(selected_income)]

    if d.empty:
        return go.Figure().update_layout(title="No data for selection")

    agg = d.groupby("Region")[METHOD_COLS].mean().reset_index()

    fig = go.Figure()

    def _rgba(hex_color, alpha):
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return f"rgba({r},{g},{b},{alpha})"

    for method in METHOD_COLS:
        bar_colors = [
            _rgba(METHOD_COLOR[method], 0.88)
            if (not clicked_region or row["Region"] == clicked_region)
            else _rgba(METHOD_COLOR[method], 0.22)
            for _, row in agg.iterrows()
        ]
        fig.add_trace(go.Bar(
            name=f'<span style="font-size: 12px;">{method}</span>',
            x=agg["Region"],
            y=agg[method],
            marker=dict(color=bar_colors),
            hovertemplate=(
                "<b>%{x}</b><br>"
                f"{method}: %{{y:.1f}}%<extra></extra>"
            )
        ))

    year_note = f"Year: {effective_year}" if effective_year is not None else ""
    subtitle_parts = [p for p in [year_note, "Average across surveys", "Click a region bar to filter bubble chart"] if p]

    fig.update_layout(
        barmode="stack",
        title=dict(
            text="Contraceptive Method Mix by Region<br>"
                 f"<sup>{' · '.join(subtitle_parts)}</sup>",
            x=0.5, xanchor="center",
            font=dict(size=16, color="#1a2f4a")
        ),
        xaxis=dict(title="", tickangle=-25, tickfont=dict(size=10)),
        yaxis=dict(title="Average Usage (%)", range=[0, 80]),
        legend=dict(
            orientation="h", y=-0.38, x=0.5, xanchor="center",
            font=dict(size=9)
        ),
        margin=dict(t=75, b=130, l=50, r=20),
        plot_bgcolor="#fefefe",
        paper_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", size=11)
    )
    return fig

#scatter chart
def build_scatter(selected_year=None, selected_regions=None, selected_income=None, highlighted_codes=None,
                  show_edu_bubble=True, heatmap_filter_region=None, heatmap_filter_income=None,
                  x_mode="net"):
    if selected_year is None:
        selected_year = YEAR_DEFAULT

    effective_year = selected_year
    temp_check = df[df["Time"] == selected_year].dropna(subset=[FERT, NET, EDU, MORT, AGE])
    if temp_check.empty:
        available_years = sorted(
            df.dropna(subset=[FERT, NET, EDU, MORT, AGE])["Time"].dropna().astype(int).unique().tolist()
        )
        if available_years:
            effective_year = min(available_years, key=lambda y: abs(y - selected_year))

    d = df[df["Time"] == effective_year].dropna(subset=[FERT, NET, "Income Group", "Region"]).copy()
    d["_in_filter"] = True
    if selected_regions:
        d.loc[~d["Region"].isin(selected_regions), "_in_filter"] = False
    if selected_income:
        d.loc[~d["Income Group"].isin(selected_income), "_in_filter"] = False

    heatmap_countries = None
    if heatmap_filter_region:
        heatmap_countries = set(
            d[(d["Region"] == heatmap_filter_region) &
              (d["_in_filter"] == True)]["Country Code"].tolist()
        )

    if d.empty:
        return go.Figure().update_layout(title="No data for selection")

    fig = go.Figure()
    has_highlight = bool(highlighted_codes) or (heatmap_countries is not None)

    def is_selected(row):
        if not row["_in_filter"]:
            return False
        if highlighted_codes and row["Country Code"] not in highlighted_codes:
            return False
        if heatmap_countries is not None and row["Country Code"] not in heatmap_countries:
            return False
        return True

    d["_selected"] = d.apply(is_selected, axis=1)

    x_col = NET if x_mode == "net" else MORT if x_mode == "mort" else AGE
    x_title = (
        "Internet Usage (%)"                            if x_mode == "net"  else
        "Child Mortality (per 1,000 live births)"       if x_mode == "mort" else
        "Age Dependency Ratio (% of working-age population)"
    )
    x_hover_label = (
        "Internet"            if x_mode == "net"  else
        "Child Mortality"     if x_mode == "mort" else
        "Age Dependency Ratio"
    )

    # Group 1 — ghost marks (out-of-filter)
    ghost = d[~d["_in_filter"]]
    if not ghost.empty:
        ghost_sizes = (ghost[EDU].fillna(5) / 2.8 + 7).clip(7, 36) if show_edu_bubble else [7] * len(ghost)
        fig.add_trace(go.Scatter(
            x=ghost[x_col], y=ghost[FERT], mode="markers",
            marker=dict(color="rgba(180,180,180,0.32)", size=list(ghost_sizes), line=dict(width=0)),
            hoverinfo="skip", showlegend=False
        ))

    # Groups 2 & 3 — in-filter countries per income group
    for inc in ALL_INCOME:
        sub = d[(d["Income Group"] == inc) & d["_in_filter"]]
        if sub.empty:
            continue
        color = INCOME_COLOR.get(inc, "#888888")

        if has_highlight:
            other    = sub[~sub["_selected"]]
            selected = sub[sub["_selected"]]
            if not other.empty:
                other_sizes = (other[EDU].fillna(5) / 2.8 + 7).clip(7, 36) if show_edu_bubble else [11] * len(other)
                fig.add_trace(go.Scatter(
                    x=other[x_col], y=other[FERT], mode="markers",
                    marker=dict(color="rgba(180,180,180,0.35)", size=list(other_sizes), opacity=0.35, line=dict(width=0)),
                    hoverinfo="skip", showlegend=False
                ))
            if not selected.empty:
                selected_sizes = (selected[EDU].fillna(5) / 2.8 + 10).clip(10, 36) if show_edu_bubble else [15] * len(selected)
                customdata    = selected[["Country Name", "Country Code", "Region", EDU, AGE, "Time"]].values
                ht = (f"<b>%{{customdata[0]}}</b><br>Country Code: %{{customdata[1]}}<br>"
                      f"Region: %{{customdata[2]}}<br>{x_hover_label}: %{{x:.1f}}<br>"
                      "Fertility: %{y:.2f}<br>Female Tertiary Enrollment: %{customdata[3]:.1f}%<br>")
                if x_mode == "age":
                    ht += "Age Dependency Ratio: %{customdata[4]:.1f}%<br>"
                ht += "Year: %{customdata[5]:.0f}<extra></extra>"
                fig.add_trace(go.Scatter(
                    x=selected[x_col], y=selected[FERT], mode="markers",
                    marker=dict(color=color, size=list(selected_sizes), opacity=0.95, line=dict(color="black", width=1.5)),
                    customdata=customdata, hovertemplate=ht, showlegend=False
                ))
        else:
            sizes      = (sub[EDU].fillna(5) / 2.8 + 7).clip(7, 36) if show_edu_bubble else [12] * len(sub)
            customdata = sub[["Country Name", "Country Code", "Region", EDU, AGE, "Time"]].values
            ht = (f"<b>%{{customdata[0]}}</b><br>Country Code: %{{customdata[1]}}<br>"
                  f"Region: %{{customdata[2]}}<br>{x_hover_label}: %{{x:.1f}}<br>"
                  "Fertility: %{y:.2f}<br>Female Tertiary Enrollment: %{customdata[3]:.1f}%<br>")
            if x_mode == "age":
                ht += "Age Dependency Ratio: %{customdata[4]:.1f}%<br>"
            ht += "Year: %{customdata[5]:.0f}<extra></extra>"
            fig.add_trace(go.Scatter(
                x=sub[x_col], y=sub[FERT], mode="markers",
                marker=dict(color=color, size=list(sizes), opacity=0.82, line=dict(color="white", width=0.8)),
                customdata=customdata, hovertemplate=ht, showlegend=False
            ))

    # Group 4 — legend markers
    for inc in ALL_INCOME:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", name=inc,
            marker=dict(color=INCOME_COLOR.get(inc, "#888888"), size=12, opacity=0.9, line=dict(color="white", width=0.8)),
            showlegend=True
        ))

    bubble_note = "Bubble size = Female Tertiary Enrollment (%)" if show_edu_bubble else "Uniform bubble size"
    year_note = f"Year: {effective_year}"
    in_filter_n = int(d["_in_filter"].sum())
    total_n     = len(d)
    filter_note = f"{in_filter_n} of {total_n} countries at full detail" if in_filter_n < total_n else ""
    if heatmap_filter_region:
        filter_label = heatmap_filter_region
        if heatmap_filter_income:
            filter_label += f", {heatmap_filter_income}"
        highlight_note = f"Region selected: {filter_label}"
    elif highlighted_codes:
        highlight_note = "Selected country compared with other countries"
    else:
        highlight_note = ""
    subtitle = " · ".join(p for p in [year_note, bubble_note, filter_note, highlight_note] if p)

    layout_kwargs = dict(
        title=dict(
            text=f"{x_title} vs Fertility Rate by Income Group<br><sup>{subtitle}</sup>",
            x=0.5, xanchor="center", font=dict(size=14, color="#1a2f4a")
        ),
        xaxis_title=x_title,
        yaxis_title="Fertility Rate (births/woman)",
        legend=dict(
            title="Income Group", x=0.83, y=0.98,
            xanchor="left", yanchor="top",
            bgcolor="rgba(255,255,255,0.88)", bordercolor="rgba(200,200,200,0.6)",
            borderwidth=1, font=dict(size=10)
        ),
        margin=dict(t=75, b=45, l=60, r=30),
        plot_bgcolor="#fefefe", paper_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", size=11),
        hovermode="closest", clickmode="event+select"
    )
    if x_mode == "net":
        layout_kwargs["xaxis"] = dict(range=[-3, 103], showgrid=True, gridcolor="#eeeeee")
    elif x_mode == "mort":
        layout_kwargs["xaxis"] = dict(range=[0, 150], showgrid=True, gridcolor="#eeeeee")
    else:
        layout_kwargs["xaxis"] = dict(showgrid=True, gridcolor="#eeeeee")
    layout_kwargs["yaxis"] = dict(range=[0.3, 7.2], showgrid=True, gridcolor="#eeeeee")
    fig.update_layout(**layout_kwargs)
    return fig

# line chart
def build_trend(selected_regions=None, selected_income=None,
                highlighted_codes=None, show_indicators=None,
                method_filter_region=None, selected_year=None):
    if show_indicators is None:
        show_indicators = ["edu"]

    d = df_trend.copy()
    if selected_regions:
        d = d[d["Region"].isin(selected_regions)]
    if selected_income:
        d = d[d["Income Group"].isin(selected_income)]
    if d.empty:
        return go.Figure().update_layout(title="No data for selection")

    fig = go.Figure()
    show_edu  = "edu"  in show_indicators
    show_mort = "mort" in show_indicators

    global_fert = df_trend.groupby("Time")[FERT].mean().reset_index()
    subset_fert = d.groupby("Time")[FERT].mean().reset_index()
    if show_edu:
        global_edu = df_trend.groupby("Time")[EDU].mean().reset_index()
        subset_edu = d.groupby("Time")[EDU].mean().reset_index()
    if show_mort:
        global_mort = df_trend.groupby("Time")[MORT].mean().reset_index()
        subset_mort = d.groupby("Time")[MORT].mean().reset_index()

    fig.add_trace(go.Scatter(
        x=global_fert["Time"], y=global_fert[FERT], name='<span style="font-size: 12px;">Global avg fertility</span>',
        mode="lines", line=dict(color="#7A7A7A", width=2.5, dash="dot"),
        hovertemplate="Global avg fertility: %{y:.2f}<extra></extra>", yaxis="y1"
    ))
    fig.add_trace(go.Scatter(
        x=subset_fert["Time"], y=subset_fert[FERT], name='<span style="font-size: 12px;">Filtered avg fertility</span>',
        mode="lines", line=dict(color="#833e5c", width=3),
        hovertemplate="Filtered avg fertility: %{y:.2f}<extra></extra>", yaxis="y1"
    ))
    if show_edu:
        fig.add_trace(go.Scatter(
            x=global_edu["Time"], y=global_edu[EDU], name='<span style="font-size: 12px;">Global avg female tertiary enrollment</span>',
            mode="lines", line=dict(color="#999999", width=2.5, dash="dot"),
            hovertemplate="Global avg female tertiary enrollment: %{y:.1f}%<extra></extra>", yaxis="y2"
        ))
        fig.add_trace(go.Scatter(
            x=subset_edu["Time"], y=subset_edu[EDU], name='<span style="font-size: 12px;">Filtered avg female tertiary enrollment</span>',
            mode="lines", line=dict(color="#0d9488", width=3),
            hovertemplate="Filtered avg female tertiary enrollment: %{y:.1f}%<extra></extra>", yaxis="y2"
        ))
    if show_mort:
        fig.add_trace(go.Scatter(
            x=global_mort["Time"], y=global_mort[MORT], name='<span style="font-size: 12px;">Global avg child mortality</span>',
            mode="lines", line=dict(color="#AAAAAA", width=2.5, dash="dot"),
            hovertemplate="Global avg child mortality: %{y:.1f}<extra></extra>", yaxis="y3"
        ))
        fig.add_trace(go.Scatter(
            x=subset_mort["Time"], y=subset_mort[MORT], name='<span style="font-size: 12px;">Filtered avg child mortality</span>',
            mode="lines", line=dict(color="#CC79A7", width=3),
            hovertemplate="Filtered avg child mortality: %{y:.1f}<extra></extra>", yaxis="y3"
        ))

    if method_filter_region:
        d_region    = df_trend[df_trend["Region"] == method_filter_region]
        region_fert = d_region.groupby("Time")[FERT].mean().reset_index()
        fig.add_trace(go.Scatter(
            x=region_fert["Time"], y=region_fert[FERT],
            name=f'<span style="font-size: 12px;">{method_filter_region} avg fertility</span>',
            mode="lines", line=dict(color="#E69F00", width=2.5, dash="dash"),
            hovertemplate=f"{method_filter_region} avg fertility: %{{y:.2f}}<extra></extra>",
            yaxis="y1"
        ))
        if show_mort:
            d_region_mort = d_region.groupby("Time")[MORT].mean().reset_index()
            fig.add_trace(go.Scatter(
                x=d_region_mort["Time"], y=d_region_mort[MORT],
                name=f'<span style="font-size: 12px;">{method_filter_region} avg child mortality</span>',
                mode="lines", line=dict(color="#B8860B", width=2.5, dash="dash"),
                hovertemplate=f"{method_filter_region} avg child mortality: %{{y:.1f}}<extra></extra>",
                yaxis="y3"
            ))

    if highlighted_codes:
        for code, cdf in df_trend[df_trend["Country Code"].isin(highlighted_codes)].groupby("Country Code"):
            cdf   = cdf.sort_values("Time")
            cname = cdf["Country Name"].iloc[0]
            fig.add_trace(go.Scatter(
                x=cdf["Time"], y=cdf[FERT], name=f'<span style="font-size: 12px;">{cname} fertility</span>',
                mode="lines+markers", line=dict(color="#003B73", width=3.5), marker=dict(size=5),
                hovertemplate=f"{cname} fertility: %{{y:.2f}}<extra></extra>", yaxis="y1"
            ))
            if show_edu:
                fig.add_trace(go.Scatter(
                    x=cdf["Time"], y=cdf[EDU], name=f'<span style="font-size: 12px;">{cname} female tertiary enrollment</span>',
                    mode="lines+markers", line=dict(color="#B86B00", width=3.5), marker=dict(size=5),
                    hovertemplate=f"{cname} female tertiary enrollment: %{{y:.1f}}%<extra></extra>", yaxis="y2"
                ))
            if show_mort:
                fig.add_trace(go.Scatter(
                    x=cdf["Time"], y=cdf[MORT], name=f'<span style="font-size: 12px;">{cname} child mortality</span>',
                    mode="lines+markers", line=dict(color="#7B3F8C", width=3.5), marker=dict(size=5),
                    hovertemplate=f"{cname} child mortality: %{{y:.1f}}<extra></extra>", yaxis="y3"
                ))

    layout_kwargs = dict(
        title=dict(
            text="Fertility Rate Over Time (2000–2024)<br>"
                 "<sup>Dotted = global baseline · Solid = filtered selection · Bold = clicked country</sup>",
            x=0.5, xanchor="center", font=dict(size=16, color="#1a2f4a")
        ),
        xaxis=dict(title="Year", showgrid=True, gridcolor="#eeeeee"),
        yaxis=dict(title="Fertility Rate (births/woman)", range=[0, 8],
                   showgrid=True, gridcolor="#eeeeee", side="left"),
        legend=dict(orientation="h", y=-0.32, x=0.5, xanchor="center", font=dict(size=9)),
        margin=dict(t=75, b=105, l=60, r=120),
        plot_bgcolor="#fefefe", paper_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", size=11),
        hovermode="x unified"
    )
    if show_edu:
        layout_kwargs["yaxis2"] = dict(
            title='<span style="font-size: 12px;">Female Tertiary Enrollment (%)</span>', range=[0, 120],
            overlaying="y", side="right", showgrid=False,
            anchor="free", position=0.88 if show_mort else 0.97


        )
    if show_mort:
        layout_kwargs["yaxis3"] = dict(
            title='<span style="font-size: 12px;">Child Mortality (per 1,000)</span>', range=[0, 150],
            overlaying="y", side="right", showgrid=False,
            anchor="free", position=0.98

        )
    fig.update_layout(**layout_kwargs)
    if selected_year is not None and 2000 <= selected_year <= 2024:
        fig.add_vline(
            x=selected_year,
            line=dict(color="#FF8C00", width=2, dash="solid"),
            opacity=0.75,
            annotation=dict(
                text=str(selected_year),
                font=dict(color="#FF8C00", size=11),
                bgcolor="rgba(255,255,255,0.7)",
                borderpad=2,
                yref="paper", y=1.02,
                showarrow=False
            )
        )
    return fig
