# Geospatial Expansion Predictor

Identifies high-potential, under-served districts for dark-store siting by blending
VIIRS-style night-light intensity with population density, extended MCDA features,
and spatial analysis — with an interactive Streamlit dashboard.

## Quick Start

```bash
pip install -e ".[dev,ml]"
python -m market_predictor.cli generate-data --mode mock
python -m market_predictor.cli run-pipeline
streamlit run visualize.py
```

## Project Structure

```
src/market_predictor/     # Main package
├── data/                 # Mock + real data acquisition, feature enrichment
├── pipeline/             # Zonal stats, scoring, spatial, opportunity, sensitivity
├── dashboard/            # Streamlit app
├── cli.py                # CLI entry point
└── config.py             # config.yaml loader
config.yaml               # Central configuration
docs/                     # Architecture + methodology
notebooks/                # End-to-end walkthrough
tests/                    # Unit + integration tests
Dockerfile                # Containerized Streamlit deployment
.github/workflows/ci.yml  # CI (pytest, ruff, mypy)
```

See [docs/architecture.md](docs/architecture.md) for a full system diagram.

## CLI Commands

```bash
# Generate synthetic data (default)
python -m market_predictor.cli generate-data --mode mock

# Generate from real sources (VIIRS, OSM, WorldPop)
python -m market_predictor.cli generate-data --mode real --boundary-source osm

# Run full pipeline
python -m market_predictor.cli run-pipeline --light-weight 0.6

# Load precomputed results (skip zonal stats)
python -m market_predictor.cli run-pipeline --skip-zonal

# Sensitivity analysis
python -m market_predictor.cli sensitivity --output-csv data/sensitivity_results.csv
```

Legacy entry points still work after `pip install -e .`:
- `python geo_data_mock.py`
- `python pipeline.py`
- `streamlit run visualize.py`

## Configuration

Edit `config.yaml` or set environment variables (`MP_SECTION__KEY=value`):

| Section | Key settings |
|---------|-------------|
| `data` | `mode`, paths, bbox, boundary source |
| `pipeline` | zonal backend, batch size, output paths |
| `scoring` | method (`weighted`/`mcda`/`pca`/`ml`), weights |
| `opportunity` | percentile cutoffs |
| `dashboard` | map backend (`folium`/`plotly`), raster overlay |

## Features

### Data & Realism
- **Mock mode:** synthetic VIIRS raster + 12×12 district grid
- **Real mode:** NOAA VIIRS night lights, OSM admin boundaries/POIs, WorldPop population
- **Extended features:** income, road access, competitor count, delivery radius

### Pipeline & Performance
- **Vectorized zonal stats** via `rasterstats` / `exactextract` (manual fallback)
- **Batch + multiprocessing** for large polygon sets
- **Persisted outputs:** GeoJSON + Parquet

### Scoring & Modeling
- Weighted, MCDA, PCA, XGBoost ML scoring
- Spatial lag + Moran's I
- Weight sensitivity analysis with rank stability

### Dashboard
- Fixed gauge threshold (uses actual score cutoff on 0–100 scale)
- Folium map with night-light raster overlay (no Mapbox token needed)
- Plotly choropleth alternative
- CSV/GeoJSON export of flagged zones
- Side-by-side comparison mode for weight settings

## Testing & Quality

```bash
pytest tests/ -v
ruff check src tests
mypy src/market_predictor
```

## Docker Deployment

```bash
docker build -t market-predictor .
docker run -p 8501:8501 market-predictor
```

## Methodology

See [docs/methodology.md](docs/methodology.md) for scoring formulas, opportunity
detection logic, and comparison to industry site-selection frameworks.

## Validated Behavior

The mock generator deliberately suppresses `current_business_count` in 3 high-light
districts — the pipeline surfaces exactly those as top-ranked opportunities.
