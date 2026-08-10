"""주차장 주소를 지오코딩해 좌표·행정동을 채운다 -> data/interim/parking_geocoded.csv

배경
----
서울 공영주차장 API(GetParkInfo)는 2,189건 중 **733건(33.5%)의 LAT/LOT가 0.0**이다.
좌표만으로 공간조인하면 61,035면 중 16,463면(27%)만 남아 공급 변수가 무너진다.

해결
----
SGIS 지오코딩 API(`addr/geocodewgs84.json`)로 주소를 변환한다.
카카오 로컬 API도 검토했으나 앱에서 OPEN_MAP_AND_LOCAL 서비스 활성화가 필요해 403이 났고,
SGIS는 좌표뿐 아니라 **행정동코드(adm_cd)를 직접 반환**해 공간조인 없이 바로 붙일 수 있다.

  응답 예: adm_cd=11040540, adm_nm=마장동, x=127.035104, y=37.569968

주소 형식
--------
원본 ADDR은 "성동구 마장동 463-2" 형태라 시도명을 붙여 조회한다.
부번이 0인 "385-0"은 "385"로 정리해야 매칭률이 오른다.
"""
from __future__ import annotations

import argparse
import re
import time

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils.logger import get_logger
from src.utils.settings import DATA_INTERIM, DATA_RAW, get_config, get_env

logger = get_logger(__name__)

SIDO = "서울특별시"
REQUEST_INTERVAL_SEC = 0.05


def get_access_token() -> str:
    base = get_config()["sgis"]["base_url"]
    resp = requests.get(
        f"{base}/auth/authentication.json",
        params={
            "consumer_key": get_env("SGIS_CONSUMER_KEY"),
            "consumer_secret": get_env("SGIS_CONSUMER_SECRET"),
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["result"]["accessToken"]


def normalize_address(addr: str) -> str:
    """'영등포구 당산동3가 385-0' -> '서울특별시 영등포구 당산동3가 385'"""
    if pd.isna(addr):
        return ""
    s = str(addr).strip()
    if s.endswith("-0"):
        s = s[:-2]
    if not s.startswith(SIDO):
        s = f"{SIDO} {s}"
    return s


def address_variants(addr: str) -> list[str]:
    """정밀 -> 개략 순으로 조회할 주소 후보들.

    지번이 폐지되었거나 '세종로 111-0 옆'처럼 군더더기가 붙어 실패하는 건이 있어,
    마지막에는 지번을 떼고 '구 + 동'만으로 조회한다. 정밀도는 떨어지지만
    행정동 단위 집계가 목적이므로 대부분 올바른 동에 떨어진다.
    """
    base = normalize_address(addr)
    if not base:
        return []

    variants = [base]

    # 군더더기 제거: 지번(숫자-숫자) 뒤 텍스트 잘라내기
    trimmed = re.sub(r"(\d+(?:-\d+)?)\s*\D.*$", r"\1", base)
    if trimmed != base:
        variants.append(trimmed)

    # 지번 제거 -> '서울특별시 종로구 와룡동'
    dong_only = re.sub(r"\s*\d+(?:-\d+)?.*$", "", base).strip()
    if dong_only and dong_only != base:
        variants.append(dong_only)

    seen, out = set(), []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _geocode_one(address: str, token: str) -> dict | None:
    base = get_config()["sgis"]["base_url"]
    resp = requests.get(
        f"{base}/addr/geocodewgs84.json",
        params={"accessToken": token, "address": address},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json().get("result") or {}
    rows = data.get("resultdata") or []
    return rows[0] if rows else None


GEO_COLS = ("geo_adm_cd", "geo_adm_nm", "geo_sgg_nm", "geo_x", "geo_y", "geo_level")


def _lookup(addr: str, token: str) -> dict | None:
    """주소 후보를 정밀 -> 개략 순으로 시도."""
    for level, query in enumerate(address_variants(addr)):
        hit = _geocode_one(query, token)
        if hit:
            return {
                "geo_adm_cd": hit.get("adm_cd"),
                "geo_adm_nm": hit.get("adm_nm"),
                "geo_sgg_nm": hit.get("sgg_nm"),
                "geo_x": float(hit["x"]) if hit.get("x") else None,
                "geo_y": float(hit["y"]) if hit.get("y") else None,
                # 0=지번 정확 / 1=군더더기 제거 / 2=동 단위 근사
                "geo_level": level,
            }
    return None


def geocode_parking(df: pd.DataFrame, only_missing: bool = False) -> pd.DataFrame:
    """주차장 DataFrame에 geo_* 컬럼을 추가.

    only_missing=True 면 geo_adm_cd 가 비어있는 행만 다시 조회한다.
    """
    token = get_access_token()
    logger.info("SGIS 토큰 발급 완료")

    out = df.reset_index(drop=True).copy()
    for col in GEO_COLS:
        if col not in out.columns:
            out[col] = None

    targets = out.index[out["geo_adm_cd"].isna()] if only_missing else out.index
    total, fail = len(targets), 0
    logger.info(f"조회 대상 {total:,}건")

    for i, idx in enumerate(targets, start=1):
        hit = _lookup(out.at[idx, "ADDR"], token)
        if hit:
            for col, val in hit.items():
                out.at[idx, col] = val
        else:
            fail += 1

        time.sleep(REQUEST_INTERVAL_SEC)
        if i % 200 == 0 or i == total:
            logger.info(f"지오코딩 {i}/{total} (실패 {fail})")

    ok = out["geo_adm_cd"].notna().sum()
    logger.info(f"지오코딩 성공 {ok:,}/{len(out):,} ({ok/len(out)*100:.1f}%)")
    if "geo_level" in out:
        lv = out["geo_level"].value_counts().sort_index()
        labels = {0: "지번 정확", 1: "군더더기 제거", 2: "동 단위 근사"}
        for k, v in lv.items():
            logger.info(f"  정밀도 {labels.get(k, k)}: {v:,}건")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="기존 결과를 읽어 실패분만 다시 조회 (전체 재조회 없이 이어하기)",
    )
    args = parser.parse_args()

    dest = DATA_INTERIM / "parking_geocoded.csv"

    if args.retry_failed and dest.exists():
        df = pd.read_csv(dest, dtype={"geo_adm_cd": str})
        logger.info(f"기존 결과 이어하기: {dest.name} ({len(df):,}건)")
        out = geocode_parking(df, only_missing=True)
    else:
        src = DATA_RAW / "parking_seoul.csv"
        df = pd.read_csv(src)
        logger.info(f"입력: {src.name} ({len(df):,}건)")
        out = geocode_parking(df)

    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest, index=False, encoding="utf-8-sig")

    slots = pd.to_numeric(out.loc[out["geo_adm_cd"].notna(), "TPKCT"], errors="coerce").sum()
    total_slots = pd.to_numeric(out["TPKCT"], errors="coerce").sum()
    logger.info(
        f"저장 완료: {dest} — 행정동 확정 주차면 {slots:,.0f}/{total_slots:,.0f} "
        f"({slots/total_slots*100:.1f}%)"
    )


if __name__ == "__main__":
    main()
