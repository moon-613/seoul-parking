"""서울시 우리마을 생활인구 (행정동) 수집 -> data/raw/living_population_{YYYYMMDD}.csv

서비스: SPOP_LOCAL_RESD_DONG (일별, 행정동 단위 내국인 생활인구)
"""
import argparse
from datetime import datetime

import pandas as pd

from src.utils.api_client import SeoulOpenApiClient
from src.utils.logger import get_logger
from src.utils.settings import DATA_RAW, get_config

logger = get_logger(__name__)


def fetch(target_date: str) -> pd.DataFrame:
    """target_date: 'YYYYMMDD'"""
    cfg = get_config()["seoul_openapi"]["services"]
    client = SeoulOpenApiClient()
    rows = client.fetch_all(cfg["living_population_dong"], extra_path=[target_date])
    df = pd.DataFrame(rows)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.today().strftime("%Y%m%d"), help="YYYYMMDD")
    args = parser.parse_args()

    df = fetch(args.date)
    out_path = DATA_RAW / f"living_population_{args.date}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {out_path} ({len(df)}행)")


if __name__ == "__main__":
    main()
