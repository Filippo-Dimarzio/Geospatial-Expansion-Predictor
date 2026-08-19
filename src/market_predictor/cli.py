"""Command-line interface for data generation and pipeline execution."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from market_predictor.config import AppConfig
from market_predictor.data import generate_mock_data, generate_real_data
from market_predictor.logging_config import setup_logging
from market_predictor.pipeline.runner import run_pipeline, run_sensitivity


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Geospatial Market Potential Predictor CLI",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--log-level", default=None, help="Logging level (DEBUG, INFO, ...)")
    sub = parser.add_subparsers(dest="command", required=True)

    # generate-data
    gen = sub.add_parser("generate-data", help="Generate mock or real geospatial data")
    gen.add_argument("--mode", choices=["mock", "real"], default=None)
    gen.add_argument("--region", choices=["europe", "united_states"], default=None)
    gen.add_argument("--raster-path", default=None)
    gen.add_argument("--districts-path", default=None)
    gen.add_argument("--boundary-source", choices=["osm", "census_tract"], default=None)

    # run-pipeline
    run = sub.add_parser("run-pipeline", help="Execute the full scoring pipeline")
    run.add_argument("--districts-path", default=None)
    run.add_argument("--raster-path", default=None)
    run.add_argument("--light-weight", type=float, default=None)
    run.add_argument("--population-weight", type=float, default=None)
    run.add_argument("--skip-zonal", action="store_true", help="Load precomputed results")
    run.add_argument("--output", default=None, help="Override GeoJSON output path")

    # sensitivity
    sens = sub.add_parser("sensitivity", help="Run weight sensitivity analysis")
    sens.add_argument("--output-csv", default="data/sensitivity_results.csv")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cfg = AppConfig.load(args.config)
    level = args.log_level or cfg.get("logging", "level", default="INFO")
    logger = setup_logging(level)

    if args.command == "generate-data":
        mode = args.mode or cfg.get("data", "mode", default="mock")
        region = (args.region or cfg.region).lower()
        raster = args.raster_path or cfg.raster_path
        districts = args.districts_path or cfg.districts_path
        bbox = cfg.region_bbox(region)
        if mode == "real":
            boundary = args.boundary_source or cfg.get("data", "boundary_source", default="osm")
            generate_real_data(
                bbox=bbox,
                output_dir=Path(raster).parent,
                boundary_source=boundary,
                census_state_fips=str(cfg.get("data", "census_state_fips", default="06")),
                census_county_fips=str(cfg.get("data", "census_county_fips", default="001")),
            )
        else:
            generate_mock_data(raster_path=raster, districts_path=districts, bbox=bbox, region=region)
        logger.info("Data generation complete for %s.", region)
        return 0

    if args.command == "run-pipeline":
        result = run_pipeline(
            districts_path=args.districts_path,
            raster_path=args.raster_path,
            config=cfg,
            light_weight=args.light_weight,
            population_weight=args.population_weight,
            skip_zonal=args.skip_zonal,
        )
        print(f"Processed {len(result)} districts.")
        top5 = result.sort_values("market_potential_score", ascending=False).head(5)
        print("\n=== Top 5 by market potential score ===")
        print(
            top5[
                ["district_id", "mean_night_light", "population_density", "market_potential_score"]
            ].to_string(index=False)
        )
        untapped = result[result["is_high_potential_untapped"]].sort_values("opportunity_rank")
        print("\n=== High Potential Untapped Zones ===")
        if untapped.empty:
            print("(none)")
        else:
            print(
                untapped[
                    ["district_id", "market_potential_score", "current_business_count", "opportunity_rank"]
                ].to_string(index=False)
            )
        morans = result.attrs.get("morans_i")
        if morans is not None:
            print(f"\nMoran's I = {morans:.4f}")
        return 0

    if args.command == "sensitivity":
        sens_df, summary = run_sensitivity(cfg)
        out = Path(args.output_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        sens_df.to_csv(out, index=False)
        summary_path = out.with_name("sensitivity_summary.csv")
        summary.to_csv(summary_path, index=False)
        logger.info("Sensitivity results -> %s, %s", out, summary_path)
        print(summary.head(10).to_string(index=False))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
