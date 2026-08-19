from __future__ import annotations

import hashlib
import json
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from branca.colormap import linear
from streamlit_folium import st_folium

from market_predictor.config import AppConfig
from market_predictor.pipeline.opportunity import identify_high_potential_zones
from market_predictor.pipeline.runner import load_precomputed
from market_predictor.pipeline.scoring import calculate_market_potential_score
from market_predictor.pipeline.sensitivity import rank_stability_summary, run_sensitivity_analysis
from market_predictor.pipeline.zonal import extract_zonal_statistics


def _score_to_gauge_value(score: float) -> float:
    return score * 100


def _gdf_hash(gdf: gpd.GeoDataFrame) -> str:
    """Create a deterministic hash of GeoDataFrame for caching purposes."""
    # Hash based on key columns and geometry
    cols_to_hash = ["district_id", "market_potential_score", "is_high_potential_untapped"]
    available_cols = [c for c in cols_to_hash if c in gdf.columns]
    
    # Use deterministic hashing with hashlib
    try:
        data_str = str(gdf[available_cols].values.tobytes())
        hash_obj = hashlib.md5(data_str.encode())
        return hash_obj.hexdigest()[:16]
    except Exception:
        # Fallback to simpler hash
        return hashlib.md5(str(gdf.shape).encode()).hexdigest()[:16]


@st.cache_resource
def _build_folium_map(
    _gdf: gpd.GeoDataFrame,
    raster_path: str | None,
    show_raster: bool,
    _gdf_id: str = "",
) -> folium.Map:
    center_lat = _gdf.geometry.centroid.y.mean()
    center_lon = _gdf.geometry.centroid.x.mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="CartoDB positron")

    if show_raster and raster_path and Path(raster_path).exists():
        import rasterio

        with rasterio.open(raster_path) as src:
            bounds = src.bounds
            img = src.read(1)
            img_norm = np.clip(img / (img.max() or 1) * 255, 0, 255).astype(np.uint8)
        folium.raster_layers.ImageOverlay(
            image=img_norm,
            bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
            opacity=0.35,
            name="Night Lights",
        ).add_to(m)

    scores = _gdf["market_potential_score"]
    colormap = linear.YlGnBu_09.scale(scores.min(), scores.max())
    colormap.caption = "Market Potential Score"

    def style_fn(feature):
        idx = feature["properties"].get("_idx")
        score = _gdf.loc[idx, "market_potential_score"] if idx in _gdf.index else 0
        return {"fillColor": colormap(score), "color": "#333", "weight": 1, "fillOpacity": 0.65}

    geojson = json.loads(_gdf.to_json())
    for i, feat in enumerate(geojson["features"]):
        feat["properties"]["_idx"] = _gdf.index[i]
        if "display_name" in _gdf.columns:
            feat["properties"]["display_name"] = _gdf.iloc[i]["display_name"]
        else:
            feat["properties"]["display_name"] = _gdf.iloc[i].get("district_id", f"Area {i + 1}")
        if "scenario_rate" in _gdf.columns:
            feat["properties"]["scenario_rate"] = float(_gdf.iloc[i]["scenario_rate"])

    tooltip_fields = ["display_name", "scenario_rate"]
    if "is_high_potential_untapped" in _gdf.columns:
        _gdf = _gdf.copy()
        _gdf["expansion_status"] = np.where(_gdf["is_high_potential_untapped"], "Untapped: yes", "Untapped: no")
        tooltip_fields = ["display_name", "scenario_rate"]

    folium.GeoJson(
        geojson,
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=["Area", "Scenario rate"][: len(tooltip_fields)],
        ),
    ).add_to(m)

    untapped = _gdf[_gdf["is_high_potential_untapped"]]
    for _, row in untapped.iterrows():
        c = row.geometry.centroid
        label = row.get("display_name", row.get("district_id", "Area"))
        folium.Marker(
            [c.y, c.x],
            popup=f"{label} • rank {int(row['opportunity_rank'])}",
            icon=folium.Icon(color="red", icon="star"),
        ).add_to(m)

    colormap.add_to(m)
    folium.LayerControl().add_to(m)
    return m


