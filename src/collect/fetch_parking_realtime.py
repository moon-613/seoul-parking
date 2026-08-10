"""시영주차장 실시간 주차대수 스냅샷 수집 -> data/raw/parking_snapshots/YYYYMMDD_HHMM.csv

공영주차장 안내정보(GetParkInfo)의 CUR_PARKING 컬럼은 폐지되었으므로,
실시간 여유율은 별도 데이터셋(OA-21709, 시영주차장 실시간 주차대수)에서만 얻을 수 있다.
커버리지가 시영주차장으로 제한되므로 전체 행정동 실측은 불가능하다 (docs/data_dictionary.md 참고).

스케줄러가 하루 여러 번 호출하여 요일 x 시간대 프로파일을 누적하는 것이 목적.
"""
import argparse
from datetime import datetime

import pandas as pd

from src.utils.api_client import SeoulOpenApiClient
from src.utils.logger import get_logger
from src.utils.settings import DATA_RAW, get_config

logger = get_logger(__name__)

SNAPSHOT_DIR = DATA_RAW / "parking_snapshots"


def fetch() -> pd.DataFrame:
    service = get_config()["seoul_openapi"]["services"]["parking_realtime"]
    client = SeoulOpenApiClient()
    rows = client.fetch_all(service)
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 응답 구조만 출력")
    args = parser.parse_args()

    snapshot_at = datetime.now()
    df = fetch()
    df["snapshot_at"] = snapshot_at.strftime("%Y-%m-%d %H:%M:%S")

    if args.dry_run:
        logger.info(f"컬럼: {list(df.columns)}")
        logger.info(f"\n{df.head()}")
        return

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SNAPSHOT_DIR / f"{snapshot_at.strftime('%Y%m%d_%H%M')}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {out_path} ({len(df)}행)")


if __name__ == "__main__":
    main()
