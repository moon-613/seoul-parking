"""분석용 패널 테이블 생성 -> data/processed/panel.csv

패널 키: 행정동 × 요일(7) × 시간대(4구간)  ≈ 424 × 7 × 4

시간에 따라 변하는 값은 생활인구뿐이고, 주차·상권은 정적이다.
따라서 '1,000명당 주차면수'처럼 생활인구를 분모로 쓰는 파생변수만 시간에 따라 변한다.

조인 구조
--------
  생활인구 ADSTRD_CODE_SE ─┐
  상권 행정동_코드          ─┼─ 행안부 행정동코드(admi_cd) 기준
  주차장 geo_adm_cd ── 크로스워크 ─┘   (SGIS 체계라 변환 필요)
"""
from __future__ import annotations

import argparse
import glob
import os

import geopandas as gpd
import pandas as pd

from src.preprocess.dong_code import build_crosswalk, attach_dong_keys
from src.preprocess.load_commercial import load_all
from src.utils.logger import get_logger
from src.utils.settings import DATA_EXTERNAL, DATA_INTERIM, DATA_PROCESSED, DATA_RAW
from src.utils.timeslot import add_panel_keys

logger = get_logger(__name__)

# 20~30대 = 20~39세 (5세 단위 컬럼 8개)
YOUNG_COLS = [
    f"{g}_F{a}_LVPOP_CO"
    for g in ("MALE", "FEMALE")
    for a in ("20T24", "25T29", "30T34", "35T39")
]

# 음식점으로 묶을 업종 (커피-음료·제과점은 카페로 따로 집계)
FOOD_TYPES = [
    "한식음식점", "중식음식점", "일식음식점", "양식음식점",
    "분식전문점", "패스트푸드점", "치킨전문점", "호프-간이주점",
]
CAFE_TYPES = ["커피-음료", "제과점"]


def build_living_population() -> pd.DataFrame:
    """생활인구 56일 -> 행정동 × 요일 × 시간대 평균."""
    files = sorted(glob.glob(str(DATA_RAW / "living_population" / "*.csv")))
    if not files:
        raise FileNotFoundError("생활인구 파일이 없습니다. fetch_living_population.py를 먼저 실행하세요.")

    boundary = gpd.read_file(DATA_EXTERNAL / "dong_boundary.geojson")
    cw = build_crosswalk(boundary)

    frames = []
    for path in files:
        df = pd.read_csv(path, dtype={"ADSTRD_CODE_SE": str})
        df = add_panel_keys(df, date_col="STDR_DE_ID", hour_col="TMZON_PD_SE")
        frames.append(df)
    lp = pd.concat(frames, ignore_index=True)
    logger.info(f"생활인구 {len(files)}일 / {len(lp):,}행 (심야 제외)")

    lp = attach_dong_keys(lp, cw)
    lp["young_pop"] = lp[YOUNG_COLS].sum(axis=1)

    panel = (
        lp.groupby(["adm_cd", "admi_cd", "adm_nm", "sgg_nm", "admi_nm", "weekday", "is_weekend", "timeslot"],
                   as_index=False)
        .agg(living_pop=("TOT_LVPOP_CO", "mean"), young_pop=("young_pop", "mean"))
    )
    panel["young_ratio"] = panel["young_pop"] / panel["living_pop"]
    logger.info(f"패널 골격 {len(panel):,}행 / 행정동 {panel.admi_cd.nunique()}개")
    return panel


def build_parking() -> pd.DataFrame:
    """주차장 -> 행정동(admi_cd)별 주차면수·평균요금."""
    path = DATA_INTERIM / "parking_geocoded_standard.csv"
    if not path.exists():
        raise FileNotFoundError("주차장 지오코딩 결과가 없습니다. geocode_parking.py를 먼저 실행하세요.")

    pk = pd.read_csv(path, dtype={"geo_adm_cd": str})
    pk["prkcmprt"] = pd.to_numeric(pk["prkcmprt"], errors="coerce")

    # 시간당 요금 환산: 기본요금 / 기본시간 * 60
    # 무료 주차장은 결측이 아니라 0원이다. 기본시간이 0이면 환산 불가라 결측 처리.
    basic_charge = pd.to_numeric(pk.get("basicCharge"), errors="coerce")
    basic_time = pd.to_numeric(pk.get("basicTime"), errors="coerce")

    fee = (basic_charge / basic_time.replace(0, pd.NA) * 60).where(basic_time > 0)
    fee = fee.mask(pk.get("parkingchrgeInfo") == "무료", 0.0)
    pk["fee_per_hour"] = fee

    agg = (
        pk.groupby("geo_adm_cd", as_index=False)
        .agg(
            parking_slots=("prkcmprt", "sum"),
            parking_lots=("prkcmprt", "size"),
            avg_fee_per_hour=("fee_per_hour", "mean"),
        )
        .rename(columns={"geo_adm_cd": "adm_cd"})
    )
    logger.info(f"주차장 집계: {len(agg)}개 행정동 / {agg.parking_slots.sum():,.0f}면")
    return agg