@st.cache_data
def _build_plotly_map(_gdf: gpd.GeoDataFrame, _gdf_id: str = "") -> go.Figure:
    geojson_dict = _gdf.__geo_interface__
    display_name_col = "display_name" if "display_name" in _gdf.columns else "district_id"
    if "scenario_rate" not in _gdf.columns:
        _gdf = _gdf.copy()
        _gdf["scenario_rate"] = 0.9
    fig = px.choropleth_mapbox(
        _gdf,
        geojson=geojson_dict,
        locations=_gdf.index,
        color="market_potential_score",
        color_continuous_scale="Viridis",
        range_color=(0, 1),
        mapbox_style="carto-positron",
        zoom=10,
        center={"lat": _gdf.geometry.centroid.y.mean(), "lon": _gdf.geometry.centroid.x.mean()},
        opacity=0.65,
        hover_name=display_name_col,
        hover_data={
            "scenario_rate": ":.2f",
            "market_potential_score": ":.3f",
        },
    )
    untapped = _gdf[_gdf["is_high_potential_untapped"]]
    if not untapped.empty:
        fig.add_scattermapbox(
            lat=untapped.geometry.centroid.y,
            lon=untapped.geometry.centroid.x,
            mode="markers+text",
            marker=dict(size=14, color="red", symbol="star"),
            text=untapped[display_name_col],
            textposition="top right",
            name="High-Potential Untapped",
        )
    fig.update_layout(margin=dict(t=10, b=10, l=0, r=0), height=480)
    return fig


def _download_buttons(gdf: gpd.GeoDataFrame) -> None:
    flagged = gdf[gdf["is_high_potential_untapped"]].copy()
    if flagged.empty:
        st.info("No flagged zones to export.")
        return
    csv_buf = flagged.drop(columns="geometry").to_csv(index=False)
    geojson_buf = flagged.to_json()
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Download CSV", csv_buf, "untapped_zones.csv", "text/csv")
    with c2:
        st.download_button("Download GeoJSON", geojson_buf, "untapped_zones.geojson", "application/json")


