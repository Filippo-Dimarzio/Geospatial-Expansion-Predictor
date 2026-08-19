#  Geospatial Expansion Predictor

> **An enterprise-grade location intelligence platform for quick-commerce & retail site selection using satellite imagery, spatial analytics, and machine learning.**


## Executive Overview

Finding the best locations for new fulfillment hubs and delivery centers usually takes months of costly manual research. This project automates that process by combining satellite images of city night lights, population maps, and local business data to instantly highlight prime, underserved areas ready for business.

It features an end-to-end data processing pipeline, dynamic Multi-Criteria Decision Analysis (MCDA), spatial autocorrelation modeling, XGBoost scoring, and an interactive Streamlit decision dashboard.

### Validated Business Logic
To test accuracy, I hid existing business data for 3 busy, high-activity neighborhoods. The pipeline successfully flagged all 3 hidden areas as top expansion targets—proving it reliably spots prime, untapped business opportunities.


## System Architecture

The project follows clean architecture principles, separating data ingestion, processing, modeling, and visualization into modular layers:

## 🔥 Key Technical Highlights

* **Multi-Modal Geospatial Pipeline:** Supports both local mock generation and real-world data extraction from NOAA VIIRS raster layers, WorldPop grids, and OSM administrative boundaries.
* **Accelerated Zonal Statistics:** Vectorized spatial operations using `rasterstats` / `exactextract` with multiprocessing and batching for high performance over large polygon sets.
* **Flexible Scoring Engine:** Evaluates target zones using multiple methodologies:
  * Weighted Sum Modeling
  * Multi-Criteria Decision Analysis (MCDA)
  * Principal Component Analysis (PCA)
  * XGBoost Supervised Machine Learning
* **Spatial Econometrics:** Computes spatial lag and Moran’s I to measure spatial clustering and neighborhood spillover effects.
* **Sensitivity & Stability Analysis:** Automated parameter sensitivity testing with rank stability scoring across varying weight configurations.
* **Interactive Executive Dashboard:** Built with Streamlit and Folium/Plotly to render interactive raster overlays, choropleth heatmaps, and customizable scenario modeling.
