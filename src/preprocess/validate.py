"""데이터 품질 검증 — 전처리 결과가 분석에 쓸 만한지 자동 점검한다.

실행: python -m src.preprocess.validate
      python -m src.preprocess.validate --strict   (경고도 실패로 처리)

검사 항목
--------
  구조   행/열 수, 패널 키 조합의 완전성
  중복   키 중복, 완전 중복
  논리   음수·범위 위반·파생변수 재계산 일치
  결측   컬럼별 결측률과 사유 대조
  이상치 IQR 3배 밖 비율 (제거하지 않고 보고만 한다)

이상치를 제거하지 않는 이유
------------------------
서교동 117,158명, 여의동 97,017명 같은 값은 오류가 아니라 실제 번화가다.
이 극단값이야말로 분석의 핵심이므로 잘라내면 안 된다.
(그래서 표준화도 Min-Max가 아닌 Z-score를 쓴다)
"""
from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np
import pandas as pd

from src.utils.logger import get_logger
from src.utils.settings import DATA_EXTERNAL, DATA_INTERIM, DATA_PROCESSED, DATA_RAW
from src.utils.timeslot import get_weekday_names, timeslot_order

logger = get_logger(__name__)

# 사유가 확인된 허용 결측률 (이 이상이면 경고)
ALLOWED_MISSING = {
    "avg_fee_per_hour": 0.30,   # 공영주차장 없는 동 + 요금 미기재
    "worker_pop": 0.05,         # 상권 직장인구가 414개 동만 제공
    "store_food": 0.01,
    "store_cafe": 0.01,
    "facility_cnt": 0.01,
    "resident_pop": 0.01,
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def check(self, ok: bool, name: str, detail: str = "", warn_only: bool = False) -> None:
        if ok:
            logger.info(f"  [OK]   {name}")
            return
        msg = f"{name}{' — ' + detail if detail else ''}"
        if warn_only:
            self.warnings.append(msg)
            logger.warning(f"  [경고] {msg}")
        else:
            self.errors.append(msg)
            logger.error(f"  [실패] {msg}")

    def note(self, name: str, detail: str) -> None:
        logger.info(f"  [정보] {name}: {detail}")


def validate_raw(rep: Report) -> None:
    logger.info("── 원본 데이터 ──")

    lp_files = sorted(glob.glob(str(DATA_RAW / "living_population" / "*.csv")))
    rep.check(len(lp_files) > 0, "생활인구 파일 존재", f"{len(lp_files)}개")
    if lp_files:
        sample = pd.read_csv(lp_files[0], dtype={"ADSTRD_CODE_SE": str}, nrows=100)
        need = {"STDR_DE_ID", "TMZON_PD_SE", "ADSTRD_CODE_SE", "TOT_LVPOP_CO"}
        rep.check(need <= set(sample.columns), "생활인구 필수 컬럼",
                  f"누락 {need - set(sample.columns)}")
        # 요일 균등성
        dates = [pd.to_datetime(os.path.basename(f)[:8], format="%Y%m%d") for f in lp_files]
        cnt = pd.Series([d.weekday() for d in dates]).value_counts()
        rep.check(cnt.nunique() == 1, "요일별 표본 균등",
                  f"요일별 {cnt.to_dict()}", warn_only=True)
        rep.note("생활인구 기간", f"{min(dates).date()} ~ {max(dates).date()} ({len(dates)}일)")

    pk = DATA_RAW / "parking_standard.csv"
    rep.check(pk.exists(), "주차장 표준데이터 존재")
    if pk.exists():
        df = pd.read_csv(pk)
        need = {"prkplceNm", "prkcmprt", "prkplceSe", "lnmadr"}
        rep.check(need <= set(df.columns), "주차장 필수 컬럼", f"누락 {need - set(df.columns)}")

    bnd_path = DATA_EXTERNAL / "dong_boundary.geojson"
    rep.check(bnd_path.exists(), "행정동 경계 존재")
    if bnd_path.exists():
        with open(bnd_path, encoding="utf-8") as fp:
            bnd = json.load(fp)
        xs, ys = [], []
        for ft in bnd["features"]:
            c = ft["geometry"]["coordinates"]
            while isinstance(c[0], list):
                c = c[0]
            xs.append(c[0])
            ys.append(c[1])
        # SGIS는 CRS84라고 선언하면서 UTM-K 미터 좌표를 주는 경우가 있다.
        # 미터 좌표면 지도에 아무것도 안 그려지므로 값으로 직접 확인한다.
        in_seoul = 126.5 <= min(xs) and max(xs) <= 127.3 and 37.3 <= min(ys) and max(ys) <= 37.8
        rep.check(in_seoul, "경계 좌표가 서울 경위도 범위",
                  f"경도 {min(xs):.3f}~{max(xs):.3f} / 위도 {min(ys):.3f}~{max(ys):.3f} "
                  "— 미터 좌표면 EPSG:5179→4326 재투영 필요")

    rep.check((DATA_EXTERNAL / "dong_crosswalk.csv").exists(), "행정동 크로스워크 존재")


def validate_geocode(rep: Report) -> None:
    logger.info("── 지오코딩 ──")
    path = DATA_INTERIM / "parking_geocoded_standard.csv"
    if not path.exists():
        rep.check(False, "지오코딩 결과 존재")
        return

    df = pd.read_csv(path, dtype={"geo_adm_cd": str})
    df["prkcmprt"] = pd.to_numeric(df["prkcmprt"], errors="coerce")
    assigned = df["geo_adm_cd"].notna()
    rate = df.loc[assigned, "prkcmprt"].sum() / df["prkcmprt"].sum()
    rep.check(rate >= 0.99, "주차면 배정률 99% 이상", f"{rate*100:.1f}%")

    with open(DATA_EXTERNAL / "dong_boundary.geojson", encoding="utf-8") as fp:
        boundary = json.load(fp)
    codes = {ft["properties"]["adm_cd"] for ft in boundary["features"]}
    unmatched = set(df.loc[assigned, "geo_adm_cd"]) - codes
    rep.check(not unmatched, "배정 코드가 모두 경계에 존재", f"미매칭 {len(unmatched)}개")


def validate_panel(rep: Report) -> pd.DataFrame:
    logger.info("── 패널 테이블 ──")
    path = DATA_PROCESSED / "panel.csv"
    if not path.exists():
        rep.check(False, "패널 존재")
        return pd.DataFrame()

    p = pd.read_csv(path, dtype={"adm_cd": str, "admi_cd": str})
    rep.note("규모", f"{len(p):,}행 × {p.shape[1]}열")

    # 구조
    key = ["admi_cd", "weekday", "timeslot"]
    # 요일·시간대 개수는 config에서 읽는다 (구간 설계를 바꿔도 검증이 따라오도록)
    n_wd, n_ts = len(get_weekday_names()), len(timeslot_order())
    expected = p["admi_cd"].nunique() * n_wd * n_ts
    rep.check(len(p) == expected, "패널 키 조합 완전성",
              f"{len(p):,} vs 기대 {expected:,} (동 {p['admi_cd'].nunique()} × 요일 {n_wd} × 시간대 {n_ts})")
    rep.check(p.duplicated(key).sum() == 0, "키 중복 없음", f"{p.duplicated(key).sum()}건")
    rep.check(p.duplicated().sum() == 0, "완전 중복 없음", f"{p.duplicated().sum()}건")

    # 논리
    logic = {
        "생활인구 양수": (p["living_pop"] <= 0).sum(),
        "20~30대 <= 총생활인구": (p["young_pop"] > p["living_pop"]).sum(),
        "비중 0~1 범위": ((p["young_ratio"] < 0) | (p["young_ratio"] > 1)).sum(),
        "주차면 음수 없음": (p["parking_slots"] < 0).sum(),
        "요금 음수 없음": (p["avg_fee_per_hour"] < 0).sum(),
        "has_parking 일관성": ((p["parking_slots"] > 0) != p["has_parking"]).sum(),
        "slots_per_1k 재계산 일치": (
            ~np.isclose(p["slots_per_1k"], p["parking_slots"] / p["living_pop"] * 1000)
        ).sum(),
    }
    for name, bad in logic.items():
        rep.check(bad == 0, name, f"{bad}건 위반")

    # 결측
    for col, limit in ALLOWED_MISSING.items():
        if col not in p.columns:
            continue
        rate = p[col].isna().mean()
        rep.check(rate <= limit, f"결측률 {col}",
                  f"{rate*100:.1f}% (허용 {limit*100:.0f}%)", warn_only=True)

    # 이상치는 보고만
    logger.info("  [정보] 이상치 (IQR 3배 밖, 제거하지 않음)")
    for col in ["living_pop", "parking_slots", "slots_per_1k", "avg_fee_per_hour", "store_food"]:
        s = p[col].dropna()
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        n = ((s < q1 - 3 * iqr) | (s > q3 + 3 * iqr)).sum()
        logger.info(f"           {col:18} {n:>5}행 ({n/len(s)*100:4.1f}%) 최대 {s.max():>10,.1f}")

    return p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="경고도 실패로 처리")
    args = parser.parse_args()

    rep = Report()
    validate_raw(rep)
    validate_geocode(rep)
    validate_panel(rep)

    logger.info("── 결과 ──")
    if rep.errors:
        logger.error(f"실패 {len(rep.errors)}건")
        for e in rep.errors:
            logger.error(f"  - {e}")
    if rep.warnings:
        logger.warning(f"경고 {len(rep.warnings)}건")
        for w in rep.warnings:
            logger.warning(f"  - {w}")
    if not rep.errors and not rep.warnings:
        logger.info("모든 검사 통과")

    failed = bool(rep.errors) or (args.strict and bool(rep.warnings))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
