"""전국주차장정보 표준데이터 수집(서울 필터) -> data/raw/parking_standard.csv

민영주차장을 포함하는 유일한 경로. 서울 공영주차장 API(GetParkInfo)는 공영만 제공하므로
공급 과소추정을 줄이려면 이 데이터가 필요하다.

주의 (2026-08-10 확인):
- 포털 파일 다운로드는 /download/columList.json 에서 HTTP 500 반환 (서버 장애)
- 오픈 API도 60초 후 HTTP 504 Gateway Timeout 반환 (서버 장애)
두 경로 모두 서버측 문제이므로, 복구 여부를 --probe 로 먼저 확인한 뒤 수집할 것.

인증키: .env 의 DATA_GO_KR_KEY 는 Encoding 키(% 포함)이므로 재인코딩하면 403이 난다.
config 의 key_is_url_encoded 설정에 따라 그대로 붙인다.
"""
import argparse
import time

import pandas as pd
import requests

from src.utils.logger import get_logger
from src.utils.settings import DATA_RAW, get_config, get_env

logger = get_logger(__name__)


def _build_url(page: int, rows: int) -> str:
    cfg = get_config()["data_go_kr"]
    key = get_env("DATA_GO_KR_KEY")
    if not cfg.get("key_is_url_encoded"):
        key = requests.utils.quote(key, safe="")
    return f"{cfg['parking_api']}?serviceKey={key}&pageNo={page}&numOfRows={rows}&type=json"


def _request(page: int, rows: int, timeout: int) -> dict:
    resp = requests.get(_build_url(page, rows), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def probe(timeout: int = 90) -> bool:
    """API가 살아있는지 1건만 요청해 확인."""
    try:
        payload = _request(1, 1, timeout)
    except requests.HTTPError as e:
        logger.error(f"HTTP 오류: {e.response.status_code} — 서버 장애 가능성 (504=게이트웨이 타임아웃)")
        return False
    except requests.RequestException as e:
        logger.error(f"요청 실패: {e}")
        return False

    header = payload.get("response", {}).get("header", {})
    total = payload.get("response", {}).get("body", {}).get("totalCount")
    logger.info(f"정상 응답 — resultCode={header.get('resultCode')}, totalCount={total}")
    return True


def fetch_all(timeout: int = 90, sleep_sec: float = 0.3) -> pd.DataFrame:
    cfg = get_config()["data_go_kr"]
    rows_per_page = cfg["page_size"]

    first = _request(1, rows_per_page, timeout)
    body = first["response"]["body"]
    total = int(body["totalCount"])
    total_pages = (total + rows_per_page - 1) // rows_per_page
    logger.info(f"전체 {total:,}건 / {total_pages}페이지 수집 시작")

    records = list(body.get("items", []))
    for page in range(2, total_pages + 1):
        payload = _request(page, rows_per_page, timeout)
        records.extend(payload["response"]["body"].get("items", []))
        logger.info(f"{page}/{total_pages} 페이지 (누적 {len(records):,}건)")
        time.sleep(sleep_sec)

    return pd.DataFrame(records)


def filter_seoul(df: pd.DataFrame) -> pd.DataFrame:
    """소재지 주소 기준 서울만 남긴다."""
    sido = get_config()["data_go_kr"]["sido_filter"]
    addr_cols = [c for c in ("rdnmadr", "lnmadr") if c in df.columns]
    if not addr_cols:
        logger.warning(f"주소 컬럼을 찾지 못해 필터를 건너뜁니다. 컬럼: {list(df.columns)[:15]}")
        return df

    mask = False
    for col in addr_cols:
        mask = mask | df[col].astype(str).str.startswith(sido)
    return df[mask]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="API 생존 여부만 확인")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    if args.probe:
        ok = probe(args.timeout)
        logger.info("사용 가능" if ok else "사용 불가 — 나중에 다시 시도하세요")
        return

    df = filter_seoul(fetch_all(args.timeout))
    out_path = DATA_RAW / "parking_standard.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {out_path} (서울 {len(df):,}건)")


if __name__ == "__main__":
    main()
