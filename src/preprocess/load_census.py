"""인구주택총조사 거처종류별 가구(행정동) 로드 -> 비아파트 가구 산출

왜 필요한가
----------
생활인구만으로 주차 수요를 재면 **부설주차장을 갖춘 아파트 거주자까지 수요로 계산**된다.
공영주차 실수요는 부설주차장이 없는 가구(단독·연립·다세대)에서 주로 발생하므로,
아파트를 제외한 가구 수를 따로 잡아야 확충 대상지를 잘못 고르지 않는다.
(예: 송파구 오륜동은 비아파트 7가구뿐인데 생활인구 기준으로는 공급부족으로 잡힌다)

왜 합산이 아니라 차감인가
----------------------
KOSIS는 가구 수가 적은 소분류를 비공개(`X`)로 표기한다.
연립 12.1% · 다세대 7.0% · 단독 6.1%가 X라서 이들을 더하면 결측이 전파된다.
반면 `일반가구`와 `아파트`는 각각 0건·2건만 X이므로
  비아파트 가구 = 일반가구 − 아파트
로 구하면 결측이 11개 → 2개로 줄어든다. 두 방식의 차이는 최대 5가구로 무시할 수 있다.

행정동 매칭이 까다로운 이유
------------------------
원본에 자치구 컬럼이 없고 **행정동 이름만** 있다. 그래서 세 가지를 처리한다.
  ① 같은 이름이 두 곳     신사동(관악구·강남구) → 파일 순서로 구분.
                          KOSIS도 패널도 행정동코드 순이라 앞이 관악, 뒤가 강남이다.
  ② 통합된 행정동         용신동 = 용두동 + 신설동, 상일1동 외 1개 통합 = 상일1동 + 상일2동
  ③ 패널에 없는 동         항동(구로구) — 생활인구 미제공이라 버린다
결과: 427행 → 424개 행정동에 100% 매칭.
"""
from __future__ import annotations

import pandas as pd

from src.preprocess.dong_code import normalize_dong_name
from src.utils.logger import get_logger
from src.utils.settings import DATA_EXTERNAL

logger = get_logger(__name__)

CENSUS_PATH = DATA_EXTERNAL / "census" / "거처종류별가구_행정동.csv"

COLUMNS = ["census_nm", "households", "house_total", "detached", "apartment",
           "rowhouse", "multiplex", "nonresidential", "non_house"]

# 통합 행정동: 패널 이름 -> 총조사에서 합쳐야 할 이름들
MERGED_DONGS = {
    "용신동": ["용두동", "신설동"],                    # 동대문구
    "상일1동 외 1개 통합": ["상일1동", "상일2동"],      # 강동구
}

SUM_COLS = COLUMNS[1:]


def load_raw() -> pd.DataFrame:
    """헤더 2줄(연도/항목)을 건너뛰고 읽는다. 'X'(비공개)는 결측 처리."""
    if not CENSUS_PATH.exists():
        raise FileNotFoundError(
            f"총조사 파일이 없습니다: {CENSUS_PATH}\n"
            "KOSIS「거처의 종류별 가구」에서 서울 행정동(최하위레벨 선택)으로 받아 두세요."
        )
    d = pd.read_csv(CENSUS_PATH, skiprows=2, header=None, encoding="utf-8-sig")
    d.columns = COLUMNS
    for c in SUM_COLS:
        d[c] = pd.to_numeric(d[c], errors="coerce")   # 'X' -> NaN
    d = d[d.census_nm != "서울특별시"].reset_index(drop=True)
    logger.info(f"총조사 원본 {len(d)}행 로드")
    return d


def apply_merges(d: pd.DataFrame) -> pd.DataFrame:
    """통합 행정동을 합쳐 한 행으로 만든다 (첫 구성동 위치에 둔다)."""
    d = d.copy()
    for target, parts in MERGED_DONGS.items():
        idx = d.index[d.census_nm.isin(parts)]
        if len(idx) != len(parts):
            logger.warning(f"{target}: 구성동 {parts} 중 {len(idx)}개만 발견 — 건너뜀")
            continue
        merged = d.loc[idx, SUM_COLS].sum(min_count=1)
        d.loc[idx[0], SUM_COLS] = merged.values
        d.loc[idx[0], "census_nm"] = target
        d = d.drop(index=idx[1:])
        logger.info(f"통합: {' + '.join(parts)} -> {target} (일반가구 {merged.households:,.0f})")
    return d.reset_index(drop=True)


