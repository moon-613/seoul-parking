"""나들이 적합도 지수 (PCA 기반) -> data/processed/dong_suitability.csv

기획서가 약속한 것
---------------
"임의 가중치가 아닌 데이터 기반의 '나들이 적합도 지수'를 구성"
"주성분은 분산 최대 방향일 뿐 그 자체가 적합도를 뜻하지 않으므로
 로딩을 확인해 해석하고 지수의 부호 방향을 명시적으로 고정함"

로딩을 확인한 결과
---------------
두 축이 거의 완벽하게 분리됐다. 우리가 나눈 게 아니라 데이터가 그렇게 나뉜다.
  PC1 (52.1%)  음식점 .582 · 카페 .584 · 집객시설 .548 | 주차 -.13, -.04  -> 매력도 축
  PC2 (39.2%)  천명당주차면 .694 · 주차여유 .708       | 매력도 ~.1       -> 주차 여유 축
따라서 PC1을 매력도 지수, PC2를 주차 여유 지수로 쓴다.

부호 고정
--------
PCA의 주성분 부호는 실행마다 뒤집힐 수 있다(고유벡터는 ±가 모두 해).
보고서 숫자가 실행할 때마다 뒤집히면 안 되므로 **기준 변수의 로딩이 양수가 되도록** 고정한다.
  PC1 -> 음식점 로딩이 양수
  PC2 -> 천명당주차면 로딩이 양수

두 지수를 왜 기하평균으로 합치는가
----------------------------
산술평균은 '놀거리 100 + 주차 0'과 '50 + 50'을 같게 본다.
그러나 나들이는 **약한 쪽이 병목**이다. 주차가 없으면 놀거리가 아무리 많아도 못 가고,
주차만 널널하고 볼 게 없으면 갈 이유가 없다.
기하평균은 한쪽이 낮으면 전체가 낮아져 이 병목 구조를 반영한다.
(두 축이 PCA로 직교화되어 서로 독립이므로 곱해도 중복 계산이 아니다)
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from src.utils.logger import get_logger
from src.utils.plotstyle import annotate_spread, use_korean_font
from src.utils.settings import DATA_PROCESSED, ROOT_DIR, get_config

logger = get_logger(__name__)

FIG_DIR = ROOT_DIR / "reports" / "figures"
use_korean_font()

# 지수 구성 변수 (로그 대상은 LOG_VARS)
VARS = {
    "store_food": "음식점",
    "store_cafe": "카페",
    "facility_cnt": "집객시설",
    "slots_per_1k": "천명당주차면",
    "z_residual": "주차여유(잔차)",
}
LOG_VARS = ["store_food", "store_cafe", "facility_cnt", "slots_per_1k"]

# 부호를 고정할 기준 변수 (이 변수의 로딩이 양수가 되도록 뒤집는다)
SIGN_ANCHOR = {0: "store_food", 1: "slots_per_1k"}
AXIS_NAME = {0: "매력도지수", 1: "주차여유지수"}


def load_data() -> pd.DataFrame:
    cfg = get_config()["panel"]["regression_baseline"]
    panel = pd.read_csv(DATA_PROCESSED / "panel.csv", dtype={"adm_cd": str, "admi_cd": str})
    res = pd.read_csv(DATA_PROCESSED / "dong_residual.csv", dtype={"adm_cd": str, "admi_cd": str})
    d = panel[(panel.weekday == cfg["weekday"]) & (panel.timeslot == cfg["timeslot"])].merge(
        res[["admi_cd", "z_residual"]], on="admi_cd", how="left")
    d = d[d.has_parking].dropna(subset=list(VARS)).copy()
    logger.info(f"기준 {cfg['weekday']}요일 {cfg['timeslot']} / 행정동 {len(d)}개")
    return d


def build_index(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, PCA]:
    X = d[list(VARS)].copy()
    for c in LOG_VARS:
        X[c] = np.log1p(X[c])
    z = StandardScaler().fit_transform(X)

    pca = PCA(random_state=0).fit(z)
    scores = pca.transform(z)

    # 부호 고정 — 기준 변수의 로딩이 음수면 축 전체를 뒤집는다
    cols = list(VARS)
    comps = pca.components_.copy()
    for pc, anchor in SIGN_ANCHOR.items():
        if comps[pc, cols.index(anchor)] < 0:
            comps[pc] *= -1
            scores[:, pc] *= -1
            logger.info(f"PC{pc+1} 부호 반전 ({anchor} 로딩이 양수가 되도록)")

    d = d.copy()
    for pc, name in AXIS_NAME.items():
        d[name] = scores[:, pc]
        d[f"{name}_pct"] = d[name].rank(pct=True) * 100

    # 병목 구조를 반영해 기하평균으로 결합
    d["나들이적합도"] = np.sqrt(d.매력도지수_pct * d.주차여유지수_pct)

    loadings = pd.DataFrame(comps[:2].T, index=[VARS[c] for c in cols],
                            columns=[AXIS_NAME[0], AXIS_NAME[1]])
    ev = pca.explained_variance_ratio_
    logger.info(f"설명분산 PC1 {ev[0]:.1%} / PC2 {ev[1]:.1%} (합 {ev[:2].sum():.1%})")
    return d, loadings, pca


def plot(d: pd.DataFrame, loadings: pd.DataFrame, pca: PCA) -> None:
    ev = pca.explained_variance_ratio_
    fig, axes = plt.subplots(1, 3, figsize=(19, 6.2))

    # ① 두 지수 평면 — 적합도 상위가 오른쪽 위에 모이는지
    ax = axes[0]
    sc = ax.scatter(d.매력도지수_pct, d.주차여유지수_pct, c=d.나들이적합도,
                    cmap="RdYlGn", s=26, alpha=0.85, edgecolor="none")
    fig.colorbar(sc, ax=ax, shrink=0.85, label="나들이 적합도")
    annotate_spread(ax, [(r.매력도지수_pct, r.주차여유지수_pct, r.admi_nm)
                         for _, r in d.nlargest(7, "나들이적합도").iterrows()])
    ax.set_xlabel(f"매력도 지수 백분위 (PC1, {ev[0]:.0%})")
    ax.set_ylabel(f"주차 여유 지수 백분위 (PC2, {ev[1]:.0%})")
    ax.set_title(f"나들이 적합도 = 두 지수의 기하평균 (n={len(d)})")
    ax.grid(alpha=0.3)

    # ② 로딩 — 축이 어떻게 구성됐는지 (해석의 근거)
    ax = axes[1]
    im = ax.imshow(loadings.values, cmap="RdBu_r", vmin=-0.8, vmax=0.8, aspect="auto")
    ax.set_xticks(range(2), loadings.columns)
    ax.set_yticks(range(len(loadings)), loadings.index)
    for i in range(loadings.shape[0]):
        for j in range(loadings.shape[1]):
            v = loadings.iloc[i, j]
            ax.text(j, i, f"{v:+.3f}", ha="center", va="center", fontsize=10,
                    color="white" if abs(v) > 0.5 else "black")
    ax.set_title("주성분 로딩 — 두 축이 분리되었는가")
    fig.colorbar(im, ax=ax, shrink=0.85)

    # ③ 적합도 TOP 15
    ax = axes[2]
    top = d.nlargest(15, "나들이적합도").iloc[::-1]
    yy = np.arange(len(top))
    ax.barh(yy - 0.2, top.매력도지수_pct, height=0.4, color="#F58518", label="매력도")
    ax.barh(yy + 0.2, top.주차여유지수_pct, height=0.4, color="#4C78A8", label="주차 여유")
    ax.set_yticks(yy, [f"{r.sgg_nm} {r.admi_nm}  ({r.나들이적합도:.0f})"
                       for _, r in top.iterrows()], fontsize=8)
    ax.set_xlabel("백분위")
    ax.set_title("나들이 적합도 TOP 15")
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "suitability.png", dpi=150)
    plt.close(fig)
    logger.info("저장: suitability.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    d, loadings, pca = build_index(load_data())

    print("\n=== 주성분 로딩 (부호 고정 후) ===")
    print(loadings.round(3).to_string())
    ev = pca.explained_variance_ratio_
    print(f"\n  설명분산 {AXIS_NAME[0]} {ev[0]:.1%} / {AXIS_NAME[1]} {ev[1]:.1%} "
          f"(두 축 합계 {ev[:2].sum():.1%})")
    print("  -> 매력도 변수 3종과 주차 변수 2종이 서로 다른 축으로 분리됨.")
    print("     축을 사람이 정한 것이 아니라 데이터 구조에서 나온 것이 지수의 근거.")

    cols = ["adm_cd", "admi_cd", "sgg_nm", "admi_nm", "나들이적합도",
            "매력도지수", "매력도지수_pct", "주차여유지수", "주차여유지수_pct",
            *VARS]
    dest = DATA_PROCESSED / "dong_suitability.csv"
    d[cols].sort_values("나들이적합도", ascending=False).to_csv(
        dest, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {dest} ({len(d)}행)")

    plot(d, loadings, pca)

    show = ["sgg_nm", "admi_nm", "나들이적합도", "매력도지수_pct", "주차여유지수_pct",
            "store_food", "parking_slots"]
    print("\n=== 나들이 적합도 TOP 15 ===")
    print(d.nlargest(15, "나들이적합도")[show].to_string(index=False, float_format="%.1f"))

    print("\n=== 기하평균이 산술평균과 다른 이유 (한쪽만 높은 동네) ===")
    d2 = d.copy()
    d2["산술평균"] = (d2.매력도지수_pct + d2.주차여유지수_pct) / 2
    d2["차이"] = d2.산술평균 - d2.나들이적합도
    print(d2.nlargest(8, "차이")[
        ["sgg_nm", "admi_nm", "매력도지수_pct", "주차여유지수_pct", "산술평균", "나들이적합도"]
    ].to_string(index=False, float_format="%.1f"))
    print("  -> 한쪽만 극단적으로 높은 동네는 기하평균에서 순위가 내려간다 (병목 반영)")


if __name__ == "__main__":
    main()
