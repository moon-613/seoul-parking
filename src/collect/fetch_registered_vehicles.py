"""자치구별 자동차 등록현황 수집 -> data/raw/registered_vehicles.csv

서비스: TbCarRegistNum (자치구 단위 - 행정동 배분은 전처리 단계에서 보정)
"""
import pandas as pd

from src.utils.api_client import SeoulOpenApiClient
from src.utils.logger import get_logger
from src.utils.settings import DATA_RAW, get_config

logger = get_logger(__name__)


def fetch() -> pd.DataFrame:
    cfg = get_config()["seoul_openapi"]["services"]
    client = SeoulOpenApiClient()
    rows = client.fetch_all(cfg["registered_vehicles"])
    return pd.DataFrame(rows)


def main():
    df = fetch()
    out_path = DATA_RAW / "registered_vehicles.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {out_path} ({len(df)}행)")


if __name__ == "__main__":
    main()
