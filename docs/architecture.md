# Architecture

```mermaid
flowchart LR
    subgraph Data Sources
        VIIRS[VIIRS Night Lights NOAA]
        WP[WorldPop / Census]
        OSM[OpenStreetMap POIs]
        MOCK[Synthetic Mock Generator]
    end

    subgraph Data Layer
        REAL[real.py]
        MOCKM[mock.py]
        FEAT[features.py]
    end

    subgraph Pipeline
        ZONAL[zonal.py rasterstats/exactextract]
        SCORE[scoring.py weighted/MCDA/PCA/ML]
        SPATIAL[spatial.py Moran's I / lag]
        OPP[opportunity.py]
        SENS[sensitivity.py]
        RUN[runner.py]
    end

    subgraph Outputs
        GEOJSON[pipeline_results.geojson]
        PARQUET[pipeline_results.parquet]
    end

    subgraph Dashboard
        ST[Streamlit app.py]
        FOLIUM[Folium map + raster overlay]
        PLOTLY[Plotly choropleth / gauge]
    end

    VIIRS --> REAL
    WP --> REAL
    OSM --> REAL
    MOCK --> MOCKM
    REAL --> FEAT
    MOCKM --> FEAT
    FEAT --> ZONAL
    ZONAL --> SCORE
    SCORE --> SPATIAL
    SPATIAL --> OPP
    OPP --> RUN
    RUN --> GEOJSON
    RUN --> PARQUET
    GEOJSON --> ST
    PARQUET --> ST
    ST --> FOLIUM
    ST --> PLOTLY
    OPP --> SENS
    SENS --> ST
```

## Module Layout

```
src/market_predictor/
├── config.py           # config.yaml loader
├── cli.py              # CLI entry point
├── data/
│   ├── mock.py         # synthetic VIIRS + grid districts
│   ├── real.py         # NOAA VIIRS, OSM, WorldPop, census tracts
│   └── features.py     # income, roads, competitors, delivery radius
├── pipeline/
│   ├── zonal.py        # vectorized zonal statistics
│   ├── scoring.py      # weighted, MCDA, PCA, XGBoost
│   ├── spatial.py      # Moran's I, spatial lag
│   ├── opportunity.py  # untapped zone detection
│   ├── sensitivity.py  # weight sweep analysis
│   └── runner.py       # orchestration + persistence
└── dashboard/
    └── app.py          # Streamlit UI
```
