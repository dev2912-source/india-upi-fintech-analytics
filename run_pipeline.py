"""Single-command CLI runner for the full India UPI FinTech pipeline."""

import argparse
import logging

from src.anomaly_detection import run_anomaly_detection
from src.clustering import run_clustering
from src.etl import run_etl
from src.forecasting import run_forecasting
from src.generate_charts import generate_all_charts

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PhonePe Pulse FinTech analytics pipeline.")
    parser.add_argument("--skip-charts", action="store_true", help="Skip PNG chart generation.")
    args = parser.parse_args()

    logger.info("Step 1/5: Running ETL...")
    run_etl()

    logger.info("Step 2/5: Running District Clustering...")
    run_clustering()

    logger.info("Step 3/5: Running State Anomaly Detection...")
    run_anomaly_detection()

    logger.info("Step 4/5: Running Multi-Model Forecasting Bake-Off...")
    run_forecasting()

    if not args.skip_charts:
        logger.info("Step 5/5: Generating README Charts...")
        generate_all_charts()

    logger.info("Pipeline completed successfully.")


if __name__ == "__main__":
    main()
