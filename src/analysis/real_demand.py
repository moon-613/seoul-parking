"""가설 6 — 실수요(비아파트 가구) 기준 공영주차 진단 -> data/processed/dong_real_demand.csv

검증하는 것
----------
생활인구는 부설주차장을 갖춘 아파트 거주자까지 수요로 세므로 공영주차 실수요를 과대 추정한다.
**아파트를 제외한 가구로 다시 재면 취약지역 판정이 어떻게 달라지는가.**
달라지는 동이 곧 '생활인구 기준의 오탐' 이며, 확충 예산이 잘못 갈 뻔한 지점이다.

두 수요 지표
----------
  유동수요 = 생활인구        나들이 이용자가 겪는 경쟁 (주 사용자 관점)
  정주수요 = 비아파트 가구    공영주차에 의존할 수밖에 없는 가구 (부 사용자 관점)

확충 불필요 그룹을 왜 먼저 떼는가
-----------------------------
비아파트 가구가 극소인 동(잠실4동 1가구 등)은 '가구당 주차면'이 19,200까지 치솟아
순위를 지배한다. 그러나 이들은 지표 이상치가 아니라 **애초에 공영주차 실수요가 없는 동네**다.
그래서 제외가 아니라 '확충 불필요'로 따로 분류해 부 사용자에게 명시한다.

임계값 100가구의 근거
------------------
분포에 자연 단절이 있다. 정렬하면 ... 7, 7, 35, 40 | 101, 129, 149 ... 로
40과 101 사이가 61가구 벌어져 있고 그 위로는 20~30씩 촘촘하다.
**41~100 어느 값을 잡아도 같은 13개 동**이 분리되므로 임계값이 결과를 좌우하지 않는다.
아파트 비율 99% 이상(12개 동)으로 잡아도 거의 같은 집합이라 교차 검증된다.

R²에 대한 정직한 서술
------------------
실수요로 바꿔도 설명력은 오르지 않는다(생활인구 0.074 -> 비아파트 0.016).
이것 자체가 발견이다 — **서울 공영주차장 배치는 어떤 수요 지표로도 설명되지 않는다.**
따라서 비아파트 가구는 설명력 개선용이 아니라 **오탐 제거용**으로 쓴다.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from src.utils.logger import get_logger
from src.utils.plotstyle import annotate_spread, use_korean_font
from src.utils.settings import DATA_PROCESSED, ROOT_DIR, get_config

logger = get_logger(__name__)

FIG_DIR = ROOT_DIR / "reports" / "figures"
use_korean_font()

MIN_NONAPT = 100        # 확충 불필요 판정 임계 (docstring 근거 참조)
VULNERABLE = -1.0       # 표준화 잔차 임계 (config와 동일)


def load_baseline() -> pd.DataFrame:
    cfg = get_config()["panel"]["regression_baseline"]
    panel = pd.read_csv(DATA_PROCESSED / "panel.csv", dtype={"adm_cd": str, "admi_cd": str})
    d = panel[(panel.weekday == cfg["weekday"]) & (panel.timeslot == cfg["timeslot"])].copy()
    d = d.dropna(subset=["non_apt_households", "living_pop", "parking_slots"])
    logger.info(f"기준 {cfg['weekday']}요일 {cfg['timeslot']} / 행정동 {len(d)}개")
    return d


def zresidual(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    """로그-로그 회귀의 표준화 잔차와 R²."""
    lr = stats.linregress(x, y)
    r = y - (lr.intercept + lr.slope * x)
    return (r - r.mean()) / r.std(ddof=1), lr.rvalue ** 2


def diagnose(d: pd.DataFrame) -> tuple[pd.DataFrame, float, float]:
    """두 수요 기준으로 각각 잔차를 내고 판정 차이를 분류한다.

    표본을 다르게 잡는 이유
      z_유동  주차장 있는 358개 전체.  확충 불필요 동까지 넣어야
              "생활인구 기준으로는 이런 곳도 부족으로 잡힌다"를 보일 수 있다.
      z_정주  그중 실수요가 있는 동(비아파트 >= MIN_NONAPT)만.
              비아파트 1~7가구짜리를 회귀에 넣으면 실수요가 있는 동네끼리의
              비교라는 의미가 흐려진다.
    """
    d = d.copy()
    d["확충필요성"] = np.where(d.non_apt_households < MIN_NONAPT, "불필요", "검토대상")
    logger.info(f"확충 불필요 {(d.확충필요성 == '불필요').sum()}개 동 "
                f"(비아파트 {MIN_NONAPT}가구 미만)")

    flow = d[d.has_parking].copy()
    y = np.log1p(flow.parking_slots.to_numpy())
    flow["z_유동"], r2_flow = zresidual(np.log1p(flow.living_pop.to_numpy()), y)

    res = flow[flow.확충필요성 == "검토대상"].copy()
    res["z_정주"], r2_res = zresidual(
        np.log1p(res.non_apt_households.to_numpy()), np.log1p(res.parking_slots.to_numpy()))
    logger.info(f"단순회귀 R²  유동수요(생활인구, n={len(flow)}) {r2_flow:.3f} / "
                f"정주수요(비아파트, n={len(res)}) {r2_res:.3f}")

    d = d.merge(flow[["admi_cd", "z_유동"]], on="admi_cd", how="left")
    d = d.merge(res[["admi_cd", "z_정주"]], on="admi_cd", how="left")

    d["판정_유동"] = np.where(d.z_유동 <= VULNERABLE, "공급부족", "보통")
    d["판정_정주"] = np.where(d.z_정주 <= VULNERABLE, "공급부족", "보통")
    d.loc[d.z_유동.isna(), "판정_유동"] = "-"
    d.loc[d.z_정주.isna(), "판정_정주"] = "-"

    # 판정이 갈리는 이유는 둘이다. 아파트 비율로 구분해야 정책 대응이 달라진다.
    #   아파트 흡수형   부설주차장이 실수요를 흡수 -> 확충 우선순위를 내려야 함
    #   방문객 수요형   거주민보다 방문객이 압도 -> 확충은 필요하나 거주자우선이 아닌 시간제
    d["구분"] = "일치"
    both = d.판정_정주 != "-"
    d.loc[both & (d.판정_유동 == "공급부족") & (d.판정_정주 == "보통"), "구분"] = np.where(
        d.loc[both & (d.판정_유동 == "공급부족") & (d.판정_정주 == "보통"), "apt_ratio"] >= 0.5,
        "유동만 부족(아파트 흡수형)", "유동만 부족(방문객 수요형)")
    d.loc[both & (d.판정_유동 == "보통") & (d.판정_정주 == "공급부족"), "구분"] = "정주만 부족(누락)"
    d.loc[d.확충필요성 == "불필요", "구분"] = "확충 불필요"
    return d, r2_flow, r2_res


def plot(d: pd.DataFrame, r2_flow: float, r2_res: float) -> None:
    m = d[d.z_정주.notna()]
    colors = {"일치": "#C7C7C7",
              "유동만 부족(아파트 흡수형)": "#D62728",
              "유동만 부족(방문객 수요형)": "#F58518",
              "정주만 부족(누락)": "#2CA02C"}

    fig, axes = plt.subplots(1, 3, figsize=(19, 6.2))

    # ① 두 기준 잔차 비교
    ax = axes[0]
    for g in ["일치", "유동만 부족(방문객 수요형)", "유동만 부족(아파트 흡수형)", "정주만 부족(누락)"]:
        sub = m[m.구분 == g]
        if sub.empty:
            continue
        ax.scatter(sub.z_유동, sub.z_정주, s=24, alpha=0.8, color=colors[g], label=f"{g} ({len(sub)})")
    lim = [m[["z_유동", "z_정주"]].min().min() - 0.3, m[["z_유동", "z_정주"]].max().max() + 0.3]
    ax.plot(lim, lim, "k--", lw=1, alpha=0.5, label="두 기준 일치선")
    ax.axhline(VULNERABLE, color="#888", ls=":", lw=1)
    ax.axvline(VULNERABLE, color="#888", ls=":", lw=1)
    annotate_spread(ax, [(r.z_유동, r.z_정주, r.admi_nm) for _, r
                         in m[m.구분.str.startswith("유동만")].nsmallest(5, "z_유동").iterrows()],
                    color="#8B1A1A")
    ax.set_xlabel(f"유동수요 기준 잔차 (생활인구, R²={r2_flow:.3f})")
    ax.set_ylabel(f"정주수요 기준 잔차 (비아파트 가구, R²={r2_res:.3f})")
    ax.set_title("두 수요 지표의 취약지역 판정 비교")
    ax.legend(fontsize=7.5, loc="upper left")
    ax.grid(alpha=0.3)

    # ② 가설 6 핵심 — 확충 불필요 동을 생활인구 기준으로 보면 부족으로 잡힌다
    ax = axes[1]
    skip = d[(d.확충필요성 == "불필요") & d.z_유동.notna()].sort_values("z_유동", ascending=False)
    yy = np.arange(len(skip))
    cols = ["#D62728" if z <= VULNERABLE else "#C7C7C7" for z in skip.z_유동]
    ax.barh(yy, skip.z_유동, color=cols)
    ax.axvline(VULNERABLE, color="#D62728", ls="--", lw=1.2, label="공급부족 기준 (-1)")
    ax.set_yticks(yy, [f"{r.sgg_nm} {r.admi_nm}\n비아파트 {r.non_apt_households:,.0f}가구"
                       for _, r in skip.iterrows()], fontsize=7.5)
    ax.set_xlabel("생활인구 기준 표준화 잔차")
    n_fp = (skip.z_유동 <= VULNERABLE).sum()
    ax.set_title(f"확충 불필요 동인데 생활인구로는 부족 판정 — {n_fp}개")
    ax.legend(fontsize=8)
    ax.grid(axis="x", alpha=0.3)

    # ③ 확충 우선순위 (정주수요 기준 하위)
    ax = axes[2]
    top = m[m.판정_정주 == "공급부족"].nsmallest(12, "z_정주").iloc[::-1]
    yy = np.arange(len(top))
    ax.barh(yy, top.non_apt_households, color="#4C78A8")
    ax.set_yticks(yy, [f"{r.sgg_nm} {r.admi_nm}\n주차 {r.parking_slots:,.0f}면"
                       for _, r in top.iterrows()], fontsize=7.5)
    ax.set_xlabel("비아파트 가구 수 (공영주차 실수요)")
    ax.set_title("확충 우선순위 — 실수요 대비 공급 부족")
    ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "real_demand.png", dpi=150)
    plt.close(fig)
    logger.info("저장: real_demand.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    d, r2_flow, r2_res = diagnose(load_baseline())

    cols = ["adm_cd", "admi_cd", "sgg_nm", "admi_nm", "확충필요성", "구분",
            "판정_유동", "판정_정주", "z_유동", "z_정주",
            "living_pop", "households", "apartment", "non_apt_households", "apt_ratio",
            "parking_slots", "slots_per_100_nonapt"]
    dest = DATA_PROCESSED / "dong_real_demand.csv"
    d[cols].sort_values(["구분", "z_정주"]).to_csv(dest, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {dest} ({len(d)}행)")

    plot(d, r2_flow, r2_res)

    show = ["sgg_nm", "admi_nm", "non_apt_households", "apt_ratio", "parking_slots", "z_유동", "z_정주"]

    skip = d[(d.확충필요성 == "불필요") & d.z_유동.notna()]
    fp_skip = skip[skip.z_유동 <= VULNERABLE]
    print(f"\n=== 가설 6 판정 ===")
    print(f"  확충 불필요 {len(skip)}개 동(주차장 보유분)을 생활인구 기준으로 보면 "
          f"{len(fp_skip)}개가 '공급부족'으로 잡힘 -> {'지지' if len(fp_skip) else '기각'}")
    print(f"  비아파트 가구가 2~35호뿐인 동네가 확충 대상으로 지목되던 셈")
    print(fp_skip.sort_values("z_유동")[
        ["sgg_nm", "admi_nm", "households", "apartment", "non_apt_households",
         "parking_slots", "z_유동"]].to_string(index=False, float_format="%.2f"))

    for label in ["유동만 부족(아파트 흡수형)", "유동만 부족(방문객 수요형)", "정주만 부족(누락)"]:
        sub = d[d.구분 == label]
        if sub.empty:
            continue
        key = "z_유동" if label.startswith("유동") else "z_정주"
        print(f"\n=== {label} ({len(sub)}개) ===")
        if label.endswith("아파트 흡수형)"):
            print("    부설주차장이 실수요를 흡수 -> 확충 우선순위를 내려야 함")
        elif label.endswith("방문객 수요형)"):
            print("    거주민보다 방문객이 압도 -> 확충은 필요하나 거주자우선이 아닌 시간제로")
        else:
            print("    생활인구로는 놓쳤으나 거주 실수요 기준으로는 부족 -> 확충 후보 추가")
        print(sub.nsmallest(8, key)[show].to_string(index=False, float_format="%.3f"))

    print(f"\n=== 확충 불필요 {(d.확충필요성 == '불필요').sum()}개 동 "
          f"(비아파트 {MIN_NONAPT}가구 미만) ===")
    print("    공영주차에 의존할 가구가 사실상 없음 — 확충 대상에서 제외할 것")
    print(d[d.확충필요성 == "불필요"].nsmallest(13, "non_apt_households")[
        ["sgg_nm", "admi_nm", "households", "apartment", "non_apt_households", "parking_slots"]
    ].to_string(index=False, float_format="%.0f"))

    prio = d[d.판정_정주 == "공급부족"].nsmallest(15, "z_정주")
    print(f"\n=== 확충 우선순위 TOP 15 (실수요 기준) ===")
    print(prio[show].to_string(index=False, float_format="%.3f"))


if __name__ == "__main__":
    main()