def build_commercial(quarter: str) -> pd.DataFrame:
    """상권분석 4종 -> 행정동(admi_cd)별 변수."""
    fr = load_all()
    out: pd.DataFrame | None = None

    def pick(df: pd.DataFrame) -> pd.DataFrame:
        d = df[df["기준_년분기_코드"].astype(str) == quarter].copy()
        d["admi_cd"] = d["행정동_코드"].astype(str)
        return d

    if "store" in fr:
        st = pick(fr["store"])
        st["전체_점포_수"] = pd.to_numeric(st["전체_점포_수"], errors="coerce")
        food = st[st["서비스_업종_코드_명"].isin(FOOD_TYPES)].groupby("admi_cd")["전체_점포_수"].sum()
        cafe = st[st["서비스_업종_코드_명"].isin(CAFE_TYPES)].groupby("admi_cd")["전체_점포_수"].sum()
        out = pd.DataFrame({"store_food": food, "store_cafe": cafe}).reset_index()

    if "facility" in fr:
        fa = pick(fr["facility"])[["admi_cd", "집객시설_수"]].rename(columns={"집객시설_수": "facility_cnt"})
        out = fa if out is None else out.merge(fa, on="admi_cd", how="outer")

    if "resident" in fr:
        rs = pick(fr["resident"])[["admi_cd", "총_상주인구_수"]].rename(columns={"총_상주인구_수": "resident_pop"})
        out = rs if out is None else out.merge(rs, on="admi_cd", how="outer")

    if "worker" in fr:
        wk = pick(fr["worker"])[["admi_cd", "총_직장_인구_수"]].rename(columns={"총_직장_인구_수": "worker_pop"})
        out = wk if out is None else out.merge(wk, on="admi_cd", how="outer")

    if out is None:
        logger.warning("상권 데이터가 없어 상권 변수는 비워둡니다.")
        return pd.DataFrame(columns=["admi_cd"])

    out = out.drop_duplicates("admi_cd")
    logger.info(f"상권({quarter}) 집계: {len(out)}개 행정동")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quarter", default="20261", help="상권분석 기준 분기 (기본 20261)")
    args = parser.parse_args()

    panel = build_living_population()
    panel = panel.merge(build_parking(), on="adm_cd", how="left")
    panel = panel.merge(build_commercial(args.quarter), on="admi_cd", how="left")

    # 주차장이 없는 행정동은 0면 (결측 아님)
    panel["parking_slots"] = panel["parking_slots"].fillna(0)
    panel["parking_lots"] = panel["parking_lots"].fillna(0)

    # 시간에 따라 변하는 핵심 파생변수
    panel["slots_per_1k"] = panel["parking_slots"] / panel["living_pop"] * 1000
    panel["has_parking"] = panel["parking_slots"] > 0

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    dest = DATA_PROCESSED / "panel.csv"
    panel.to_csv(dest, index=False, encoding="utf-8-sig")

    logger.info(f"저장 완료: {dest}")
    logger.info(f"  {len(panel):,}행 / 행정동 {panel.admi_cd.nunique()}개 × 요일 {panel.weekday.nunique()} × 시간대 {panel.timeslot.nunique()}")
    logger.info(f"  주차장 있는 행정동 {panel[panel.has_parking].admi_cd.nunique()}개")
    miss = panel[["store_food", "facility_cnt", "resident_pop", "worker_pop"]].isna().sum()
    for k, v in miss.items():
        if v:
            logger.warning(f"  결측 {k}: {v:,}행 ({v/len(panel)*100:.1f}%)")


if __name__ == "__main__":
    main()
