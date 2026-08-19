# Quick Reference Guide

## 🚀 Common Usage Scenarios

### Scenario 1: First-Time Setup & Exploration

**Goal**: Understand how the system works with synthetic data

```bash
# Step 1: Activate environment
cd "Geospatial Micro-Level Market Potential Predictor"
source .venv/bin/activate

# Step 2: Launch interactive demo
python interactive_demo.py

# Select these options in order:
# 1. System Architecture (learn the workflow)
# 2. Data Generation (see mock data creation)
# 3. Zonal Statistics (understand data extraction)
# 4. Feature Enrichment (see MCDA features)
# 5. Scoring Methods (compare algorithms)
# 6. Opportunity Identification (find target zones)
# 11. Help & Quick-Start Guide

# Duration: ~20 minutes
```

---

### Scenario 2: Generate Data & Run Pipeline

**Goal**: Create synthetic data and compute market potential scores

```bash
source .venv/bin/activate

# Generate mock data (300x300 raster + 144 districts)
python -m market_predictor.cli generate-data --mode mock

# Run full pipeline with default settings
python -m market_predictor.cli run-pipeline

# Check results
ls -la data/
# Output: districts.geojson, night_lights.tif, pipeline_results.geojson, pipeline_results.parquet

# View summary
python -c "
import geopandas as gpd
result = gpd.read_file('data/pipeline_results.geojson')
print(f'Total districts: {len(result)}')
untapped = result[result['is_high_potential_untapped']]
print(f'High-potential untapped: {len(untapped)}')
print(untapped[['district_id', 'market_potential_score']].head())
"

# Duration: ~3-5 minutes
```

---

### Scenario 3: Interactive Dashboard Exploration

**Goal**: Visualize scores and experiment with different parameters

```bash
source .venv/bin/activate

# Ensure data exists
python -m market_predictor.cli generate-data --mode mock
python -m market_predictor.cli run-pipeline

# Launch dashboard
streamlit run visualize.py

# In the dashboard, try:
# 1. Drag "Night Light Weight" slider from 0.3 to 0.9
#    → Watch scores and zone rankings change
# 2. Toggle "Comparison mode" 
#    → See 3 maps with different weights side-by-side
# 3. Expand "Sensitivity Analysis" expander
#    → View how rankings change with weight variations
# 4. Expand "Full District Table" expander
#    → Download flagged zones as CSV/GeoJSON

# Duration: ~10 minutes
# Portal: http://localhost:8501
```

---

### Scenario 4: Change Scoring Method

**Goal**: Compare different market potential algorithms

```bash
source .venv/bin/activate

# Using config.yaml
sed -i '' 's/method: weighted/method: mcda/' config.yaml
python -m market_predictor.cli run-pipeline

# Or using CLI flag
python -m market_predictor.cli run-pipeline \
  --config config.yaml \
  --method mcda

# Or using environment variable
MP_SCORING__METHOD=pca python -m market_predictor.cli run-pipeline

# Compare results
python -c "
import geopandas as gpd

for method in ['weighted', 'mcda', 'pca']:
    print(f'\n{method.upper()}')
    gdf = gpd.read_file('data/pipeline_results.geojson')
    top5 = gdf.nlargest(5, 'market_potential_score')
    print(top5[['district_id', 'market_potential_score']].to_string())
"

# Duration: ~5 minutes
```

Available methods:
- **weighted** (fast, simple) - Linear combination of 2 features
- **mcda** (holistic) - Multi-Criteria Decision Analysis with 6 features
- **pca** (statistical) - Principal Component Analysis
- **ml** (advanced) - XGBoost machine learning (requires historical data)

---

### Scenario 5: Adjust Opportunity Thresholds

**Goal**: Find more or fewer target zones

```bash
source .venv/bin/activate

# Method 1: Modify config.yaml
# Change these values:
# - market_potential_percentile: 70 → 80 (stricter = fewer zones)
# - business_density_percentile: 40 → 30 (stricter = fewer zones)

python -m market_predictor.cli run-pipeline

# Method 2: Use environment variables
export MP_OPPORTUNITY__MARKET_POTENTIAL_PERCENTILE=85
export MP_OPPORTUNITY__BUSINESS_DENSITY_PERCENTILE=25
python -m market_predictor.cli run-pipeline

# View results
python -c "
import geopandas as gpd
result = gpd.read_file('data/pipeline_results.geojson')
untapped = result[result['is_high_potential_untapped']]
print(f'Found {len(untapped)} high-potential untapped zones')
"

# Duration: ~3 minutes
```