def attach_admi_cd(census: pd.DataFrame, panel_dongs: pd.DataFrame) -> pd.DataFrame:
    """행정동명으로 admi_cd를 붙인다. 동명이인은 순서로 가른다.

    panel_dongs: admi_cd, admi_nm 두 컬럼 (admi_cd 오름차순 정렬 상태여야 함)
    """
    census = census.copy()
    census["key"] = census.census_nm.map(normalize_dong_name)
    census["_ord"] = range(len(census))

    tgt = panel_dongs.copy()
    tgt["key"] = tgt.admi_nm.map(normalize_dong_name)
    tgt["_ord"] = range(len(tgt))

    # 이름별로 양쪽을 순서대로 짝지어 동명이인을 가른다
    # (KOSIS·패널 모두 행정동코드 순이므로 n번째끼리 대응된다)
    census["_rank"] = census.groupby("key")["_ord"].rank(method="first").astype(int)
    tgt["_rank"] = tgt.groupby("key")["_ord"].rank(method="first").astype(int)

    dup = [k for k, n in census.key.value_counts().items() if n > 1]
    if dup:
        logger.info(f"동명이인 {dup} — 파일 순서로 구분")

    out = tgt.merge(census.drop(columns=["_ord"]), on=["key", "_rank"], how="left")

    miss = out[out.households.isna()].admi_nm.tolist()
    extra = set(census.key) - set(tgt.key)
    if miss:
        logger.warning(f"미매칭 {len(miss)}개: {miss}")
    if extra:
        logger.info(f"총조사에만 있는 동 {len(extra)}개 (패널에 없어 제외): {sorted(extra)}")
    logger.info(f"매칭 {out.households.notna().sum()}/{len(out)}개 동")
    return out


def load_census(panel_dongs: pd.DataFrame) -> pd.DataFrame:
    """패널에 붙일 수 있는 형태로 반환: admi_cd + 가구 지표."""
    d = attach_admi_cd(apply_merges(load_raw()), panel_dongs)

    d["non_apt_households"] = d.households - d.apartment
    d["apt_ratio"] = d.apartment / d.households

    cols = ["admi_cd", "households", "apartment", "non_apt_households", "apt_ratio",
            "detached", "rowhouse", "multiplex", "non_house"]
    out = d[cols]

    zero = (out.non_apt_households == 0).sum()
    if zero:
        logger.info(f"비아파트 가구 0인 동 {zero}개 — 가구당 지표 산출 시 0 나눗셈 주의")
    logger.info(
        f"아파트 거주 비율 중앙값 {out.apt_ratio.median():.1%} "
        f"(최저 {out.apt_ratio.min():.1%} / 최고 {out.apt_ratio.max():.1%})"
    )
    return out


def main():
    from src.utils.settings import DATA_PROCESSED
    panel = pd.read_csv(DATA_PROCESSED / "panel.csv", dtype={"adm_cd": str, "admi_cd": str})
    dongs = (panel[["admi_cd", "admi_nm"]].drop_duplicates()
             .sort_values("admi_cd").reset_index(drop=True))
    out = load_census(dongs)
    print("\n=== 비아파트 가구 상위 10 (공영주차 실수요 큰 동) ===")
    m = out.merge(panel[["admi_cd", "sgg_nm", "admi_nm"]].drop_duplicates(), on="admi_cd")
    print(m.nlargest(10, "non_apt_households")[
        ["sgg_nm", "admi_nm", "households", "apartment", "non_apt_households", "apt_ratio"]
    ].to_string(index=False, float_format="%.3f"))
    print("\n=== 아파트 비율 최고 10 (실수요 낮음 — 확충 대상에서 걸러야) ===")
    print(m.nlargest(10, "apt_ratio")[
        ["sgg_nm", "admi_nm", "households", "apartment", "non_apt_households", "apt_ratio"]
    ].to_string(index=False, float_format="%.3f"))


if __name__ == "__main__":
    main()
