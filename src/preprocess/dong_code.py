"""행정동코드 크로스워크 — 생활인구 ↔ SGIS 경계를 잇는다.

문제
----
생활인구와 SGIS 경계는 서로 다른 행정동코드 체계를 쓴다.
  생활인구 ADSTRD_CODE_SE : 11110515  (행정안전부 행정동코드)
  SGIS      adm_cd        : 11010530  (SGIS 자체 체계)
코드로 직접 조인하면 424개 중 32개만 맞는다.

해결
----
서울 열린데이터광장이 제공하는 '전국 행정동 코드정보'(ADMI_*.csv)가 다리 역할을 한다.
  ADMI_CD  == 생활인구 ADSTRD_CODE_SE  (같은 체계)
  FULL_NM  == SGIS adm_nm              (같은 형식: "서울특별시 종로구 사직동")

따라서 [생활인구 코드] -> ADMI_CD -> FULL_NM -> SGIS adm_nm -> [경계] 로 연결한다.

표기 차이
--------
매핑표는 가운뎃점을 '.'로, SGIS는 '·'로 쓴다. (예: '상계3.4동' vs '상계3·4동')
normalize_dong_name()이 이를 통일한다. 정규화 전 98.1% -> 정규화 후 매칭률 상승.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.utils.logger import get_logger
from src.utils.settings import DATA_EXTERNAL

logger = get_logger(__name__)

ADMI_DIR = DATA_EXTERNAL / "adm_code" / "SEOUL_ADMI"
SEOUL = "서울특별시"

# 생활인구 1개 코드가 경계 여러 개에 대응하는 분할 케이스.
# 순서 매칭(resolve_legacy_codes)으로는 1:N을 풀 수 없어 명시적으로 둔다.
#   11740520 (구 상일동) -> 상일1동 11740525 + 상일2동 11740526
# 분석 단위는 생활인구 쪽에 맞추고, 경계는 dissolve_split_dongs()로 합친다.
SPLIT_DONGS: dict[str, list[str]] = {
    "11740520": ["11740525", "11740526"],
}


def normalize_dong_name(name: str) -> str:
    """행정동명 표기 통일.

    - 가운뎃점 계열(· . ㆍ ,)을 '.'로 통일
    - 공백 제거
    """
    if pd.isna(name):
        return ""
    s = str(name).strip()
    s = re.sub(r"[·ㆍ,]", ".", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _admi_files() -> list[Path]:
    files = sorted(ADMI_DIR.glob("ADMI_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"행정동 코드정보가 없습니다: {ADMI_DIR}\n"
            "서울 열린데이터광장 생활인구 페이지의 '전국 행정동 코드정보'를 받아 압축을 푸세요."
        )
    return files


def load_admi(base_ym: str | None = None) -> pd.DataFrame:
    """행정동 코드 매핑표를 읽는다.

    base_ym을 주면 그 달만, 없으면 **모든 기준월을 합친다**.
    전체를 합치는 이유: 통폐합으로 특정 월에만 존재하는 코드가 있다.
    (예: 동대문구 용신동 11230536, 강남구 일원2동 11680740 은 최신월에 없고 과거월에만 있음)
    같은 코드가 여러 달에 있으면 최신월 표기를 남긴다.
    """
    files = [ADMI_DIR / f"ADMI_{base_ym}.csv"] if base_ym else _admi_files()
    frames = []
    for path in files:
        if not path.exists():
            raise FileNotFoundError(f"해당 기준월 파일이 없습니다: {path}")
        frames.append(pd.read_csv(path, encoding="utf-8-sig", dtype=str))

    df = pd.concat(frames, ignore_index=True)
    df = df[df["SIDO_NM"] == SEOUL].copy()
    df = df.sort_values("BASE_YM").drop_duplicates("ADMI_CD", keep="last")
    df["full_nm_norm"] = df["FULL_NM"].map(normalize_dong_name)
    logger.info(f"행정동 매핑표 {len(files)}개월 병합: 서울 고유코드 {len(df)}개")
    return df


def build_crosswalk(boundary: pd.DataFrame, base_ym: str | None = None) -> pd.DataFrame:
    """생활인구 코드 ↔ SGIS 경계코드 크로스워크 생성.

    boundary: dong_boundary.geojson을 읽은 (Geo)DataFrame — adm_cd, adm_nm 필요
    반환 컬럼: adm_cd(SGIS), adm_nm, admi_cd(생활인구), sgg_nm(자치구), admi_nm(동명)
    """
    admi = load_admi(base_ym)

    b = boundary[["adm_cd", "adm_nm"]].copy()
    b["full_nm_norm"] = b["adm_nm"].map(normalize_dong_name)

    merged = b.merge(
        admi[["ADMI_CD", "SGG_NM", "ADMI_NM", "full_nm_norm"]],
        on="full_nm_norm",
        how="left",
    ).rename(columns={"ADMI_CD": "admi_cd", "SGG_NM": "sgg_nm", "ADMI_NM": "admi_nm"})

    unmatched = merged["admi_cd"].isna().sum()
    total = len(merged)
    logger.info(f"크로스워크: {total - unmatched}/{total} 매칭 ({(total-unmatched)/total*100:.1f}%)")
    if unmatched:
        for nm in merged.loc[merged["admi_cd"].isna(), "adm_nm"]:
            logger.warning(f"  미매칭(경계): {nm}")

    return merged.drop(columns=["full_nm_norm"])


def resolve_legacy_codes(living_codes: set[str], crosswalk: pd.DataFrame) -> dict[str, str]:
    """매핑표에 없는 구버전 생활인구 코드를 자치구 내 순서로 대응시킨다.

    강북구처럼 생활인구가 구버전 코드를 쓰는 경우가 있다.
      생활인구 11305590·600·606·610·620·630
      매핑표   11305595·603·608·615·625·635  (번1~3동, 수유1~3동)

    같은 자치구(코드 앞 5자리)에서
      - 생활인구에는 있는데 매핑표에 없는 코드
      - 매핑표에는 있는데 생활인구가 쓰지 않는 코드
    양쪽 개수가 같을 때만 정렬 순서로 1:1 연결한다.
    개수가 다르면 임의 매칭을 피하기 위해 손대지 않는다.

    반환: {구버전 생활인구 코드: 매핑표 코드}
    """
    cw_codes = set(crosswalk["admi_cd"].dropna())
    orphan_living = living_codes - cw_codes      # 생활인구에만 있음
    orphan_cw = cw_codes - living_codes          # 매핑표(경계)에만 있음

    mapping: dict[str, str] = {}
    for prefix in sorted({c[:5] for c in orphan_living}):
        lp_side = sorted(c for c in orphan_living if c.startswith(prefix))
        cw_side = sorted(c for c in orphan_cw if c.startswith(prefix))

        if len(lp_side) != len(cw_side) or not cw_side:
            logger.warning(
                f"자치구 {prefix}: 생활인구 미매칭 {len(lp_side)}개 vs 경계 여유 {len(cw_side)}개 "
                "— 개수 불일치로 자동 매칭하지 않음"
            )
            continue

        for old, new in zip(lp_side, cw_side):
            mapping[old] = new
        logger.info(f"자치구 {prefix}: 구버전 코드 {len(lp_side)}개 순서 매칭")

    return mapping


def dissolve_split_dongs(boundary, crosswalk: pd.DataFrame):
    """분할된 경계 폴리곤을 생활인구 단위에 맞게 합친다.

    boundary: GeoDataFrame (adm_cd 기준)
    반환: 합쳐진 GeoDataFrame — admi_cd 컬럼이 생활인구 코드와 1:1 대응
    """
    import geopandas as gpd

    b = boundary.merge(crosswalk[["adm_cd", "admi_cd"]], on="adm_cd", how="left")

    # 분할 대상은 대표 코드로 치환한 뒤 dissolve
    reverse = {child: parent for parent, children in SPLIT_DONGS.items() for child in children}
    if reverse:
        b["admi_cd"] = b["admi_cd"].replace(reverse)

    dissolved = b.dissolve(by="admi_cd", as_index=False)
    if len(dissolved) != len(b):
        logger.info(f"분할 행정동 병합: {len(b)} -> {len(dissolved)}개")
    return gpd.GeoDataFrame(dissolved, geometry="geometry", crs=boundary.crs)


def attach_dong_keys(
    living_pop: pd.DataFrame, crosswalk: pd.DataFrame, code_col: str = "ADSTRD_CODE_SE"
) -> pd.DataFrame:
    """생활인구 데이터에 경계코드·자치구·동명을 붙인다.

    구버전 코드는 resolve_legacy_codes()로 보정한 뒤 조인한다.
    """
    lp = living_pop.copy()
    lp[code_col] = lp[code_col].astype(str)

    # 분할 케이스는 순서 매칭 대상에서 제외해야 오탐이 없다
    known_split = set(SPLIT_DONGS)
    legacy = resolve_legacy_codes(set(lp[code_col]) - known_split, crosswalk)
    if legacy:
        lp[code_col] = lp[code_col].replace(legacy)

    # 분할 케이스는 대표 자식 코드로 조인해 자치구·동명을 가져온다
    cw = crosswalk[["admi_cd", "adm_cd", "adm_nm", "sgg_nm", "admi_nm"]].copy()
    for parent, children in SPLIT_DONGS.items():
        rep = cw[cw["admi_cd"] == children[0]]
        if not rep.empty:
            row = rep.iloc[0].copy()
            row["admi_cd"] = parent
            row["admi_nm"] = f"{row['admi_nm']} 외 {len(children) - 1}개 통합"
            cw = pd.concat([cw, row.to_frame().T], ignore_index=True)

    out = lp.merge(cw, left_on=code_col, right_on="admi_cd", how="left")

    missing = out["adm_cd"].isna().sum()
    if missing:
        codes = sorted(out.loc[out["adm_cd"].isna(), code_col].unique())
        logger.warning(f"경계 미매칭 생활인구 행 {missing:,}건 / 코드 {len(codes)}개: {codes[:10]}")
    return out


def main():
    import geopandas as gpd

    boundary = gpd.read_file(DATA_EXTERNAL / "dong_boundary.geojson")
    cw = build_crosswalk(boundary)

    out_path = DATA_EXTERNAL / "dong_crosswalk.csv"
    cw.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {out_path} ({len(cw)}행)")


if __name__ == "__main__":
    main()
