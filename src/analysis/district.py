"""자치구 단위 요약 -> data/processed/sgg_summary.csv

왜 자치구 단위가 따로 필요한가
--------------------------
공영주차장 확충·재배치를 실제로 집행하는 주체는 **자치구**다.
그런데 지금까지의 산출물은 전부 행정동 단위여서, 담당자가 "우리 구에 뭐가 몇 개인지"를
보려면 424행을 직접 훑어야 한다. 부 사용자가 곧바로 쓸 수 있는 형태로 접어 준다.

담는 것
------
  실수요 규모      비아파트 가구 합계 (공영주차에 의존하는 가구)
  공급             공영주차면 합계, 실수요 100가구당 주차면
  확충 후보        정주수요 기준 공급부족(z <= -1) 행정동 수와 이름
  확충 불필요      비아파트 100가구 미만 행정동 수 (예산을 쓰면 안 되는 곳)
  0면 동           공영주차가 아예 없는 행정동 수
  나들이 적합도    구 내 최고 동네 (주 사용자용)

주의
----
자치구 지표는 행정동 합계이지 평균이 아니다. 큰 구가 자동으로 상위에 오므로
'실수요 100가구당 주차면'처럼 규모를 나눈 지표로 비교해야 한다.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.utils.logger import get_logger
from src.utils.plotstyle import use_korean_font
from src.utils.settings import DATA_PROCESSED, ROOT_DIR, get_config

logger = get_logger(__name__)

FIG_DIR = ROOT_DIR / "reports" / "figures"
use_korean_font()

TOP_N_NAMES = 4     # 표에 이름을 적어 줄 확충 후보 수


def load_all() -> pd.DataFrame:
    """기준 시점 패널에 실수요 진단·적합도 결과를 붙인다."""
    cfg = get_config()["panel"]["regression_baseline"]
    panel = pd.read_csv(DATA_PROCESSED / "panel.csv", dtype={"adm_cd": str, "admi_cd": str})
    d = panel[(panel.weekday == cfg["weekday"]) & (panel.timeslot == cfg["timeslot"])].copy()

    for name, cols in [("dong_real_demand.csv", ["admi_cd", "확충필요성", "구분",
                                                 "판정_유동", "판정_정주", "z_정주"]),
                       ("dong_suitability.csv", ["admi_cd", "나들이적합도"])]:
        path = DATA_PROCESSED / name
        if not path.exists():
            raise FileNotFoundError(f"{name}이 없습니다. 해당 분석을 먼저 실행하세요.")
        d = d.merge(pd.read_csv(path, dtype={"adm_cd": str, "admi_cd": str})[cols],
                    on="admi_cd", how="left")
    logger.info(f"기준 {cfg['weekday']}요일 {cfg['timeslot']} / 행정동 {len(d)}개")
    return d


def summarize(d: pd.DataFrame) -> pd.DataFrame:
    def names(sub: pd.DataFrame) -> str:
        top = sub.nsmallest(TOP_N_NAMES, "z_정주")
        return ", ".join(top.admi_nm) if len(top) else "-"

    rows = []
    for sgg, g in d.groupby("sgg_nm"):
        cand = g[g.판정_정주 == "공급부족"]
        rows.append({
            "자치구": sgg,
            "행정동수": len(g),
            "비아파트가구": g.non_apt_households.sum(),
            "공영주차면": g.parking_slots.sum(),
            "실수요100가구당": g.parking_slots.sum() / g.non_apt_households.sum() * 100,
            "확충후보": len(cand),
            "확충불필요": (g.확충필요성 == "불필요").sum(),
            "주차0면동": (~g.has_parking).sum(),
            "최고적합도동": (g.loc[g.나들이적합도.idxmax(), "admi_nm"]
                          if g.나들이적합도.notna().any() else "-"),
            "최고적합도": g.나들이적합도.max(),
            "확충후보동명": names(cand),
        })
    out = pd.DataFrame(rows).sort_values("실수요100가구당").reset_index(drop=True)
    out.insert(0, "공급순위", range(1, len(out) + 1))
    return out


def plot(s: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(19, 7.5))

    # ① 실수요 대비 공급 — 규모를 나눈 지표라야 구끼리 비교된다
    ax = axes[0]
    v = s.sort_values("실수요100가구당")
    med = v.실수요100가구당.median()
    ax.barh(v.자치구, v.실수요100가구당,
            color=["#D62728" if x < med else "#4C78A8" for x in v.실수요100가구당])
    ax.axvline(med, color="#333", ls="--", lw=1.2, label=f"서울 중앙값 {med:.1f}")
    ax.set_xlabel("실수요 100가구당 공영주차면")
    ax.set_title("자치구별 실수요 대비 공영주차 공급")
    ax.legend(fontsize=9)
    ax.grid(axis="x", alpha=0.3)

    # ② 확충 후보 / 불필요 / 0면
    ax = axes[1]
    v = s.sort_values("확충후보")
    yy = np.arange(len(v))
    ax.barh(yy, v.확충후보, color="#D62728", label="확충 후보")
    ax.barh(yy, v.확충불필요, left=v.확충후보, color="#C7C7C7", label="확충 불필요")
    ax.barh(yy, v.주차0면동, left=v.확충후보 + v.확충불필요, color="#7A0C0C", label="공영주차 0면")
    ax.set_yticks(yy, v.자치구, fontsize=9)
    ax.set_xlabel("행정동 수")
    ax.set_title("자치구별 확충 후보·불필요·0면 동")
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(axis="x", alpha=0.3)

    # ③ 실수요 규모 vs 공급 — 어느 구가 선 아래인가
    ax = axes[2]
    ax.scatter(s.비아파트가구, s.공영주차면, s=60, color="#4C78A8", alpha=0.85)
    z = np.polyfit(s.비아파트가구, s.공영주차면, 1)
    xs = np.linspace(s.비아파트가구.min(), s.비아파트가구.max(), 50)
    ax.plot(xs, np.polyval(z, xs), "k--", lw=1.2, label="서울 평균 추세")
    for _, r in s.iterrows():
        ax.annotate(r.자치구, (r.비아파트가구, r.공영주차면), fontsize=7.5,
                    xytext=(4, 3), textcoords="offset points")
    ax.set_xlabel("비아파트 가구 수 (공영주차 실수요)")
    ax.set_ylabel("공영주차면 수")
    ax.set_title("실수요 규모 대비 공급 — 선 아래가 부족한 구")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "district.png", dpi=150)
    plt.close(fig)
    logger.info("저장: district.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    s = summarize(load_all())

    dest = DATA_PROCESSED / "sgg_summary.csv"
    s.to_csv(dest, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {dest} ({len(s)}행)")

    plot(s)

    print("\n=== 자치구 요약 (실수요 대비 공급이 부족한 순) ===")
    show = ["공급순위", "자치구", "행정동수", "비아파트가구", "공영주차면",
            "실수요100가구당", "확충후보", "확충불필요", "주차0면동"]
    print(s[show].to_string(index=False, float_format="%.1f"))

    print("\n=== 확충 후보가 많은 자치구 TOP 8 ===")
    for _, r in s.nlargest(8, "확충후보").iterrows():
        print(f"  {r.자치구:5} 후보 {r.확충후보}개 — {r.확충후보동명}")

    print("\n=== 확충 불필요 동이 있는 자치구 (예산 배분 시 제외할 곳) ===")
    for _, r in s[s.확충불필요 > 0].sort_values("확충불필요", ascending=False).iterrows():
        print(f"  {r.자치구:5} {r.확충불필요}개 동")

    print("\n=== 나들이 적합도 최고 동네 (주 사용자용) ===")
    for _, r in s.nlargest(8, "최고적합도").iterrows():
        print(f"  {r.자치구:5} {r.최고적합도동} ({r.최고적합도:.1f}점)")


if __name__ == "__main__":
    main()
