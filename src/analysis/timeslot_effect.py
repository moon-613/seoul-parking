"""가설 5 — 시간대 조정만으로 주차 여유가 얼마나 달라지는가 -> reports/figures/timeslot_effect.png

검증하는 것
----------
같은 동네를 **언제 가느냐만 바꿔도** 주차 여유가 유의하게 달라지는가.
달라진다면 이용자는 목적지를 바꾸지 않고도 만차를 피할 수 있다.

무엇이 변하는가 (중요)
-------------------
공영주차면수는 시간에 따라 변하지 않는다. `slots_per_1k`가 흔들리는 것은 오직
분모인 생활인구가 바뀌기 때문이다. 따라서 이 분석이 말하는 것은
'주차장이 늘어난다'가 아니라 **'같은 주차장을 두고 경쟁할 사람이 줄어든다'** 이다.
보고서에도 이 표현을 그대로 쓸 것.

검정 방법
--------
행정동마다 요일×시간대 값이 하나씩이라 동 내부 분산이 없다.
그래서 **행정동을 블록으로 두는 프리드먼 검정**을 쓴다.
  H0: 시점(요일·시간대)에 따라 주차 여유 순위가 다르지 않다
정규성을 가정하지 않고 동별 순위만 쓰므로, 규모가 크게 다른 동네를 함께 넣어도 된다.

유의성과 체감은 다르다
-------------------
n=350 규모에서는 사소한 차이도 유의해진다. 그래서 p값과 함께
**동별 개선율((최대-최소)/최소)** 분포를 같이 본다. 실제로 쓸 만한지는 이쪽이 답한다.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from src.utils.logger import get_logger
from src.utils.plotstyle import use_korean_font
from src.utils.settings import DATA_PROCESSED, ROOT_DIR
from src.utils.timeslot import timeslot_order

logger = get_logger(__name__)

FIG_DIR = ROOT_DIR / "reports" / "figures"
use_korean_font()

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
MEANINGFUL = 0.20   # 체감 가능한 개선률 기준 (+20%)


def load_wide() -> pd.DataFrame:
    """행정동 × (요일, 시간대) 주차 여유 행렬. 28개 시점이 모두 있는 동만 남긴다."""
    panel = pd.read_csv(DATA_PROCESSED / "panel.csv", dtype={"adm_cd": str, "admi_cd": str})
    d = panel[panel.has_parking]
    w = d.pivot_table(index=["admi_cd", "sgg_nm", "admi_nm"],
                      columns=["weekday", "timeslot"], values="slots_per_1k", observed=True)
    w = w.reindex(columns=pd.MultiIndex.from_product(
        [WEEKDAYS, timeslot_order()], names=["weekday", "timeslot"]))
    before = len(w)
    w = w.dropna()
    logger.info(f"행정동 {before}개 중 28개 시점이 모두 있는 {len(w)}개 사용")
    return w


def friedman(w: pd.DataFrame, level: str) -> tuple[float, float, int]:
    """행정동을 블록으로 한 프리드먼 검정. level='timeslot' | 'weekday' | 'all'."""
    if level == "all":
        groups = [w[c].to_numpy() for c in w.columns]
    else:
        agg = w.T.groupby(level=level).mean().T
        order = timeslot_order() if level == "timeslot" else WEEKDAYS
        groups = [agg[c].to_numpy() for c in order]
    stat, p = stats.friedmanchisquare(*groups)
    return stat, p, len(groups)


def effect_sizes(w: pd.DataFrame) -> pd.DataFrame:
    """동별 최적/최악 시점과 개선율."""
    best_i = w.values.argmax(axis=1)
    worst_i = w.values.argmin(axis=1)
    cols = list(w.columns)

    out = pd.DataFrame({
        "최적요일": [cols[i][0] for i in best_i],
        "최적시간대": [cols[i][1] for i in best_i],
        "최적값": w.values.max(axis=1),
        "최악요일": [cols[i][0] for i in worst_i],
        "최악시간대": [cols[i][1] for i in worst_i],
        "최악값": w.values.min(axis=1),
    }, index=w.index)
    out["개선율"] = out.최적값 / out.최악값 - 1
    return out.reset_index()


def plot(w: pd.DataFrame, eff: pd.DataFrame, p_all: float) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))

    # ① 서울 전체 시점별 여유 지수
    ax = axes[0]
    idx = w.mean() / w.mean().mean() * 100
    for wd in WEEKDAYS:
        sub = idx.loc[wd]
        ax.plot(timeslot_order(), sub.values, "o-", lw=1.6, ms=5, label=wd,
                color=("#D62728" if wd in ("토", "일") else "#4C78A8"),
                alpha=1.0 if wd in ("토", "일") else 0.45)
    ax.axhline(100, color="#888", ls="--", lw=1)
    ax.set_ylabel("주차 여유 지수 (전체 평균=100)")
    ax.set_title("시점별 주차 여유 — 서울 평균")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.3)

    # ② 동별 개선율 분포
    ax = axes[1]
    ax.hist(eff.개선율 * 100, bins=34, color="#4C78A8", edgecolor="white")
    med = eff.개선율.median() * 100
    ax.axvline(med, color="#F58518", lw=1.8, label=f"중앙값 {med:.0f}%")
    ax.axvline(MEANINGFUL * 100, color="#2CA02C", ls="--", lw=1.4,
               label=f"체감 기준 +{MEANINGFUL:.0%}")
    ax.set_xlabel("최적 시점 대비 최악 시점 개선율 (%)")
    ax.set_ylabel("행정동 수")
    ax.set_title(f"동별 시간대 조정 효과 (프리드먼 p={p_all:.1e})")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # ③ 효과가 큰 동네 TOP 12
    ax = axes[2]
    top = eff.nlargest(12, "개선율").iloc[::-1]
    ax.barh(range(len(top)), top.개선율 * 100, color="#2CA02C")
    ax.set_yticks(range(len(top)),
                  [f"{r.admi_nm}\n{r.최악요일}·{r.최악시간대} → {r.최적요일}·{r.최적시간대}"
                   for _, r in top.iterrows()], fontsize=7.5)
    ax.set_xlabel("개선율 (%)")
    ax.set_title("시간대만 바꿔도 효과가 큰 동네 TOP 12")
    ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "timeslot_effect.png", dpi=150)
    plt.close(fig)
    logger.info("저장: timeslot_effect.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    w = load_wide()
    eff = effect_sizes(w)

    print("\n=== 프리드먼 검정 (행정동을 블록으로) ===")
    for level, label in [("timeslot", "시간대 4구간"), ("weekday", "요일 7개"), ("all", "요일×시간대 28개")]:
        stat, p, k = friedman(w, level)
        print(f"  {label:14} chi2={stat:9.1f}  df={k-1:2}  p={p:.3e}  "
              f"{'유의' if p < 0.05 else '유의하지 않음'}")

    _, p_all, _ = friedman(w, "all")

    print("\n=== 개선율 분포 (최적 시점 / 최악 시점) ===")
    q = eff.개선율.quantile([0.25, 0.5, 0.75, 0.9, 1.0])
    for k, v in q.items():
        print(f"  {k:.0%} 분위 : {v:+.1%}")
    n_big = (eff.개선율 >= MEANINGFUL).sum()
    print(f"\n  +{MEANINGFUL:.0%} 이상 개선되는 동: {n_big}개 / {len(eff)}개 ({n_big/len(eff):.1%})")

    print("\n=== 언제가 가장 여유로운가 (동별 최적 시점 빈도) ===")
    vc = eff.groupby(["최적요일", "최적시간대"], observed=True).size().nlargest(8)
    for (wd, ts), n in vc.items():
        print(f"  {wd}요일 {ts:4} : {n:3}개 동")

    print("\n=== 시간대만 바꿔도 효과가 큰 동네 TOP 10 ===")
    show = ["sgg_nm", "admi_nm", "최악요일", "최악시간대", "최악값", "최적요일", "최적시간대", "최적값", "개선율"]
    top = eff.nlargest(10, "개선율")[show].copy()
    top["개선율"] = (top.개선율 * 100).round(0).astype(int).astype(str) + "%"
    print(top.to_string(index=False, float_format="%.1f"))

    dest = DATA_PROCESSED / "dong_timeslot.csv"
    eff.sort_values("개선율", ascending=False).to_csv(dest, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {dest} ({len(eff)}행)")

    plot(w, eff, p_all)

    print("\n=== 가설 5 판정 ===")
    print(f"  시점 효과는 통계적으로 유의(p={p_all:.1e})하며, 동별 개선율 중앙값 "
          f"{eff.개선율.median():+.1%} / 상위 10% {eff.개선율.quantile(0.9):+.1%}")
    print(f"  -> 지지: 목적지를 바꾸지 않고 시점만 옮겨도 {n_big}개 동에서 "
          f"+{MEANINGFUL:.0%} 이상 여유해짐")


if __name__ == "__main__":
    main()