EUROPE_COUNTRIES = {
    "Portugal": (-9.5, 36.8, -6.1, 42.2), "Spain": (-9.5, 36.0, 3.5, 43.8),
    "France": (-5.2, 42.2, 9.5, 51.1), "Germany": (5.8, 47.2, 15.0, 55.1),
    "Italy": (6.6, 36.6, 18.5, 47.1), "Netherlands": (3.3, 51.2, 7.3, 53.6),
    "Belgium": (2.5, 49.4, 6.5, 51.5), "Poland": (14.0, 49.0, 24.2, 54.9),
    "Czechia": (12.0, 48.5, 18.9, 51.2), "Austria": (9.1, 46.3, 17.2, 49.1),
    "Sweden": (11.0, 55.3, 24.2, 69.1), "Norway": (4.9, 57.9, 31.1, 71.2),
    "Finland": (20.5, 59.8, 31.5, 70.2), "Denmark": (8.0, 54.5, 12.8, 57.8),
    "Ireland": (-10.5, 51.3, -5.4, 55.4), "Greece": (19.0, 34.8, 29.7, 41.9),
    "Romania": (20.1, 43.6, 29.8, 48.3), "Hungary": (16.1, 45.7, 22.9, 48.6),
    "Bulgaria": (22.2, 41.1, 28.7, 44.3), "Slovenia": (13.4, 45.4, 16.6, 46.9),
    "Croatia": (13.4, 42.4, 19.4, 46.5), "Switzerland": (6.0, 45.8, 10.5, 47.8),
    "United Kingdom": (-8.7, 50.0, 1.8, 59.0),
}
US_STATES = {
    "Washington": (-125.0, 45.5, -116.9, 49.1), "Oregon": (-124.8, 41.9, -116.4, 46.3),
    "California": (-124.5, 32.5, -114.1, 42.1), "Nevada": (-120.0, 35.0, -114.0, 42.0),
    "Idaho": (-117.2, 41.9, -111.0, 49.0), "Montana": (-116.0, 44.3, -104.0, 49.1),
    "Wyoming": (-111.1, 40.9, -104.0, 45.1), "Utah": (-114.1, 36.9, -109.0, 42.0),
    "Arizona": (-115.0, 31.3, -109.0, 37.1), "New Mexico": (-109.1, 31.3, -103.0, 37.0),
    "Colorado": (-109.1, 36.9, -102.0, 41.1), "Nebraska": (-104.1, 40.0, -95.3, 43.1),
    "Kansas": (-102.1, 36.9, -94.3, 40.2), "Oklahoma": (-103.1, 33.6, -94.4, 37.0),
    "Texas": (-106.7, 25.8, -93.5, 36.5), "Minnesota": (-97.2, 43.4, -89.5, 49.4),
    "Iowa": (-96.6, 40.4, -90.1, 43.5), "Missouri": (-95.8, 36.0, -89.1, 40.6),
    "Arkansas": (-94.6, 33.0, -89.6, 36.5), "Louisiana": (-94.1, 28.9, -88.8, 33.1),
    "Wisconsin": (-92.9, 42.5, -86.8, 47.3), "Illinois": (-91.5, 36.9, -87.4, 42.5),
    "Michigan": (-90.4, 41.7, -82.1, 48.3), "Indiana": (-88.1, 37.8, -84.8, 41.8),
    "Ohio": (-84.8, 38.4, -80.5, 42.5), "Kentucky": (-89.6, 36.6, -81.9, 39.2),
    "Tennessee": (-90.3, 34.9, -81.6, 36.6), "Mississippi": (-91.7, 30.2, -88.1, 35.0),
    "Alabama": (-88.5, 30.1, -84.8, 35.0), "Georgia": (-85.6, 30.4, -80.8, 35.2),
    "Florida": (-87.6, 24.4, -80.0, 31.1), "North Carolina": (-84.3, 33.8, -75.4, 36.6),
    "South Carolina": (-83.4, 32.0, -78.5, 35.2), "Virginia": (-83.7, 36.5, -75.2, 39.5),
    "West Virginia": (-82.6, 37.2, -77.7, 40.7), "Pennsylvania": (-80.5, 39.7, -71.9, 42.5),
    "New York": (-79.8, 40.5, -71.8, 45.0), "New Jersey": (-75.6, 38.9, -73.9, 41.4),
    "Connecticut": (-73.8, 41.1, -71.8, 42.1), "Massachusetts": (-73.5, 41.2, -70.0, 42.9),
    "Rhode Island": (-71.9, 41.1, -71.0, 42.1), "Maine": (-71.1, 43.0, -66.9, 47.5),
    "New Hampshire": (-72.6, 42.7, -70.7, 45.3), "Vermont": (-73.4, 42.7, -71.5, 45.0),
    "Maryland": (-79.5, 37.9, -75.0, 39.7), "Delaware": (-75.8, 38.4, -75.0, 39.9),
    "District of Columbia": (-77.12, 38.80, -76.90, 38.99), "Alaska": (-179.1, 51.2, -129.9, 71.4),
    "Hawaii": (-160.3, 18.8, -154.8, 22.3), "North Dakota": (-104.0, 45.9, -96.5, 49.0),
    "South Dakota": (-104.1, 42.4, -96.5, 45.9), "Maine": (-71.1, 43.0, -66.9, 47.5),
    "New Hampshire": (-72.6, 42.7, -70.7, 45.3), "Vermont": (-73.4, 42.7, -71.5, 45.0),
}


def _lookup_label(lon: float, lat: float, mapping: dict[str, tuple[float, float, float, float]], default: str) -> str:
    for name, (min_lon, min_lat, max_lon, max_lat) in mapping.items():
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            return name
    return default


def _base_region_label(lon: float, lat: float, region_name: str) -> str:
    if region_name.lower() == "united states":
        return _lookup_label(lon, lat, US_STATES, "United States")
    return _lookup_label(lon, lat, EUROPE_COUNTRIES, "Europe")


def _centroid_lon_lat(gdf: gpd.GeoDataFrame) -> tuple[np.ndarray, np.ndarray]:
    out = gdf.copy()
    if out.empty:
        return np.array([]), np.array([])
    if out.geometry.crs is None:
        out = out.set_crs("EPSG:4326")
    projected = out.to_crs("EPSG:3857")
    centroids = projected.geometry.centroid.to_crs("EPSG:4326")
    return centroids.x.to_numpy(), centroids.y.to_numpy()


