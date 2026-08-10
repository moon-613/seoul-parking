"""서울시 주차장 안내 정보 수집 -> data/raw/parking_lots.csv

서비스: GetParkInfo (주차장코드/명, 위경도, 급지구분, 총주차면 등)
"""
import pandas as pd

from src.utils.api_client import SeoulOpenApiClient
from src.utils.logger import get_logger
from src.utils.settings import DATA_RAW, get_config

logger = get_logger(__name__)


def fetch() -> pd.DataFrame:
    cfg = get_config()["seoul_openapi"]["services"]
    client = SeoulOpenApiClient()
    rows = client.fetch_all(cfg["parking_lot_info"])
    return pd.DataFrame(rows)


def main():
    df = fetch()
    out_path = DATA_RAW / "parking_lots.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {out_path} ({len(df)}행)")


if __name__ == "__main__":
    main()
