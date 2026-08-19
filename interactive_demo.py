#!/usr/bin/env python
"""
Interactive Demo Interface for Geospatial Market Potential Predictor
=====================================================================

This script provides an interactive menu-driven interface to explore and 
understand how the market potential predictor system works end-to-end.

Run with: python interactive_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Set up path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

import geopandas as gpd
import numpy as np
import pandas as pd
from tabulate import tabulate

from market_predictor.config import AppConfig
from market_predictor.data import generate_mock_data
from market_predictor.data.features import add_synthetic_features
from market_predictor.pipeline.opportunity import identify_high_potential_zones
from market_predictor.pipeline.runner import run_pipeline
from market_predictor.pipeline.scoring import calculate_market_potential_score
from market_predictor.pipeline.spatial import add_spatial_features
from market_predictor.pipeline.zonal import extract_zonal_statistics


class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def print_section(title: str, color: str = Colors.BOLD) -> None:
    """Print a formatted section title."""
    print(f"\n{color}{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}{Colors.END}\n")


def print_subsection(title: str) -> None:
    """Print a formatted subsection title."""
    print(f"\n{Colors.CYAN}{title}{Colors.END}")
    print(f"{'-'*70}")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ {message}{Colors.END}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def demo_1_architecture() -> None:
    """Show system architecture and workflow."""
    print_section("1. SYSTEM ARCHITECTURE & WORKFLOW", Colors.BOLD + Colors.BLUE)
    
    architecture = """
    PROJECT GOAL:
    ─────────────
    Identify high-potential, under-served districts for dark-store siting by
    combining geospatial data (night-light intensity, population density) with
    extended features (income, road access, competitors) and spatial analysis.

    COMPLETE WORKFLOW:
    ──────────────────
    
    ┌─────────────────────────────────────────────────────────────────┐
    │                      DATA GENERATION LAYER                      │
    ├─────────────────────────────────────────────────────────────────┤
    │  • Mock Mode (Synthetic):                                       │
    │    - Generate VIIRS-style night-light raster (300×300 pixels)   │
    │    - Create 12×12 grid of districts (~144 zones)               │
    │    - Synthetic population density & business counts             │
    │                                                                  │
    │  • Real Mode (Production):                                      │
    │    - NOAA VIIRS night-light data (actual satellite imagery)     │
    │    - OpenStreetMap admin boundaries & POIs                      │
    │    - WorldPop population data                                   │
    └─────────────────────────────────────────────────────────────────┘
                                    ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │                    FEATURE ENRICHMENT LAYER                     │
    ├─────────────────────────────────────────────────────────────────┤
    │  For each district, compute:                                    │
    │  • Mean & peak night-light intensity (zonal statistics)         │
    │  • Population density (from raster or census data)              │
    │  • Median income (synthetic or from census)                     │
    │  • Road access score (OSM network distance)                     │
    │  • Competitor count (existing businesses)                       │
    │  • Delivery radius capability                                   │
    └─────────────────────────────────────────────────────────────────┘
                                    ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │                    SCORING & ANALYSIS LAYER                     │
    ├─────────────────────────────────────────────────────────────────┤
    │  Scoring Methods:                                               │
    │  • Weighted: light_weight × normalized_light +                  │
    │              population_weight × normalized_population          │
    │  • MCDA: Multi-Criteria Decision Analysis (6 features)          │
    │  • PCA: Principal Component Analysis (dimensionality reduction) │
    │  • ML: XGBoost regression (when historical data available)      │
    │                                                                  │
    │  Spatial Analysis:                                              │
    │  • Moran's I: Measure spatial autocorrelation                   │
    │  • Spatial lag: Neighbor-weighted scores                        │
    └─────────────────────────────────────────────────────────────────┘
                                    ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │                   OPPORTUNITY IDENTIFICATION                    │
    ├─────────────────────────────────────────────────────────────────┤
    │  Identify "High-Potential Untapped" zones:                      │
    │  • HIGH potential: score ≥ market_potential_percentile cutoff   │
    │  • UNTAPPED: business_count ≤ business_density_percentile       │
    │  • Rank by opportunity score (potential × scarcity)             │
    └─────────────────────────────────────────────────────────────────┘
                                    ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │                      OUTPUTS & INSIGHTS                         │
    ├─────────────────────────────────────────────────────────────────┤
    │  • GeoJSON: All districts with scores & flags                   │
    │  • Parquet: Tabular results for analytics                       │
    │  • Dashboard: Interactive Streamlit visualization               │
    │    - Map with color-coded scores                                │
    │    - Gauge chart for top zone                                   │
    │    - Sensitivity analysis (weight variations)                   │
    │    - CSV/GeoJSON export of target zones                         │
    └─────────────────────────────────────────────────────────────────┘
    """
    print(architecture)
    
    print_subsection("Key Configuration Settings (config.yaml)")
    
    cfg = AppConfig.load()
    config_table = [
        ["Section", "Setting", "Current Value", "Purpose"],
        ["-" * 15, "-" * 20, "-" * 20, "-" * 30],
        ["data", "mode", cfg.get("data", "mode", default="mock"), "Data source (mock/real)"],
        ["data", "districts_path", cfg.districts_path, "GeoJSON file path"],
        ["data", "raster_path", cfg.raster_path, "Night-light raster path"],
        ["pipeline", "zonal_backend", cfg.get("pipeline", "zonal_backend", default="auto"), "Zonal stats engine"],
        ["scoring", "method", cfg.get("scoring", "method", default="weighted"), "Scoring algorithm"],
        ["scoring", "light_weight", cfg.get("scoring", "light_weight", default=0.6), "Light intensity weight"],
        ["scoring", "population_weight", cfg.get("scoring", "population_weight", default=0.4), "Population weight"],
        ["opportunity", "business_density_percentile", cfg.get("opportunity", "business_density_percentile", default=40), "Low density cutoff"],
        ["opportunity", "market_potential_percentile", cfg.get("opportunity", "market_potential_percentile", default=70), "High potential cutoff"],
        ["dashboard", "map_backend", cfg.get("dashboard", "map_backend", default="folium"), "Map visualization"],
    ]
    
    print(tabulate(config_table, headers="firstrow", tablefmt="grid"))


def demo_2_data_generation() -> None:
    """Demonstrate data generation process."""
    print_section("2. DATA GENERATION PROCESS", Colors.BOLD + Colors.BLUE)
    
    cfg = AppConfig.load()
    districts_path = cfg.districts_path
    raster_path = cfg.raster_path
    
    if Path(districts_path).exists() and Path(raster_path).exists():
        print_success("Data files already exist!")
        print_info(f"Districts: {districts_path}")
        print_info(f"Raster: {raster_path}")
    else:
        print_warning("Data files not found. Generating mock data...")
        try:
            generate_mock_data(raster_path=raster_path, districts_path=districts_path)
            print_success("Mock data generated successfully!")
        except Exception as e:
            print_error(f"Failed to generate data: {e}")
            return
    
    # Load and display data info
    print_subsection("Generated Data Statistics")
    
    try:
        districts = gpd.read_file(districts_path)
        print_info(f"Total districts: {len(districts)}")
        print_info(f"CRS: {districts.crs}")
        
        import rasterio
        with rasterio.open(raster_path) as src:
            raster_data = src.read(1)
            print_info(f"Raster shape: {raster_data.shape}")
            print_info(f"Raster value range: [{raster_data.min():.1f}, {raster_data.max():.1f}]")
            print_info(f"Raster CRS: {src.crs}")
        
        print_subsection("Sample District Data (first 5)")
        sample_cols = [c for c in districts.columns if c != 'geometry'][:5]
        display_df = districts[sample_cols].head(5)
        print(tabulate(display_df, headers="keys", tablefmt="grid", showindex=True))
        
    except Exception as e:
        print_error(f"Error loading data: {e}")


def demo_3_zonal_statistics() -> None:
    """Demonstrate zonal statistics extraction."""
    print_section("3. ZONAL STATISTICS (Night-Light Extraction)", Colors.BOLD + Colors.BLUE)
    
    print("""
    WHAT ARE ZONAL STATISTICS?
    ──────────────────────────
    For each district polygon, compute summary statistics from the raster:
    • MEAN: Average night-light intensity within district
    • MAX: Peak night-light intensity (brightest pixel)
    • COUNT: Number of pixels in district
    
    These become the core features for market potential scoring.
    
    BACKEND COMPARISON:
    ───────────────────
    """)
    
    backend_comparison = [
        ["Backend", "Speed", "Accuracy", "Requirements", "Notes"],
        ["-" * 12, "-" * 10, "-" * 12, "-" * 20, "-" * 30],
        ["rasterstats", "Medium", "High", "pip install rasterstats", "Widely used, reliable"],
        ["exactextract", "Fast", "Very High", "pip install exactextract", "Most accurate, GDAL"],
        ["manual", "Slow", "Good", "Standard library", "Fallback, no deps needed"],
        ["auto", "Variable", "Best available", "None", "Auto-selects best available"],
    ]
    print(tabulate(backend_comparison, headers="firstrow", tablefmt="grid"))
    
    print_subsection("Computing Zonal Statistics")
    
    cfg = AppConfig.load()
    districts_path = cfg.districts_path
    raster_path = cfg.raster_path
    
    try:
        if not Path(districts_path).exists():
            print_warning("Data not found. Run demo 2 first.")
            return
        
        print_info("Loading districts...")
        districts = gpd.read_file(districts_path)
        
        print_info("Extracting zonal statistics...")
        zonal_gdf = extract_zonal_statistics(districts, raster_path, backend="auto")
        
        print_success("Zonal statistics computed!")
        
        print_subsection("Sample Results (first 8 districts)")
        display_cols = [c for c in ["district_id", "mean_night_light", "peak_night_light", "pixel_count"] 
                       if c in zonal_gdf.columns]
        display_df = zonal_gdf[display_cols].head(8)
        print(tabulate(display_df, headers="keys", tablefmt="grid", showindex=False))
        
        print_subsection("Statistics Summary")
        stats_data = [
            ["Metric", "Mean", "Std Dev", "Min", "Max"],
            ["-" * 15, "-" * 10, "-" * 10, "-" * 10, "-" * 10],
        ]
        for col in ["mean_night_light", "peak_night_light"]:
            if col in zonal_gdf.columns:
                data = zonal_gdf[col].dropna()
                stats_data.append([
                    col,
                    f"{data.mean():.2f}",
                    f"{data.std():.2f}",
                    f"{data.min():.2f}",
                    f"{data.max():.2f}",
                ])
        print(tabulate(stats_data, headers="firstrow", tablefmt="grid"))
        
    except Exception as e:
        print_error(f"Error in zonal statistics: {e}")


def demo_4_feature_enrichment() -> None:
    """Demonstrate feature enrichment."""
    print_section("4. FEATURE ENRICHMENT", Colors.BOLD + Colors.BLUE)
    
    print("""
    EXTENDED FEATURES FOR MCDA SCORING
    ───────────────────────────────────
    
    In addition to night-light and population density, the system computes:
    
    1. MEDIAN INCOME
       ├─ Derived from: night-light intensity + population density
       ├─ Logic: brighter areas + dense populations = higher income
       └─ Range: $15,000 - $150,000 per capita
    
    2. ROAD ACCESS SCORE
       ├─ Derived from: OSM highway network distance (if osmnx available)
       ├─ Fallback: synthetic based on night-light intensity
       └─ Range: 0.0 - 1.0 (1.0 = best access)
    
    3. COMPETITOR COUNT
       ├─ Derived from: existing business database or synthetic
       ├─ Stored in: current_business_count
       └─ Range: 0 - 20+ businesses per district
    
    4. DELIVERY RADIUS KM
       ├─ Formula: 5.0 - (competitor_count × 0.15) + (road_access × 2)
       ├─ Logic: fewer competitors + better roads = larger radius
       └─ Range: 1.5 - 8.0 km
    
    PURPOSE: These features enable multi-criteria decision analysis (MCDA),
    giving a holistic view of market potential beyond just light/population.
    """)
    
    print_subsection("Computing Enhanced Features")
    
    cfg = AppConfig.load()
    
    try:
        # Load or generate data
        districts_path = cfg.districts_path
        raster_path = cfg.raster_path
        
        if not Path(districts_path).exists():
            print_warning("Data not found. Generating...")
            generate_mock_data(raster_path=raster_path, districts_path=districts_path)
        
        print_info("Loading districts and computing zonal stats...")
        districts = gpd.read_file(districts_path)
        zonal_gdf = extract_zonal_statistics(districts, raster_path, backend="auto")
        
        print_info("Adding synthetic features...")
        enriched_gdf = add_synthetic_features(zonal_gdf)
        
        print_success("Features enriched!")
        
        feature_cols = ["median_income", "road_access_score", "competitor_count", "delivery_radius_km"]
        available_cols = [c for c in feature_cols if c in enriched_gdf.columns]
        
        print_subsection("Sample Enriched Data (first 5 districts)")
        display_cols = ["district_id"] + available_cols
        display_df = enriched_gdf[display_cols].head(5).copy()
        for col in available_cols:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else x)
        print(tabulate(display_df, headers="keys", tablefmt="grid", showindex=False))
        
        print_subsection("Feature Statistics Summary")
        stats_data = [
            ["Feature", "Mean", "Std Dev", "Min", "Max"],
            ["-" * 20, "-" * 12, "-" * 12, "-" * 12, "-" * 12],
        ]
        for col in available_cols:
            data = enriched_gdf[col].dropna()
            stats_data.append([
                col,
                f"{data.mean():.2f}",
                f"{data.std():.2f}",
                f"{data.min():.2f}",
                f"{data.max():.2f}",
            ])
        print(tabulate(stats_data, headers="firstrow", tablefmt="grid"))
        
    except Exception as e:
        print_error(f"Error in feature enrichment: {e}")


def demo_5_scoring_methods() -> None:
    """Demonstrate different scoring methods."""
    print_section("5. MARKET POTENTIAL SCORING", Colors.BOLD + Colors.BLUE)
    
    print("""
    AVAILABLE SCORING METHODS
    ─────────────────────────
    
    1. WEIGHTED SCORE (Fastest, Simplest)
       ┌─────────────────────────────────────┐
       │ Score = w_light × L + w_pop × P    │
       │ where:                              │
       │   w_light = 0.6 (night-light weight)│
       │   w_pop = 0.4 (population weight)   │
       │   L, P = normalized [0, 1]          │
       └─────────────────────────────────────┘
       Use for: Quick assessments, real-time dashboards
    
    2. MCDA - Multi-Criteria Decision Analysis (Most Holistic)
       ┌─────────────────────────────────────────────────┐
       │ Score = Σ (w_i × normalized_feature_i)         │
       │ with 6 criteria:                                │
       │   • Night-light intensity (0.25)                │
       │   • Population density (0.20)                   │
       │   • Median income (0.15)                        │
       │   • Road access score (0.15)                    │
       │   • Competitor count (-0.10, inverted)          │
       │   • Delivery radius (0.10)                      │
       └─────────────────────────────────────────────────┘
       Use for: Comprehensive analysis with multiple factors
    
    3. PCA - Principal Component Analysis (Statistical)
       ┌──────────────────────────────────┐
       │ Reduce dimensions to main driver │
       │ Use PC1 as market potential      │
       └──────────────────────────────────┘
       Use for: Dimensionality reduction, noise filtering
    
    4. ML - Machine Learning (XGBoost)
       ┌────────────────────────────────────┐
       │ Train on historical store data:   │
       │   Input: 6 features                │
       │   Output: store revenue/performance│
       │ Predict market potential score    │
       └────────────────────────────────────┘
       Use for: Production systems with labeled data
    """)
    
    print_subsection("Computing Scores with Different Methods")
    
    cfg = AppConfig.load()
    
    try:
        # Prepare data
        districts_path = cfg.districts_path
        raster_path = cfg.raster_path
        
        if not Path(districts_path).exists():
            print_warning("Data not found. Generating...")
            generate_mock_data(raster_path=raster_path, districts_path=districts_path)
        
        print_info("Preparing data...")
        districts = gpd.read_file(districts_path)
        zonal_gdf = extract_zonal_statistics(districts, raster_path, backend="auto")
        enriched_gdf = add_synthetic_features(zonal_gdf)
        
        # Compute scores with different methods
        methods = ["weighted", "mcda", "pca"]
        scores_dict = {}
        
        for method in methods:
            print_info(f"Computing {method} scores...")
            try:
                scored = calculate_market_potential_score(
                    enriched_gdf.copy(),
                    light_weight=0.6,
                    population_weight=0.4,
                    method=method,
                    feature_weights=cfg.get("scoring", "feature_weights", default={}),
                )
                scores_dict[method] = scored
            except Exception as e:
                print_warning(f"Could not compute {method}: {e}")
        
        print_success("Scoring complete!")
        
        # Comparison table
        if scores_dict:
            print_subsection("Score Comparison (Top 5 Districts by Weighted Score)")
            top_indices = scores_dict["weighted"].nlargest(5, "market_potential_score").index
            
            comparison_data = []
            for idx in top_indices:
                row = [enriched_gdf.loc[idx, "district_id"]]
                for method in methods:
                    if method in scores_dict:
                        score = scores_dict[method].loc[idx, "market_potential_score"]
                        row.append(f"{score:.3f}")
                comparison_data.append(row)
            
            headers = ["District"] + [m.upper() for m in methods if m in scores_dict]
            print(tabulate(comparison_data, headers=headers, tablefmt="grid"))
            
            # Statistics
            print_subsection("Score Statistics")
            for method in methods:
                if method in scores_dict:
                    scores = scores_dict[method]["market_potential_score"]
                    print_info(f"{method.upper():10} - Mean: {scores.mean():.3f}, Std: {scores.std():.3f}, "
                             f"Min: {scores.min():.3f}, Max: {scores.max():.3f}")
        
    except Exception as e:
        print_error(f"Error in scoring: {e}")


def demo_6_opportunity_identification() -> None:
    """Demonstrate opportunity zone identification."""
    print_section("6. HIGH-POTENTIAL UNTAPPED ZONE IDENTIFICATION", Colors.BOLD + Colors.BLUE)
    
    print("""
    OPPORTUNITY IDENTIFICATION LOGIC
    ─────────────────────────────────
    
    A district is flagged as a TARGET OPPORTUNITY if it meets TWO criteria:
    
    CRITERION 1: HIGH POTENTIAL
    ┌──────────────────────────────────────────────────┐
    │ market_potential_score ≥                         │
    │   (market_potential_percentile-th percentile)    │
    │                                                   │
    │ Default: 70th percentile (top 30% of markets)   │
    │ Result: Only markets with strong fundamentals    │
    └──────────────────────────────────────────────────┘
    
    CRITERION 2: UNTAPPED (Low Competition)
    ┌──────────────────────────────────────────────────┐
    │ current_business_count ≤                         │
    │   (business_density_percentile-th percentile)    │
    │                                                   │
    │ Default: 40th percentile (bottom 40% density)   │
    │ Result: Markets with fewer existing competitors  │
    └──────────────────────────────────────────────────┘
    
    OPPORTUNITY RANKING
    ───────────────────
    Zones are ranked by "opportunity_score":
      opportunity_score = market_potential × scarcity_factor
    
    This prioritizes zones that are both valuable AND less competitive.
    """)
    
    print_subsection("Running Full Pipeline")
    
    cfg = AppConfig.load()
    
    try:
        print_info("Generating/loading data...")
        districts_path = cfg.districts_path
        raster_path = cfg.raster_path
        
        if not Path(districts_path).exists():
            generate_mock_data(raster_path=raster_path, districts_path=districts_path)
        
        print_info("Running full pipeline...")
        result_gdf = run_pipeline(
            districts_path=districts_path,
            raster_path=raster_path,
            config=cfg,
        )
        
        print_success("Pipeline complete!")
        
        # Count results
        total = len(result_gdf)
        untapped = len(result_gdf[result_gdf["is_high_potential_untapped"]])
        pct = (untapped / total * 100) if total > 0 else 0
        
        print_subsection("Opportunity Identification Results")
        print_info(f"Total districts analyzed: {total}")
        print_info(f"High-potential untapped zones found: {untapped} ({pct:.1f}%)")
        
        # Display top opportunities
        if untapped > 0:
            print_subsection("Top 10 Target Zones (Ranked by Opportunity)")
            top_opps = result_gdf[result_gdf["is_high_potential_untapped"]].nsmallest(10, "opportunity_rank")
            
            display_cols = ["district_id", "market_potential_score", "current_business_count", "opportunity_rank"]
            available_cols = [c for c in display_cols if c in top_opps.columns]
            display_df = top_opps[available_cols].reset_index(drop=True)
            
            # Format numeric columns
            for col in ["market_potential_score", "opportunity_rank"]:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:.3f}" if isinstance(x, (int, float)) else x)
            
            print(tabulate(display_df, headers="keys", tablefmt="grid", showindex=False))
        else:
            print_warning("No high-potential untapped zones found at current thresholds.")
            print_info("Try adjusting percentile thresholds in config.yaml or via CLI.")
        
        # Spatial statistics
        if "morans_i" in result_gdf.attrs:
            print_subsection("Spatial Autocorrelation")
            morans = result_gdf.attrs.get("morans_i")
            print_info(f"Moran's I: {morans:.4f}")
            print_info("(Value between -1 and +1; >0 indicates spatial clustering)")
        
    except Exception as e:
        print_error(f"Error in opportunity identification: {e}")


def demo_7_dashboard_preview() -> None:
    """Show dashboard information."""
    print_section("7. INTERACTIVE STREAMLIT DASHBOARD", Colors.BOLD + Colors.BLUE)
    
    print("""
    THE INTERACTIVE DASHBOARD
    ──────────────────────────
    
    The Streamlit dashboard provides real-time visualization and interaction:
    
    COMPONENTS:
    ───────────
    
    1. SIDEBAR CONTROLS (Left Panel)
       ├─ Load precomputed results checkbox
       ├─ Scoring method selector (weighted/mcda/pca/ml)
       ├─ Night-light weight slider (0.0 - 1.0)
       ├─ Population weight auto-calculator (1.0 - night_weight)
       ├─ Business density percentile slider (10 - 60)
       ├─ Market potential percentile slider (50 - 95)
       ├─ Map backend selector (folium/plotly)
       ├─ Night-light raster layer toggle
       ├─ Comparison mode toggle
       └─ Comparison weights multiselect
    
    2. MAIN PANEL (Center)
       ├─ Title & formula explanation
       ├─ Key metrics gauge
       │  └─ Top zone score on 0-100 scale
       ├─ Summary statistics
       │  └─ Count of high-potential untapped zones
       ├─ Top-ranked target zones table
       ├─ Download buttons (CSV, GeoJSON)
       ├─ Interactive map
       │  ├─ Color-coded districts by score
       │  ├─ Red star markers for target zones
       │  ├─ Optional night-light raster overlay
       │  └─ Folium/Plotly alternatives
       ├─ Sensitivity analysis expander
       │  └─ Rank stability as weight varies
       └─ Full data table expander
    
    INTERACTIVE FEATURES:
    ────────────────────
    
    • REAL-TIME RECALCULATION
      Change any slider → Scores update immediately (cached)
    
    • COMPARISON MODE
      View multiple weight configurations side-by-side
    
    • SENSITIVITY ANALYSIS
      See how zone rankings change with different weight settings
    
    • DATA EXPORT
      Download flagged zones as CSV or GeoJSON
    
    • HOVER TOOLTIPS
      Hover over districts on map to see detailed stats
    """)
    
    print_subsection("To Launch the Dashboard")
    print_success("Run one of these commands:")
    print(f"  {Colors.BOLD}streamlit run visualize.py{Colors.END}")
    print(f"  {Colors.BOLD}python -m streamlit run src/market_predictor/dashboard/app.py{Colors.END}")
    print()
    print_info("The dashboard will open in your browser at: http://localhost:8501")


def demo_8_full_workflow() -> None:
    """Run the complete workflow end-to-end."""
    print_section("8. END-TO-END WORKFLOW DEMONSTRATION", Colors.BOLD + Colors.BOLD + Colors.BLUE)
    
    print("""
    RUNNING THE COMPLETE PIPELINE
    ────────────────────────────────
    
    This will execute the entire workflow:
    
      1. Data Generation       (mock VIIRS + districts)
      2. Zonal Statistics      (night-light extraction)
      3. Feature Enrichment    (income, roads, competitors)
      4. Scoring              (market potential calculation)
      5. Spatial Analysis     (Moran's I, spatial lag)
      6. Opportunity ID       (high-potential + untapped)
      7. Persistence          (save to GeoJSON + Parquet)
    """)
    
    response = input(f"\n{Colors.YELLOW}Run full pipeline? (y/n): {Colors.END}").strip().lower()
    if response != "y":
        print_info("Skipped.")
        return
    
    cfg = AppConfig.load()
    
    try:
        print_info("Starting full pipeline...")
        result = run_pipeline(config=cfg)
        
        print_success("Full pipeline completed!")
        
        print_subsection("Pipeline Results Summary")
        print_info(f"Processed: {len(result)} districts")
        untapped = len(result[result["is_high_potential_untapped"]])
        print_info(f"Target zones identified: {untapped}")
        
        if "morans_i" in result.attrs:
            print_info(f"Spatial autocorrelation (Moran's I): {result.attrs['morans_i']:.4f}")
        
        print_info(f"Output files:")
        print_info(f"  • {cfg.output_path}")
        print_info(f"  • {cfg.parquet_path}")
        
        # Top zones
        top_5 = result.nlargest(5, "market_potential_score")
        print_subsection("Top 5 Zones by Market Potential")
        display_cols = ["district_id", "mean_night_light", "population_density", "market_potential_score"]
        available_cols = [c for c in display_cols if c in top_5.columns]
        print(tabulate(top_5[available_cols], headers="keys", tablefmt="grid", showindex=False))
        
    except Exception as e:
        print_error(f"Error in pipeline: {e}")


def demo_9_configuration() -> None:
    """Show configuration options."""
    print_section("9. CONFIGURATION & CUSTOMIZATION", Colors.BOLD + Colors.BLUE)
    
    print("""
    CONFIGURATION METHODS
    ─────────────────────
    
    The system uses a three-level override hierarchy:
    
    LEVEL 1: DEFAULTS (in config.py)
    ├─ Built-in hardcoded defaults
    └─ Fallback if nothing else specified
    
    LEVEL 2: config.yaml FILE
    ├─ Central configuration file in project root
    ├─ YAML format for easy editing
    └─ Override defaults for your setup
    
    LEVEL 3: ENVIRONMENT VARIABLES
    ├─ MP_SECTION__KEY=value pattern
    ├─ Example: MP_SCORING__METHOD=mcda
    ├─ Highest priority (production deployments)
    └─ Override both defaults and config.yaml
    
    LEVEL 4: CLI FLAGS
    ├─ Command-line arguments
    ├─ Example: python -m market_predictor.cli run-pipeline --light-weight 0.8
    └─ Override for one-off executions
    """)
    
    print_subsection("Current config.yaml")
    
    cfg_path = Path("config.yaml")
    if cfg_path.exists():
        with open(cfg_path) as f:
            content = f.read()
        # Show with syntax highlighting (basic)
        for line in content.split("\n"):
            if line.startswith("#"):
                print(f"{Colors.CYAN}{line}{Colors.END}")
            elif ":" in line and not line.strip().startswith("#"):
                parts = line.split(":", 1)
                print(f"{Colors.BOLD}{parts[0]}{Colors.END}:{parts[1]}")
            else:
                print(line)
    else:
        print_error("config.yaml not found in current directory")
    
    print_subsection("Common Customizations")
    
    customizations = [
        [
            "Change scoring method",
            "config.yaml: scoring.method: mcda",
            "scoring.method determines how potential is calculated"
        ],
        [
            "Adjust light/population weights",
            "config.yaml: scoring.light_weight: 0.8",
            "Must sum to 1.0 with population_weight"
        ],
        [
            "Modify opportunity thresholds",
            "config.yaml: opportunity.market_potential_percentile: 75",
            "Higher = fewer but stronger opportunities"
        ],
        [
            "Use real data instead of mock",
            "config.yaml: data.mode: real",
            "Requires VIIRS, OSM, WorldPop access"
        ],
        [
            "Change zonal backend",
            "config.yaml: pipeline.zonal_backend: exactextract",
            "auto, rasterstats, exactextract, or manual"
        ],
        [
            "Enable multiprocessing",
            "config.yaml: pipeline.use_multiprocessing: true",
            "Speeds up large datasets (manual backend only)"
        ],
    ]
    
    print(tabulate(customizations, headers=["Customization", "Setting", "Note"], tablefmt="grid"))


def print_menu() -> None:
    """Print the main menu."""
    print_section("GEOSPATIAL MARKET POTENTIAL PREDICTOR", Colors.BOLD + Colors.GREEN)
    print(f"""
{Colors.CYAN}Interactive Demo & Workflow Guide{Colors.END}

{Colors.BOLD}MAIN MENU{Colors.END}
─────────────────────────────────────────

1.  System Architecture & Workflow Overview
2.  Data Generation Process
3.  Zonal Statistics (Night-Light Extraction)
4.  Feature Enrichment (Extended MCDA Features)
5.  Market Potential Scoring Methods
6.  High-Potential Untapped Zone Identification
7.  Interactive Streamlit Dashboard
8.  Full End-to-End Pipeline Execution
9.  Configuration & Customization
10. View Complete Codebase Structure
11. Help & Documentation
0.  Exit

{Colors.BOLD}Choose an option (0-11):{Colors.END}
""")


def demo_10_codebase_structure() -> None:
    """Show codebase structure."""
    print_section("10. COMPLETE CODEBASE STRUCTURE", Colors.BOLD + Colors.BLUE)
    
    structure = """
    PROJECT ROOT
    ├── config.yaml                        Central configuration file
    ├── requirements.txt                   Core dependencies
    ├── pyproject.toml                     Package metadata & optional extras
    ├── Dockerfile                         Container definition
    ├── pyrightconfig.json                 Type checking config
    │
    ├── src/market_predictor/              Main package
    │   ├── __init__.py
    │   ├── cli.py                         CLI entry point (generate-data, run-pipeline, sensitivity)
    │   ├── config.py                      YAML config loader with env overrides
    │   ├── logging_config.py              Logging setup
    │   │
    │   ├── data/                          Data acquisition & enrichment layer
    │   │   ├── __init__.py
    │   │   ├── mock.py                    Synthetic VIIRS raster + district grid
    │   │   ├── real.py                    NOAA VIIRS, OSM, WorldPop integration
    │   │   └── features.py                Feature enrichment (income, roads, competitors)
    │   │
    │   ├── pipeline/                      Core scoring & analysis pipeline
    │   │   ├── __init__.py
    │   │   ├── zonal.py                   Zonal statistics extraction (rasterstats/exactextract/manual)
    │   │   ├── scoring.py                 Market potential scoring (weighted/MCDA/PCA/ML)
    │   │   ├── spatial.py                 Spatial analysis (Moran's I, spatial lag)
    │   │   ├── opportunity.py             High-potential untapped zone identification
    │   │   ├── sensitivity.py             Weight sensitivity & rank stability analysis
    │   │   └── runner.py                  Pipeline orchestration & persistence
    │   │
    │   └── dashboard/                     Streamlit dashboard
    │       ├── __init__.py
    │       └── app.py                     Interactive Streamlit UI (maps, charts, sensitivity)
    │
    ├── tests/                             Test suite
    │   ├── test_opportunity.py
    │   ├── test_pipeline.py
    │   ├── test_scoring.py
    │   ├── test_zonal.py
    │   └── fixtures/                      Test data & fixtures
    │
    ├── docs/                              Documentation
    │   ├── architecture.md                System architecture & data flow
    │   └── methodology.md                 Technical methodology details
    │
    ├── notebooks/                         Jupyter notebooks
    │   └── walkthrough.ipynb              End-to-end workflow walkthrough
    │
    ├── data/                              Data directory
    │   ├── districts.geojson              District polygons
    │   ├── night_lights.tif               Raster data
    │   ├── pipeline_results.geojson       Pipeline output (GeoJSON)
    │   ├── pipeline_results.parquet       Pipeline output (Parquet)
    │   └── districts.geojson              Original district polygons
    │
    ├── geo_data_mock.py                   Legacy mock data generator
    ├── pipeline.py                        Legacy pipeline runner
    ├── visualize.py                       Legacy dashboard entry point
    │
    ├── .github/
    │   └── workflows/ci.yml               CI/CD pipeline (pytest, ruff, mypy)
    │
    └── README.md                          Project documentation
    
    DEPENDENCY TREE
    ───────────────
    Core Dependencies:
      • geopandas + shapely + rasterio      Geospatial processing
      • pandas + numpy + pyarrow            Data manipulation
      • scikit-learn                        PCA & preprocessing
      • streamlit + folium + plotly         Visualization & UI
      • pyyaml                              Configuration
      • requests                            HTTP requests
    
    Optional Dependencies:
      • xgboost [ml]                        Machine learning scoring
      • osmnx [roads]                       OSM road network access
      • exactextract [extract]              High-performance zonal stats
      • pytest, ruff, mypy [dev]            Testing & QA
    """
    
    print(structure)


def demo_11_help() -> None:
    """Show help and quick-start guide."""
    print_section("11. HELP & QUICK-START GUIDE", Colors.BOLD + Colors.BLUE)
    
    help_text = f"""
    QUICK START (3 STEPS)
    ─────────────────────
    
    {Colors.BOLD}Step 1: Install Dependencies{Colors.END}
      pip install -e ".[dev,ml]"
    
    {Colors.BOLD}Step 2: Generate Data{Colors.END}
      python -m market_predictor.cli generate-data --mode mock
    
    {Colors.BOLD}Step 3: Run Pipeline{Colors.END}
      python -m market_predictor.cli run-pipeline
    
    {Colors.BOLD}Step 4: View Dashboard{Colors.END}
      streamlit run visualize.py
    
    ────────────────────────────────────────────────────────────
    
    CLI COMMANDS
    ────────────
    
    {Colors.BOLD}Data Generation:{Colors.END}
      python -m market_predictor.cli generate-data --mode mock
      python -m market_predictor.cli generate-data --mode real --boundary-source osm
    
    {Colors.BOLD}Pipeline Execution:{Colors.END}
      python -m market_predictor.cli run-pipeline --light-weight 0.6
      python -m market_predictor.cli run-pipeline --skip-zonal  # Load precomputed
      python -m market_predictor.cli run-pipeline --output custom_output.geojson
    
    {Colors.BOLD}Sensitivity Analysis:{Colors.END}
      python -m market_predictor.cli sensitivity --output-csv results.csv
    
    ────────────────────────────────────────────────────────────
    
    ENVIRONMENT VARIABLES (for production)
    ──────────────────────────────────────
    
    MP_DATA__MODE=real                          # Switch to real data
    MP_SCORING__METHOD=mcda                     # Use MCDA scoring
    MP_SCORING__LIGHT_WEIGHT=0.8                # Adjust light weight
    MP_OPPORTUNITY__MARKET_POTENTIAL_PERCENTILE=75  # Stricter threshold
    
    ────────────────────────────────────────────────────────────
    
    TESTING & QUALITY
    ─────────────────
    
    {Colors.BOLD}Run Tests:{Colors.END}
      pytest tests/ -v
    
    {Colors.BOLD}Code Quality:{Colors.END}
      ruff check src tests
      mypy src/market_predictor
    
    ────────────────────────────────────────────────────────────
    
    COMMON ISSUES & SOLUTIONS
    ─────────────────────────
    
    {Colors.RED}✗ "No module named 'market_predictor'"{Colors.END}
    → Solution: Install package with: pip install -e .
    
    {Colors.RED}✗ "rasterstats not found"{Colors.END}
    → Solution: Install with: pip install rasterstats
    → Or use: --zonal-backend manual (slower but always works)
    
    {Colors.RED}✗ "xgboost not found"{Colors.END}
    → Solution: Install with: pip install xgboost
    → Or use different scoring method: --method weighted
    
    {Colors.RED}✗ "Data files not found"{Colors.END}
    → Solution: Generate data first: python -m market_predictor.cli generate-data
    
    ────────────────────────────────────────────────────────────
    
    NEXT STEPS
    ──────────
    
    1. Explore the architecture (Menu 1)
    2. Generate mock data (Menu 2)
    3. Run the full pipeline (Menu 8)
    4. Launch the interactive dashboard
    5. Modify config.yaml for your use case
    6. Integrate with your own data sources
    
    For detailed documentation:
    • docs/architecture.md    - System design & data flow
    • docs/methodology.md     - Technical methodology
    • README.md               - Project overview
    • notebooks/walkthrough.ipynb - Interactive notebook
    """
    
    print(help_text)


def main() -> None:
    """Main interactive menu loop."""
    try:
        while True:
            print_menu()
            choice = input().strip()
            
            if choice == "0":
                print(f"\n{Colors.GREEN}Thank you for exploring the Market Potential Predictor!{Colors.END}\n")
                break
            elif choice == "1":
                demo_1_architecture()
            elif choice == "2":
                demo_2_data_generation()
            elif choice == "3":
                demo_3_zonal_statistics()
            elif choice == "4":
                demo_4_feature_enrichment()
            elif choice == "5":
                demo_5_scoring_methods()
            elif choice == "6":
                demo_6_opportunity_identification()
            elif choice == "7":
                demo_7_dashboard_preview()
            elif choice == "8":
                demo_8_full_workflow()
            elif choice == "9":
                demo_9_configuration()
            elif choice == "10":
                demo_10_codebase_structure()
            elif choice == "11":
                demo_11_help()
            else:
                print_error("Invalid option. Please try again.")
            
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")
    
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.END}\n")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