def _add_display_names(gdf: gpd.GeoDataFrame, region_name: str) -> gpd.GeoDataFrame:
    out = gdf.copy()
    if out.empty:
        out["display_name"] = []
        out["market_area"] = []
        return out

    if out.geometry.crs is None:
        out = out.set_crs("EPSG:4326")

    centroid_lons, centroid_lats = _centroid_lon_lat(out)
    area_labels = []
    for lon, lat in zip(centroid_lons, centroid_lats):
        area_labels.append(_base_region_label(float(lon), float(lat), region_name))

    out["display_name"] = area_labels
    out["market_area"] = area_labels
    out["region_group"] = region_name
    return out


def _land_only_mask(gdf: gpd.GeoDataFrame, region_name: str) -> np.ndarray:
    if gdf.empty:
        return np.array([], dtype=bool)
    if gdf.geometry.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    centroid_lons, centroid_lats = _centroid_lon_lat(gdf)
    mapping = US_STATES if region_name.lower() == "united states" else EUROPE_COUNTRIES
    mask = []
    for lon, lat in zip(centroid_lons, centroid_lats):
        in_land = any(
            min_lon <= float(lon) <= max_lon and min_lat <= float(lat) <= max_lat
            for _, (min_lon, min_lat, max_lon, max_lat) in mapping.items()
        )
        mask.append(in_land)
    return np.asarray(mask, dtype=bool)


def _scope_region(gdf: gpd.GeoDataFrame, region_name: str) -> gpd.GeoDataFrame:
    out = gdf.copy()
    if out.empty:
        return out

    if out.geometry.crs is None:
        out = out.set_crs("EPSG:4326")

    centroid_lons, centroid_lats = _centroid_lon_lat(out)
    if region_name.lower() == "united states":
        mask = (
            (centroid_lons >= -125) & (centroid_lons <= -66) &
            (centroid_lats >= 24) & (centroid_lats <= 50) &
            ((centroid_lons <= -117) | (centroid_lons >= -79))
        )
        out = out[mask].copy()
    else:
        mask = (centroid_lons >= -10) & (centroid_lons <= 35) & (centroid_lats >= 35) & (centroid_lats <= 72)
        out = out[mask].copy()

    if out.empty:
        return out

    land_mask = _land_only_mask(out, region_name)
    out = out[land_mask].copy()
    if out.empty:
        return out

    out["market_area"] = [
        _base_region_label(float(lon), float(lat), region_name)
        for lon, lat in zip(_centroid_lon_lat(out)[0], _centroid_lon_lat(out)[1])
    ]
    return out


