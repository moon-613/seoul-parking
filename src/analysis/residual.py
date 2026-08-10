"""회귀 잔차로 공영주차 공급 과부족 진단 -> data/processed/dong_residual.csv

아이디어
-------
"사람이 이만큼 오는 동네라면 공영주차장이 대략 이 정도는 있어야 한다"는 기준선을
회귀선으로 긋고, 실제 값이 그 선보다 얼마나 위/아래인지(=잔차)를 본다.
  잔차 < 0 : 기대보다 부족  -> 공영주차 취약
  잔차 > 0 : 기대보다 여유  -> 추천 후보

왜 로그를 쓰는가
--------------
원단위(면수 ~ 생활인구)로 돌리면 회귀 가정이 깨진다.
  잔차 왜도 +2.36 / 정규성 위배 / 등분산 위배
  -> 큰 동네일수록 잔차가 커져 대형 상권이 하위권을 독식한다.
로그-로그로 바꾸면 등분산이 회복되고(p=0.45) 잔차 왜도도 -0.68로 개선된다.
해석도 "기대 대비 몇 배"가 되어 규모가 다른 동네를 공정하게 비교할 수 있다.

제외 대상
--------
공영주차면 0면인 행정동 66개는 민영 미개방 영향이 섞여 있어 제외한다.
(0면을 '공급 부족 1위'로 뽑으면 데이터 부재를 주차난으로 오독하게 된다)

설명력에 관한 결론
----------------
단순회귀 R²=0.074, 5개 변수 다중회귀로 확장해도 R²=0.092 (adj 0.079)에 그친다.
VIF는 모두 10 미만이라 다중공선성 탓이 아니다.
즉 **서울 공영주차장 공급은 생활인구·상권 규모로 거의 설명되지 않는다**는 것 자체가 발견이며,
잔차가 크다는 뜻이므로 과부족 진단(잔차 분석)은 오히려 의미를 갖는다.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from src.utils.logger import get_logger
from src.utils.settings import DATA_PROCESSED, ROOT_DIR, get_config

logger = get_logger(__name__)

FIG_DIR = ROOT_DIR / "reports" / "figures"
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# 다중회귀 후보 (VIF로 걸러낸다)
MULTI_VARS = ["living_pop", "store_food", "facility_cnt", "resident_pop", "worker_pop"]


def load_baseline() -> pd.DataFrame:
    """회귀 기준 시점(config)의 행정동 단면."""
    cfg = get_config()["panel"]["regression_baseline"]
    panel = pd.read_csv(DATA_PROCESSED / "panel.csv", dtype={"adm_cd": str, "admi_cd": str})
    d = panel[
        (panel.weekday == cfg["weekday"])
        & (panel.timeslot == cfg["timeslot"])
        & panel.has_parking
    ].copy()
    logger.info(f"기준 시점 {cfg['weekday']}요일 {cfg['timeslot']} / 행정동 {len(d)}개 (0면 제외)")
    return d


def vif(df: pd.DataFrame) -> pd.Series:
    """분산팽창계수 — 각 변수를 나머지 변수로 회귀했을 때 1/(1-R^2)."""
    out = {}
    for col in df.columns:
        y = df[col]
        X = df.drop(columns=[col])
        X = np.column_stack([np.ones(len(X)), X.values])
        beta, *_ = np.linalg.lstsq(X, y.values, rcond=None)
        pred = X @ beta
        ss_res = ((y - pred) ** 2).sum()
        ss_tot = ((y - y.mean()) ** 2).sum()
        r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
        out[col] = 1 / (1 - r2) if r2 < 1 else np.inf
    return pd.Series(out).sort_values(ascending=False)


def fit_simple(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """로그-로그 단순회귀: log(주차면) ~ log(생활인구)."""
    x = np.log1p(d["living_pop"].to_numpy())
    y = np.log1p(d["parking_slots"].to_numpy())
    lr = stats.linregress(x, y)

    resid = y - (lr.intercept + lr.slope * x)
    d = d.copy()
    d["expected_slots"] = np.expm1(lr.intercept + lr.slope * x)
    d["residual"] = resid
    d["z_residual"] = (resid - resid.mean()) / resid.std(ddof=1)
    d["supply_ratio"] = d["parking_slots"] / d["expected_slots"]

    _, p_norm = stats.shapiro(resid)
    fit = lr.intercept + lr.slope * x
    _, p_lev = stats.levene(resid[fit < np.median(fit)], resid[fit >= np.median(fit)])

    stat = {
        "r2": lr.rvalue ** 2,
        "slope": lr.slope,
        "p_value": lr.pvalue,
        "shapiro_p": p_norm,
        "levene_p": p_lev,
        "resid_skew": stats.skew(resid),
    }
    logger.info(
        f"단순회귀 R²={stat['r2']:.3f} (p={stat['p_value']:.2e}) | "
        f"등분산 p={p_lev:.2f} | 잔차왜도 {stat['resid_skew']:+.2f}"
    )
    return d, stat


def check_multi(d: pd.DataFrame) -> pd.Series:
    """다중회귀 확장 가능성 점검 (VIF)."""
    sub = d[MULTI_VARS].dropna()
    v = vif(np.log1p(sub))
    logger.info("다중회귀 후보 VIF:")
    for k, val in v.items():
        flag = " ← 10 초과, 제외 권장" if val > 10 else ""
        logger.info(f"  {k:15} {val:6.2f}{flag}")
    return v


def classify(d: pd.DataFrame) -> pd.DataFrame:
    cfg = get_config()["imbalance_index"]
    lo, hi = cfg["vulnerable_residual_threshold"], cfg["recommend_residual_threshold"]
    d = d.copy()
    d["grade"] = np.select(
        [d.z_residual <= lo, d.z_residual >= hi],
        ["공급부족", "공급여유"],
        default="보통",
    )
    for k, v in d.grade.value_counts().items():
        logger.info(f"  {k}: {v}개 동")
    return d


def plot(d: pd.DataFrame, stat: dict) -> None:
    x = np.log1p(d["living_pop"])
    y = np.log1p(d["parking_slots"])

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    ax = axes[0]
    colors = {"공급부족": "#D62728", "공급여유": "#2CA02C", "보통": "#C7C7C7"}
    for g, sub in d.groupby("grade"):
        ax.scatter(np.log1p(sub.living_pop), np.log1p(sub.parking_slots),
                   s=18, alpha=0.75, label=g, color=colors[g])
    xs = np.linspace(x.min(), x.max(), 50)
    ax.plot(xs, np.polyval(np.polyfit(x, y, 1), xs), "k--", lw=1.2, label="기대선(회귀)")
    for _, r in pd.concat([d.nsmallest(4, "z_residual"), d.nlargest(4, "z_residual")]).iterrows():
        ax.annotate(r.admi_nm, (np.log1p(r.living_pop), np.log1p(r.parking_slots)),
                    fontsize=8, alpha=0.85)
    ax.set_xlabel("log(생활인구)"); ax.set_ylabel("log(공영주차면)")
    ax.set_title(f"공영주차 공급 vs 생활인구  (R²={stat['r2']:.3f}, n={len(d)})")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)

    ax = axes[1]
    ax.hist(d.z_residual, bins=32, color="#4C78A8", edgecolor="white")
    ax.axvline(-1, color="#D62728", ls="--", lw=1.2, label="공급부족 기준 (-1)")
    ax.axvline(1, color="#2CA02C", ls="--", lw=1.2, label="공급여유 기준 (+1)")
    ax.set_xlabel("표준화 잔차"); ax.set_ylabel("행정동 수")
    ax.set_title("표준화 잔차 분포")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "residual.png", dpi=150)
    plt.close(fig)
    logger.info("저장: residual.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    d = load_baseline()
    d, stat = fit_simple(d)
    check_multi(d)
    d = classify(d)

    cols = ["adm_cd", "admi_cd", "sgg_nm", "admi_nm", "living_pop", "store_food",
            "parking_slots", "expected_slots", "supply_ratio", "residual", "z_residual", "grade"]
    out = d[cols].sort_values("z_residual")
    dest = DATA_PROCESSED / "dong_residual.csv"
    out.to_csv(dest, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {dest} ({len(out)}행)")

    plot(d, stat)

    show = ["sgg_nm", "admi_nm", "living_pop", "store_food", "parking_slots", "expected_slots", "z_residual"]
    print("\n=== 공영주차 공급 부족 TOP 10 (기대 대비) ===")
    print(out.head(10)[show].to_string(index=False, float_format="%.0f"))
    print("\n=== 공영주차 공급 여유 TOP 10 ===")
    print(out.tail(10)[show].iloc[::-1].to_string(index=False, float_format="%.0f"))


if __name__ == "__main__":
    main()