---

### Scenario 6: Sensitivity Analysis

**Goal**: Understand how zone rankings change with weight variations

```bash
source .venv/bin/activate

# Run sensitivity analysis
python -m market_predictor.cli sensitivity \
  --output-csv data/sensitivity_results.csv

# Results saved to:
# - data/sensitivity_results.csv (full data)
# - data/sensitivity_summary.csv (rank stability)

# View in Python
import pandas as pd
summary = pd.read_csv('data/sensitivity_summary.csv')
print(summary.head(10))

# Or view interactively in dashboard (Menu 6 > Sensitivity Analysis)

# Duration: ~2 minutes
```

---

### Scenario 7: Use Your Own Data

**Goal**: Analyze your own geographic regions

```bash
source .venv/bin/activate

# Method 1: Modify config.yaml to point to your files
# data:
#   districts_path: /path/to/your/districts.geojson
#   raster_path: /path/to/your/night_lights.tif

python -m market_predictor.cli run-pipeline

# Method 2: Real data from public sources (VIIRS, OSM, WorldPop)
python -m market_predictor.cli generate-data --mode real

# Requirements for real mode:
# - Bounding box defined in config.yaml
# - Internet connectivity (downloads from NOAA, OSM, WorldPop)
# - ~10-30 minutes depending on region size

# Duration: 5-30 minutes depending on data source
```

---

### Scenario 8: Export Results for Analysis

**Goal**: Get data into Excel, GIS, or analytics tools

```bash
source .venv/bin/activate

# After running pipeline, files are at:
# - data/pipeline_results.geojson    (import into ArcGIS/QGIS)
# - data/pipeline_results.parquet    (load into pandas/duckdb)

# Export flagged zones only (via dashboard)
# Dashboard → Download CSV / Download GeoJSON

# Or programmatically:
import geopandas as gpd

result = gpd.read_file('data/pipeline_results.geojson')
flagged = result[result['is_high_potential_untapped']]

# Export to CSV
flagged.drop(columns='geometry').to_csv('target_zones.csv', index=False)

# Export to GeoJSON
flagged.to_file('target_zones.geojson', driver='GeoJSON')

# Export to Excel (requires openpyxl)
flagged.drop(columns='geometry').to_excel('target_zones.xlsx', index=False)

# Duration: ~2 minutes
```

---

### Scenario 9: Run Tests & Quality Checks

**Goal**: Verify code quality and run test suite

```bash
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_scoring.py -v

# Run with coverage
pytest tests/ --cov=src/market_predictor --cov-report=html

# Code quality checks
ruff check src tests                    # Linter
mypy src/market_predictor              # Type checker

# Duration: ~5 minutes
```

---

### Scenario 10: Integrate with Jupyter Notebook

**Goal**: Interactive exploration in notebook

```bash
source .venv/bin/activate

# Launch Jupyter
jupyter notebook notebooks/walkthrough.ipynb

# Or create new notebook
jupyter notebook

# In notebook:
import sys
sys.path.insert(0, 'src')

from market_predictor.pipeline.runner import run_pipeline
from market_predictor.config import AppConfig

cfg = AppConfig.load()
result = run_pipeline(config=cfg)

# Explore interactively
result.head()
result['market_potential_score'].describe()

# Visualize
result.plot(column='market_potential_score', figsize=(12, 10))
```

---

## 📋 Command Reference

### Data Generation

```bash
# Mock (synthetic) data
python -m market_predictor.cli generate-data --mode mock

# Real data from public sources
python -m market_predictor.cli generate-data --mode real --boundary-source osm
```

### Pipeline Execution

```bash
# Full pipeline with defaults
python -m market_predictor.cli run-pipeline

# Custom light weight (night-light emphasis)
python -m market_predictor.cli run-pipeline --light-weight 0.8

# Skip zonal statistics (load precomputed)
python -m market_predictor.cli run-pipeline --skip-zonal

# Custom output path
python -m market_predictor.cli run-pipeline --output my_results.geojson

# With scoring method
python -m market_predictor.cli run-pipeline --method mcda
```

