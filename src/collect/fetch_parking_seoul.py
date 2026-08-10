"""서울시 공영주차장 정보 수집 -> data/raw/parking_seoul.csv

서비스: GetParkInfo (2,189개 / 총 61,035면 — 2026-08-10 실측)

범위 주의: 운영구분이 전부 공영(시간제/거주자우선/버스전용)으로 **민영은 포함되지 않는다**.
민영까지 필요하면 fetch_parking_standard.py(공공데이터포털)를 사용할 것.

주요 컬럼:
  PKLT_CD 주차장코드 / PKLT_NM 주차장명 / ADDR 주소
  TPKCT 총주차면수 (공급 변수)
  LAT, LOT 위경도 (행정동 공간조인용)
  PRK_CRG 주차요금 / PRK_HM 기준시간 / ADD_CRG 추가요금 / DLY_MAX_CRG 일최대요금
  PKLT_KND_NM 노상·노외 / OPER_SE_NM 운영구분 / CHGD_FREE_NM 유·무료
  * 현재주차대수(CUR_PARKING)는 폐지되어 제공되지 않음
"""
import pandas as pd

from src.utils.api_client import SeoulOpenApiClient
from src.utils.logger import get_logger
from src.utils.settings import DATA_RAW, get_config

logger = get_logger(__name__)


def fetch() -> pd.DataFrame:
    service = get_config()["seoul_openapi"]["services"]["parking_lot_public"]
    client = SeoulOpenApiClient()
    return pd.DataFrame(client.fetch_all(service))


def main():
    df = fetch()
    out_path = DATA_RAW / "parking_seoul.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    total_slots = pd.to_numeric(df.get("TPKCT"), errors="coerce").sum()
    logger.info(f"저장 완료: {out_path} ({len(df):,}건 / 총 {total_slots:,.0f}면)")


if __name__ == "__main__":
    main()
