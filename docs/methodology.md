# Methodology

## Comparison to Real-World Site Selection Frameworks

| Aspect | This Project | Industry Practice |
|--------|--------------|-------------------|
| Demand proxy | VIIRS night lights + population density | POS data, mobile footfall, search trends |
| Competition | OSM POI counts / business density | Proprietary competitor databases |
| Accessibility | Road network distance (osmnx) | Drive-time isochrones, traffic models |
| Scoring | Weighted blend, MCDA, PCA, ML | Custom MCDA + econometric models |
| Spatial effects | Moran's I, spatial lag | Geo-spatial regression (SAR/GWR) |
| Validation | Synthetic underserved zones | A/B store openings, revenue backtesting |

## Market Potential Score

**Weighted (default):**
```
Score = w_light × norm(night_light) + w_pop × norm(population_density)
```
Weights are normalized to sum to 1 when `normalize_weights: true`.

**MCDA:** Multi-criteria blend of night light, population, income, road access,
competitor count (inverted), and delivery radius.

**PCA:** First principal component of standardized feature matrix.

**ML:** XGBoost regressor on synthetic store performance (swap target for real revenue).

## Opportunity Detection

A district is flagged when:
- `current_business_count` ≤ P40 (configurable)
- `market_potential_score` ≥ P70 (configurable)

Ranked by score descending (`opportunity_rank`).

## Sensitivity Analysis

Sweeps `light_weight` from 0.2 to 0.8 and records rank stability per district.
Districts with low `rank_std` are robust to weight uncertainty.

## Real Data Mode

```bash
python -m market_predictor.cli generate-data --mode real --boundary-source osm
```

Fetches:
1. **VIIRS VNL 2023** from NOAA EOG (clipped to bbox)
2. **Admin boundaries** from OSM Overpass or US Census TIGER tracts
3. **Population** from WorldPop raster (with synthetic fallback)
4. **Business density** from OSM supermarket/shop POIs

## Deployment

- **Docker:** `docker build -t market-predictor . && docker run -p 8501:8501 market-predictor`
- **Streamlit Cloud:** point to `visualize.py`, include `data/` or run generate step
- **Render:** use Dockerfile, expose port 8501