### Sensitivity Analysis

```bash
# Run with default settings
python -m market_predictor.cli sensitivity

# Custom output file
python -m market_predictor.cli sensitivity --output-csv results.csv
```

### Dashboard

```bash
# Using visualize.py
streamlit run visualize.py

# Using app directly
python -m streamlit run src/market_predictor/dashboard/app.py
```

### Interactive Demo

```bash
python interactive_demo.py
```

---

## 🔍 File Locations

| Purpose | Path |
|---------|------|
| Configuration | `config.yaml` |
| Districts (input) | `data/districts.geojson` |
| Night-light raster | `data/night_lights.tif` |
| Pipeline results (GeoJSON) | `data/pipeline_results.geojson` |
| Pipeline results (Parquet) | `data/pipeline_results.parquet` |
| Core pipeline | `src/market_predictor/pipeline/runner.py` |
| Scoring algorithms | `src/market_predictor/pipeline/scoring.py` |
| Dashboard | `src/market_predictor/dashboard/app.py` |
| Tests | `tests/` |
| Documentation | `docs/architecture.md`, `docs/methodology.md` |

---

## ⚡ Performance Tips

### Speed Up Analysis

1. **Skip regenerating data**
   ```bash
   python -m market_predictor.cli run-pipeline --skip-zonal
   ```

2. **Use faster backend**
   ```bash
   # In config.yaml
   pipeline:
     zonal_backend: exactextract  # Faster than rasterstats
   ```

3. **Batch processing**
   ```bash
   # In config.yaml
   pipeline:
     use_multiprocessing: true
     n_workers: 4
   ```

4. **Cache in Streamlit**
   - Dashboard uses @st.cache_data by default
   - Already optimized for repeated runs

### Memory Optimization

- Large rasters: Use smaller resolution (300×300 is default)
- Many districts: Enable batching with multiprocessing
- Keep Parquet format for analytics (smaller than GeoJSON)

---

## 🐛 Troubleshooting

### "No module named 'market_predictor'"
```bash
pip install -e ".[dev]"
```

### "rasterstats not found"
```bash
pip install rasterstats
# OR use manual backend
python -m market_predictor.cli run-pipeline \
  --config <(echo "pipeline:\n  zonal_backend: manual")
```

### "xgboost not found" (when using ML method)
```bash
pip install xgboost
# OR use different method
python -m market_predictor.cli run-pipeline --method mcda
```

### Data files not found
```bash
python -m market_predictor.cli generate-data --mode mock
```

### Streamlit won't connect
```bash
# Try different port
streamlit run visualize.py --server.port 8502

# Or check firewall
netstat -an | grep 8501
```

---

## 📊 Example Output

After running `python -m market_predictor.cli run-pipeline`:

```
Processed 144 districts.

=== Top 5 by market potential score ===
district_id    mean_night_light  population_density  market_potential_score
D_0_3          65.42             7,250               0.8743
D_1_2          68.15             6,890               0.8521
D_0_4          61.38             7,120               0.8412
D_2_1          58.92             6,750               0.8134
D_3_0          52.15             6,200               0.7856

=== High Potential Untapped Zones ===
district_id    market_potential_score  current_business_count  opportunity_rank
D_10_8         0.8121                  2                       1.0
D_11_7         0.7956                  3                       2.0
D_9_11         0.7842                  2                       3.0

Moran's I = 0.6234
```

---

## 🎓 Learning Path

1. **Beginner** → Run `python interactive_demo.py` (Menu 1, 2)
2. **Intermediate** → Run full pipeline, explore dashboard
3. **Advanced** → Modify code, integrate custom data
4. **Expert** → Add new scoring methods, deploy to cloud

---

## 📞 Need Help?

1. Run `python interactive_demo.py` → Menu 11 (Help)
2. Read `INTERACTIVE_GUIDE.md` (detailed improvements)
3. Check `docs/architecture.md` (system design)
4. Review test files in `tests/` (usage examples)
5. Read docstrings in source code (API reference)