def main() -> None:
    st.set_page_config(page_title="Market Potential Predictor", page_icon="🌐", layout="wide")
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #0b1220 0%, #0f172a 100%);
            color: #e2e8f0;
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 10px;
            overflow: hidden;
        }
        .stPlotlyChart {
            border-radius: 10px;
        }
        .stSidebar {
            background: rgba(15, 23, 42, 0.95);
        }
        h1, h2, h3, h4 {
            letter-spacing: -0.02em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    cfg = AppConfig.load()

    st.sidebar.title("🌐 Market Potential Finder")
    region_name = st.sidebar.selectbox("Focus area", ["Europe", "United States"], index=0)
    region_key = "europe" if region_name == "Europe" else "united_states"
    use_precomputed = st.sidebar.checkbox("Use saved results", value=False)
    scoring_method = st.sidebar.selectbox(
        "Model", ["weighted", "mcda", "pca", "ml"], index=0
    )
    light_weight = st.sidebar.slider("Urban activity weight", 0.0, 1.0, 0.9, 0.05)
    population_weight = round(1.0 - light_weight, 2)
    st.sidebar.caption(f"Population weight: {population_weight:.2f}")

    business_pctile = st.sidebar.slider("Low competition threshold", 10, 60, 40, 5)
    score_pctile = st.sidebar.slider("Opportunity threshold", 50, 95, 70, 5)
    map_backend = st.sidebar.selectbox(
        "Map style", ["folium", "plotly"], index=1 if cfg.get("dashboard", "map_backend") == "plotly" else 1
    )
    show_raster = st.sidebar.checkbox("Show activity layer", value=True)
    comparison_mode = st.sidebar.checkbox("Compare scenarios", value=True)
    comparison_weights = st.sidebar.multiselect(
        "Scenario weights", [0.3, 0.5, 0.6, 0.7, 0.9], default=[0.3, 0.9]
    )

    region_key = "united_states" if region_name == "United States" else "europe"
    region_districts = Path("data") / f"{region_key}_districts.geojson"
    region_raster = Path("data") / f"{region_key}_night_lights.tif"
    districts_path = str(region_districts if region_districts.exists() else cfg.districts_path)
    raster_path = str(region_raster if region_raster.exists() else cfg.raster_path)

    if not region_districts.exists() or not region_raster.exists():
        st.sidebar.caption(f"Generating {region_name} market data for the current view…")
        from market_predictor.data.mock import generate_mock_data

        generate_mock_data(
            raster_path=region_raster,
            districts_path=region_districts,
            bbox=cfg.region_bbox(region_key),
            region=region_key,
        )
        districts_path = str(region_districts)
        raster_path = str(region_raster)

    @st.cache_data
    def load_zonal_stats(_districts: str, _raster: str) -> gpd.GeoDataFrame:
        districts = gpd.read_file(_districts)
        return extract_zonal_statistics(districts, _raster)

    def _prepare_region_data(base_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        filtered = _scope_region(base_gdf, region_name)
        return _add_display_names(filtered, region_name)

    if use_precomputed:
        loaded = load_precomputed(cfg.output_path)
        if loaded is None:
            st.error(f"No precomputed file at {cfg.output_path}. Run the pipeline first.")
            st.stop()
        zonal_gdf = loaded
    else:
        if not Path(districts_path).exists():
            st.warning("Data not found. Run: `python -m market_predictor.cli generate-data --mode mock`")
            st.stop()
        zonal_gdf = load_zonal_stats(districts_path, raster_path)

    from market_predictor.data.features import add_synthetic_features

    zonal_gdf = add_synthetic_features(zonal_gdf)

    cfg_override = AppConfig.load(overrides={"scoring": {"method": scoring_method}})
    scored_gdf = calculate_market_potential_score(
        zonal_gdf,
        light_weight=light_weight,
        population_weight=population_weight,
        method=scoring_method,
        feature_weights=cfg_override.get("scoring", "feature_weights"),
        normalize_weight_sum=True,
    )
    result_gdf = identify_high_potential_zones(
        scored_gdf,
        business_density_percentile=business_pctile,
        market_potential_percentile=score_pctile,
    )

    result_gdf = _prepare_region_data(result_gdf)
    if result_gdf.empty:
        st.warning(f"No districts match the selected region: {region_name}. Please switch regions or regenerate the data.")
        st.stop()
    score_cutoff = float(result_gdf["score_cutoff"].iloc[0])

    st.title("Market Expansion Opportunity Map")
    st.caption(
        "This view highlights the highest-potential expansion areas based on demand strength, local competition, and urban activity concentration."
    )
    st.caption(f"Focus: {region_name} • Model: {scoring_method.title()} • High-density urban weighting: {light_weight:.2f}")

    summary_col, gauge_col = st.columns([2, 1])
    top_zone = result_gdf.sort_values("market_potential_score", ascending=False).iloc[0]
    n_untapped = int(result_gdf["is_high_potential_untapped"].sum())

    with summary_col:
        score_bar = px.bar(
            result_gdf.sort_values("market_potential_score", ascending=False).head(10),
            x="display_name",
            y="market_potential_score",
            title="Market Potential Score by Area",
            color="market_potential_score",
            color_continuous_scale="Viridis",
        )
        score_bar.update_layout(
            margin=dict(t=40, b=20, l=10, r=10),
            height=220,
            showlegend=False,
            xaxis_title="Market Area",
            yaxis_title="Market Potential Score",
        )
        st.plotly_chart(score_bar, use_container_width=True)

    with gauge_col:
        fig_gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=_score_to_gauge_value(top_zone["market_potential_score"]),
                title={"text": f"Best-fit area: {top_zone['display_name']}"},
                number={"suffix": " / 100"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#2ca02c"},
                    "steps": [
                        {"range": [0, 40], "color": "#fde0dd"},
                        {"range": [40, 70], "color": "#fdd49e"},
                        {"range": [70, 100], "color": "#c7e9c0"},
                    ],
                    "threshold": {
                        "line": {"color": "black", "width": 3},
                        "thickness": 0.8,
                        "value": _score_to_gauge_value(score_cutoff),
                    },
                },
            )
        )
        fig_gauge.update_layout(height=220, margin=dict(t=40, b=10, l=20, r=20))
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.caption(f"Cutoff = {score_cutoff:.3f} → {_score_to_gauge_value(score_cutoff):.1f}/100")

    st.markdown("---")
    st.subheader("Priority Expansion Zones")
    st.metric("High-potential untapped areas", n_untapped)
    top_untapped = (
        result_gdf[result_gdf["is_high_potential_untapped"]]
        .sort_values("opportunity_rank")
        .drop_duplicates(subset=["display_name"])
        .head(5)
    )
    if not top_untapped.empty:
        display_top = top_untapped[["display_name", "market_potential_score", "current_business_count", "opportunity_rank"]].copy()
        display_top = display_top.rename(columns={
            "display_name": "Market Area",
            "market_potential_score": "Score",
            "current_business_count": "Current Businesses",
            "opportunity_rank": "Priority Rank",
        })
        st.dataframe(display_top, use_container_width=True, hide_index=True)
    else:
        st.info("No districts meet both cutoffs at current settings.")
    _download_buttons(result_gdf)

    st.markdown("---")
    st.subheader("🗺️ Market Opportunity Map")
    st.caption("Greener areas represent stronger demand and lower competitive pressure, making them the most attractive expansion candidates.")

    # Initialize session state for map stability
    if "last_map_hash" not in st.session_state:
        st.session_state.last_map_hash = ""
    if "last_comparison_hash" not in st.session_state:
        st.session_state.last_comparison_hash = ""

    if not result_gdf.empty:
        centroid_lon = float(result_gdf.geometry.centroid.x.mean())
        centroid_lat = float(result_gdf.geometry.centroid.y.mean())
        map_center = [centroid_lat, centroid_lon]
    elif region_name == "Europe":
        map_center = [52.5, 12.5]
    else:
        map_center = [39.5, -98.35]
    map_zoom = 4

    # Render maps with stable caching
    if comparison_mode and len(comparison_weights) >= 2:
        display_weights = comparison_weights[:2]
        cols = st.columns(2)
        comparison_gdf_list = []

        for lw in display_weights:
            pw = 1.0 - lw
            comp_scored = calculate_market_potential_score(
                zonal_gdf, light_weight=lw, population_weight=pw, method=scoring_method
            )
            comp_flagged = identify_high_potential_zones(
                comp_scored, business_pctile, score_pctile
            )
            comp_flagged = _prepare_region_data(comp_flagged).copy()
            comp_flagged["scenario_rate"] = round(float(lw), 2)
            comparison_gdf_list.append((lw, comp_flagged))

        comparison_hash = str(hash(tuple(lw for lw, _ in comparison_gdf_list)))
        st.session_state.last_comparison_hash = comparison_hash

        st.caption("Urban activity weighting shifts the expansion lens: lower values are more balanced, while higher values lean harder on dense city demand.")
        for col, (lw, comp_flagged) in zip(cols, comparison_gdf_list):
            comp_flagged = comp_flagged.copy()
            comp_flagged["scenario_rate"] = round(float(lw), 2)
            with col:
                st.markdown(f"### Scenario {lw:.2f}")
                st.caption(f"Urban activity profile: {lw:.2f}")
                if map_backend == "folium":
                    try:
                        map_obj = _build_folium_map(comp_flagged, raster_path, show_raster, _gdf_id=_gdf_hash(comp_flagged))
                        map_obj.location = map_center
                        map_obj.zoom_start = map_zoom
                        with st.container(border=True):
                            st_folium(map_obj, width=560, height=420, key=f"comp_map_{lw}", draggable=True)
                    except Exception:
                        fig = _build_plotly_map(comp_flagged)
                        with st.container(border=True):
                            st.plotly_chart(fig, width=560, height=420, key=f"comp_plotly_{lw}")
                else:
                    fig = _build_plotly_map(comp_flagged)
                    with st.container(border=True):
                        st.plotly_chart(fig, width=560, height=420, key=f"comp_plotly_{lw}")
    else:
        # Single map view with stable rendering
        result_gdf = result_gdf.copy()
        result_gdf["scenario_rate"] = round(float(light_weight), 2)
        result_hash = _gdf_hash(result_gdf)
        st.session_state.last_map_hash = result_hash

        if map_backend == "folium":
            try:
                map_obj = _build_folium_map(result_gdf, raster_path, show_raster, _gdf_id=result_hash)
                map_obj.location = map_center
                map_obj.zoom_start = map_zoom
                st_folium(map_obj, width=1200, height=640, key="main_map", draggable=True)
            except Exception:
                fig = _build_plotly_map(result_gdf)
                st.plotly_chart(fig, width=1200, height=640, key="main_plotly")
        else:
            fig = _build_plotly_map(result_gdf)
            st.plotly_chart(fig, width=1200, height=640, key="main_plotly")

    st.markdown("---")
    with st.expander("📊 Sensitivity Analysis"):
        sens_df = run_sensitivity_analysis(
            zonal_gdf, business_density_percentile=business_pctile, market_potential_percentile=score_pctile
        )
        sens_df = sens_df.merge(
            result_gdf[["district_id", "display_name", "market_area"]], on="district_id", how="left"
        )
        summary = rank_stability_summary(sens_df)
        summary = summary.merge(
            result_gdf[["district_id", "display_name", "market_area"]], on="district_id", how="left"
        )
        summary_display = summary[["display_name", "mean_rank", "rank_std", "mean_score", "flagged_fraction"]].copy()
        summary_display = summary_display.drop_duplicates(subset=["display_name"]).sort_values("mean_rank").reset_index(drop=True)
        summary_display = summary_display.rename(columns={
            "display_name": "Market Area",
            "mean_rank": "Mean Rank",
            "rank_std": "Rank Stability",
            "mean_score": "Average Score",
            "flagged_fraction": "Flagged Rate",
        })
        st.caption("This chart shows how stable each area remains as the urban-activity weight changes. Areas with higher scores and lower volatility are the most resilient expansion bets.")
        st.dataframe(summary_display.head(15), use_container_width=True, hide_index=True)
        fig = px.line(
            sens_df,
            x="light_weight",
            y="market_potential_score",
            color="display_name",
            title="Scenario Sensitivity: Market Potential by Area",
        )
        fig.update_layout(
            legend_title_text="Market Area",
            xaxis_title="Urban Activity Weight",
            yaxis_title="Market Potential Score",
        )
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("📄 Full District Table"):
        display_cols = [
            "display_name", "mean_night_light", "peak_night_light", "population_density",
            "median_income", "road_access_score", "competitor_count", "delivery_radius_km",
            "current_business_count", "market_potential_score",
            "is_high_potential_untapped", "opportunity_rank",
        ]
        available = [c for c in display_cols if c in result_gdf.columns]
        table_df = result_gdf[available].sort_values("market_potential_score", ascending=False).copy()
        table_df = table_df.drop_duplicates(subset=["display_name"]).reset_index(drop=True)
        table_df = table_df.rename(columns={
            "display_name": "Market Area",
            "mean_night_light": "Night Lights",
            "peak_night_light": "Peak Lights",
            "population_density": "Population Density",
            "median_income": "Median Income",
            "road_access_score": "Road Access",
            "competitor_count": "Competitors",
            "delivery_radius_km": "Delivery Radius (km)",
            "current_business_count": "Current Businesses",
            "market_potential_score": "Market Score",
            "is_high_potential_untapped": "Untapped",
            "opportunity_rank": "Priority Rank",
        })
        st.dataframe(table_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
