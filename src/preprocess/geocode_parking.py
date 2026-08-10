"""주차장 주소를 지오코딩해 행정동을 배정한다 -> data/interim/parking_geocoded.csv

왜 필요한가
----------
주차장 데이터에는 행정동 정보가 없다. 분석 단위가 행정동이므로 주차장마다
소속 행정동을 정해야(=배정) 동별 주차면수를 합산할 수 있다.

왜 지오코딩인가
--------------
좌표 공간조인은 좌표 결측 때문에 불안정하다.
  전국주차장 표준데이터(주 사용) : 856건 중 49건(5.7%) 결측
  서울시 공영주차장 API(보조)    : 2,189건 중 733건(33.5%) 결측
SGIS 지오코딩(`addr/geocodewgs84.json`)은 좌표뿐 아니라 **행정동코드(adm_cd)를 직접 반환**해
공간조인 없이 배정이 끝나고, 경계 파일의 adm_cd와 100% 일치한다.

  응답 예: adm_cd=11040540, adm_nm=마장동, x=127.035104, y=37.569968

카카오 로컬 API도 검토했으나 앱의 OPEN_MAP_AND_LOCAL 서비스가 비활성이라 403이 났다.

데이터 소스
----------
--source standard (기본) : data/raw/parking_standard.csv  (전국 표준데이터의 서울분)
--source seoul           : data/raw/parking_seoul.csv     (서울시 공영주차장 API)

표준데이터를 주로 쓰는 이유는 거주지우선주차지역이 제외되어 방문객 주차 분석에 맞기 때문이다.
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

# 소스별 컬럼 매핑: (입력파일, 주소컬럼 우선순위, 주차면수, 주차장명)
SOURCES = {
    "standard": {
        "file": "parking_standard.csv",
        "addr_cols": ["lnmadr", "rdnmadr"],
        "slots": "prkcmprt",
        "name": "prkplceNm",
    },
    "seoul": {
        "file": "parking_seoul.csv",
        "addr_cols": ["ADDR"],
        "slots": "TPKCT",
        "name": "PKLT_NM",
    },
}


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
    """주소 표기를 SGIS가 인식하는 형태로 정리.

    '영등포구 당산동3가 385-0'      -> '서울특별시 영등포구 당산동3가 385'
    '은평구 신사동산55번지5호'       -> '서울특별시 은평구 신사동 산55-5'
    '노원구 상계6·7동770-2'         -> '서울특별시 노원구 상계6.7동 770-2'
    """
    if pd.isna(addr):
        return ""
    s = str(addr).strip()

    s = re.sub(r"[·ㆍ]", ".", s)                       # 가운뎃점 통일
    s = re.sub(r"(\d+)번지\s*(\d+)호", r"\1-\2", s)     # 55번지5호 -> 55-5
    s = re.sub(r"(\d+)번지", r"\1", s)                 # 55번지 -> 55
    s = re.sub(r"(동|가|리)(산?\d)", r"\1 \2", s)       # 신사동산55 -> 신사동 산55
    s = re.sub(r"\s+", " ", s).strip()

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

    # 지번 앞에는 반드시 공백이 있어야 한다.
    # \s* 를 쓰면 '인현동2가'의 '2'를 지번으로 오인해 '인현동'으로 잘리므로 \s+ 를 쓴다.
    # '산10-84'처럼 산 지번도 있어 산? 을 허용한다.
    # 군더더기 제거: '... 181-0 0' -> '... 181-0'
    trimmed = re.sub(r"(\s산?\d+(?:-\d+)?)\s+\D.*$", r"\1", base)
    if trimmed != base:
        variants.append(trimmed)

    # 지번 제거 -> '서울특별시 용산구 용산동3가'
    dong_only = re.sub(r"\s+산?\d+(?:-\d+)?.*$", "", base).strip()
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


def _lookup(queries: list[str], token: str) -> dict | None:
    """주소 후보를 정밀 -> 개략 순으로 시도."""
    for level, query in enumerate(queries):
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


def _all_variants(row: pd.Series, addr_cols: list[str]) -> list[str]:
    """지번·도로명 등 가용한 모든 주소 컬럼의 후보를 순서대로 모은다.

    지번이 특이 형식이라 실패해도 도로명으로 살아나는 경우가 있어 둘 다 시도한다.
    """
    out: list[str] = []
    for col in addr_cols:
        val = row.get(col)
        if pd.isna(val) or not str(val).strip():
            continue
        # 여러 주소가 '+'로 이어진 경우가 있다 (예: '선릉로69길+선릉로 63길+도곡로57길')
        for part in str(val).split("+"):
            if not part.strip():
                continue
            for v in address_variants(part):
                if v not in out:
                    out.append(v)
    return out


def geocode_parking(
    df: pd.DataFrame, addr_cols: list[str], only_missing: bool = False
) -> pd.DataFrame:
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
        hit = _lookup(_all_variants(out.loc[idx], addr_cols), token)
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
    parser.add_argument("--source", choices=list(SOURCES), default="standard")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="기존 결과를 읽어 실패분만 다시 조회 (전체 재조회 없이 이어하기)",
    )
    args = parser.parse_args()

    cfg = SOURCES[args.source]
    dest = DATA_INTERIM / f"parking_geocoded_{args.source}.csv"

    if args.retry_failed and dest.exists():
        df = pd.read_csv(dest, dtype={"geo_adm_cd": str})
        logger.info(f"기존 결과 이어하기: {dest.name} ({len(df):,}건)")
        out = geocode_parking(df, cfg["addr_cols"], only_missing=True)
    else:
        src = DATA_RAW / cfg["file"]
        df = pd.read_csv(src)
        logger.info(f"입력: {src.name} ({len(df):,}건) / source={args.source}")
        out = geocode_parking(df, cfg["addr_cols"])

    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest, index=False, encoding="utf-8-sig")

    slot_col = cfg["slots"]
    slots = pd.to_numeric(out.loc[out["geo_adm_cd"].notna(), slot_col], errors="coerce").sum()
    total_slots = pd.to_numeric(out[slot_col], errors="coerce").sum()
    logger.info(
        f"저장 완료: {dest} — 행정동 확정 주차면 {slots:,.0f}/{total_slots:,.0f} "
        f"({slots/total_slots*100:.1f}%)"
    )


if __name__ == "__main__":
    main()
