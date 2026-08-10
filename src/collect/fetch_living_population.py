"""서울시 생활인구(행정동 x 시간대) 수집 -> data/raw/living_population/YYYYMMDD.csv

서비스: SPOP_LOCAL_RESD_DONG (일별 / 행정동 / 1시간 단위)

요일 x 시간대 패널을 만들려면 여러 날짜가 필요하다. 기본 28일(4주)로 두어
7개 요일마다 4개 표본을 확보한다.

주의: OpenAPI는 최근 2개월분만 제공하고 집계 지연도 있다.
따라서 --end-date 기본값을 과거로 두며, 그보다 오래된 기간이 필요하면
데이터셋 페이지의 월별 ZIP(LOCAL_PEOPLE_DONG_YYYYMM.zip)을 받아
data/raw/living_population/ 에 풀어 넣는 방식을 쓴다.
"""
import argparse
from datetime import datetime, timedelta

import pandas as pd

from src.utils.api_client import SeoulOpenApiClient
from src.utils.logger import get_logger
from src.utils.settings import DATA_RAW, get_config

logger = get_logger(__name__)

OUT_DIR = DATA_RAW / "living_population"

# 2026-08-10 실측한 제공 구간:
#   7일전  -> 0건 (집계 지연)
#   14~70일전 -> 정상 (10,176행/일)
#   80일전 이상 -> 0건 (제공 범위 밖)
# 즉 가용 폭은 약 57일. 기본값은 이 구간 안에 들어오도록 잡는다.
LAG_DAYS = 14          # 집계 지연 여유 (이보다 최근은 빈 응답)
API_WINDOW_DAYS = 70   # 이보다 과거는 OpenAPI 미제공 -> 월별 ZIP 사용


def fetch_one_day(target_date: str) -> pd.DataFrame:
    service = get_config()["seoul_openapi"]["services"]["living_population_dong"]
    client = SeoulOpenApiClient()
    rows = client.fetch_all(service, extra_path=[target_date])
    return pd.DataFrame(rows)


def date_range(end_date: str, days: int) -> list[str]:
    end = datetime.strptime(end_date, "%Y%m%d")
    return [(end - timedelta(days=i)).strftime("%Y%m%d") for i in range(days)]


def main():
    default_end = (datetime.today() - timedelta(days=LAG_DAYS)).strftime("%Y%m%d")
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", default=default_end, help="수집 종료일 YYYYMMDD (이 날짜부터 과거로)")
    parser.add_argument("--days", type=int, default=28, help="수집 일수 (기본 28 = 4주)")
    parser.add_argument("--overwrite", action="store_true", help="이미 받은 날짜도 다시 수집")
    args = parser.parse_args()

    dates = date_range(args.end_date, args.days)
    oldest = datetime.strptime(dates[-1], "%Y%m%d")
    if (datetime.today() - oldest).days > API_WINDOW_DAYS:
        logger.warning(
            f"요청 구간의 시작일({dates[-1]})이 OpenAPI 제공 범위(최근 {API_WINDOW_DAYS}일)를 벗어납니다. "
            "빈 응답이 나오면 월별 ZIP 파일 다운로드를 사용하세요."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"수집 대상: {dates[-1]} ~ {dates[0]} ({len(dates)}일)")

    saved = skipped = empty = 0
    for target_date in dates:
        out_path = OUT_DIR / f"{target_date}.csv"
        if out_path.exists() and not args.overwrite:
            skipped += 1
            continue

        df = fetch_one_day(target_date)
        if df.empty:
            logger.warning(f"{target_date}: 데이터 없음 (집계 지연 또는 제공 범위 밖)")
            empty += 1
            continue

        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        logger.info(f"저장: {out_path.name} ({len(df):,}행)")
        saved += 1

    logger.info(f"완료 — 저장 {saved}일 / 건너뜀 {skipped}일 / 빈응답 {empty}일")


if __name__ == "__main__":
    main()
