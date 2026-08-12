"""발표 슬라이드 전용 그림 -> reports/figures/deck/*.png

왜 분석 그림을 그대로 안 쓰는가
---------------------------
`reports/figures/`의 그림은 **분석용**이라 한 장에 패널이 3~4개씩 붙어 있다.
근거를 나란히 놓고 검토하기에는 좋지만, 4:3 슬라이드에 넣으면 축 글자가 6pt가 되어
객석에서 읽히지 않는다. 발표는 10분이고 장당 40초라 **한 장에 메시지가 하나**여야 한다.

그래서 같은 데이터에서 슬라이드용을 따로 그린다.
  · 패널 1개 (많아야 2개)
  · 폰트 12pt 이상, 값 라벨을 직접 찍어 축을 읽지 않아도 되게
  · 가로 10 × 세로 4.6 inch — 4:3 슬라이드의 그림 자리에 맞춘 비율

분석 그림은 보고서·부록에 그대로 남는다. 여기서 만드는 것은 발표용 사본이다.

그림에 제목을 넣지 않는 이유
------------------------
슬라이드가 이미 제목을 갖는다. 그림에도 제목을 달면 같은 문장이 두 번 나와
시선이 갈라지고 그림에 쓸 세로 공간만 줄어든다. 메시지는 슬라이드 제목이 지고,
그림은 근거만 보인다. (build_deck.py의 _header가 제목을 담당)
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

logger = get_logger(__name__)

OUT = ROOT_DIR / "reports" / "figures" / "deck"
use_korean_font()

# 슬라이드 그림 자리 비율 (16:9 슬라이드의 본문 영역)
FIGSIZE = (11.5, 4.3)
# 300dpi — 슬라이드를 큰 화면에 띄우거나 PDF로 확대해도 글자가 뭉개지지 않는다.
# 200dpi로는 정사각형에 가까운 그림(상관 히트맵)이 특히 흐릿했다.
DPI = 300

# 색 — 대시보드(common.py)와 같은 역할 배정을 쓴다
ALERT = "#d03b3b"
ALERT_STRONG = "#8f1f1f"
ACCENT = "#2a78d6"
ACCENT_LIGHT = "#86b6ef"
NEUTRAL = "#c3c2b7"
INK = "#0b0b0b"
MUTED = "#898781"

plt.rcParams.update({
    # 맑은 고딕에 U+2212(−)가 없어 음수 축 라벨이 두부로 나온다
    "axes.unicode_minus": False,
    "font.size": 12,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
})


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"저장: deck/{name}.png")


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_PROCESSED / name, dtype={"adm_cd": str, "admi_cd": str})


# ─────────────────────────────────────────────────────────────
# 8번 슬라이드 — 핵심 결과: 두 수요 기준 모두 공급을 설명하지 못한다
# ─────────────────────────────────────────────────────────────
def fig_core_result() -> None:
    """발표 전체에서 가장 중요한 한 장. 산점도 둘을 나란히 놓고 R²를 크게 박는다."""
    # 거주형태는 panel.csv에 이미 붙어 있다 (build_panel이 총조사를 결합)
    #
    # 표본을 real_demand.py와 **똑같이** 잡는다. 그러지 않으면 그림에 찍힌 점과
    # 라벨의 R²가 서로 다른 집단의 값이 되어 슬라이드가 스스로 어긋난다.
    #   유동수요  주차장 있는 358개 전체
    #   정주수요  그중 비아파트 100가구 이상(=확충 검토대상)만
    #             비아파트 1~7가구짜리를 넣으면 실수요 비교라는 의미가 흐려진다
    MIN_NONAPT = 100
    panel = load("panel.csv")
    base = panel[(panel.weekday == "토") & (panel.timeslot == "오후")].dropna(
        subset=["non_apt_households", "living_pop", "parking_slots"])
    flow = base[base.has_parking]
    res = flow[flow.non_apt_households >= MIN_NONAPT]

    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE)
    specs = [
        (flow, flow.living_pop, "유동수요 — 생활인구(명)", ACCENT),
        (res, res.non_apt_households, "정주수요 — 비아파트 가구(호)", ALERT),
    ]
    for ax, (sub, x, xlabel, color) in zip(axes, specs):
        lx, ly = np.log1p(x), np.log1p(sub.parking_slots)
        ax.scatter(lx, ly, s=14, alpha=0.5, color=color, edgecolor="none")
        lr = stats.linregress(lx, ly)
        xs = np.linspace(lx.min(), lx.max(), 50)
        ax.plot(xs, lr.intercept + lr.slope * xs, "--", lw=2, color=INK)
        # 회귀선이 거의 평평하다는 것이 결론이므로 R²를 그림 안에 크게 둔다.
        # 값은 박아두지 않고 그린 데이터에서 바로 계산한다
        ax.text(0.04, 0.93, f"R² = {lr.rvalue ** 2:.3f}", transform=ax.transAxes,
                fontsize=20, fontweight="bold", color=color, va="top")
        ax.text(0.04, 0.80, f"n = {len(sub)}", transform=ax.transAxes,
                fontsize=12, color=MUTED, va="top")
        ax.set_xlabel(f"log  {xlabel}")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("log  공영주차면")
    save(fig, "01_core_result")
    logger.info(f"  핵심결과 R² 유동 {stats.linregress(np.log1p(flow.living_pop), np.log1p(flow.parking_slots)).rvalue**2:.3f}"
                f" / 정주 {stats.linregress(np.log1p(res.non_apt_households), np.log1p(res.parking_slots)).rvalue**2:.3f}")


# ─────────────────────────────────────────────────────────────
# 9번 슬라이드 — 가설 1·3 기각
# ─────────────────────────────────────────────────────────────
def fig_hypothesis_13() -> None:
    """상관계수를 막대 하나로. 히트맵보다 '거의 0'이 바로 보인다.

    값은 박아두지 않고 explore.py와 같은 조건(토·오후, 0면 동 제외)으로 직접 계산한다.
    """
    panel = load("panel.csv")
    d = panel[(panel.weekday == "토") & (panel.timeslot == "오후") & panel.has_parking]
    specs = [("생활인구 ↔ 천명당 주차면", "living_pop"),
             ("20~30대 비중 ↔ 천명당 주차면", "young_ratio"),
             ("음식점 수 ↔ 천명당 주차면", "store_food")]
    labels, vals = [], []
    for label, col in specs:
        ok = d.dropna(subset=[col, "slots_per_1k"])
        labels.append(label)
        vals.append(stats.pearsonr(ok[col], ok.slots_per_1k)[0])

    fig, ax = plt.subplots(figsize=(11.5, 3.4))
    colors = [ACCENT if abs(v) >= 0.1 else NEUTRAL for v in vals]
    y = np.arange(len(vals))
    ax.barh(y, vals, color=colors, height=0.55)
    for i, v in enumerate(vals):
        ax.text(v - 0.006, i, f"{v:+.3f}", va="center", ha="right",
                fontsize=13, fontweight="bold")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.axvline(0, color=INK, lw=1)
    # 통상적인 '약한 상관' 기준선을 그어 눈금 없이도 크기를 가늠하게 한다
    ax.axvline(-0.3, color=MUTED, ls=":", lw=1.2)
    ax.text(-0.3, -0.75, "약한 상관 기준 -0.3", fontsize=10, color=MUTED, ha="center")
    ax.set_xlim(-0.42, 0.02)
    ax.set_xlabel("피어슨 상관계수")
    ax.grid(axis="x", alpha=0.25)
    save(fig, "02_hypothesis_13")


# ─────────────────────────────────────────────────────────────
# 10번 슬라이드 — 가설 2: 두 유형의 시간대 패턴이 뒤집혀 있다
# ─────────────────────────────────────────────────────────────
def fig_cluster_pattern() -> None:
    """상권형·주거형의 요일×시간대 프로파일. '정확히 반대'가 메시지다."""
    panel = load("panel.csv")
    cl = load("dong_cluster.csv")
    d = panel.merge(cl[["admi_cd", "유형"]], on="admi_cd", how="inner")
    d = d[d.has_parking]

    order = ["오전", "점심", "오후", "저녁", "밤"]
    fig, ax = plt.subplots(figsize=FIGSIZE)
    styles = {"상권형": (ALERT, "-"), "주거형": (ACCENT, "-")}
    for t, sub in d.groupby("유형"):
        # 유형마다 규모가 달라 절대값은 비교가 안 된다. 자기 평균=100 지수로 바꾼다
        prof = sub.groupby(["weekday", "timeslot"], observed=True).slots_per_1k.mean()
        prof = (prof / prof.mean() * 100).reset_index()
        prof["x"] = prof.weekday.astype(str) + "·" + prof.timeslot.astype(str)
        keys = [f"{w}·{s}" for w in ["월", "화", "수", "목", "금", "토", "일"] for s in order]
        prof = prof.set_index("x").reindex(keys)
        color, ls = styles.get(t, (MUTED, "-"))
        ax.plot(range(len(prof)), prof.slots_per_1k, ls, color=color, lw=2,
                label=f"{t} ({(cl.유형 == t).sum()}개 동)")

    ax.axhline(100, color=MUTED, ls=":", lw=1)
    ax.set_xticks([i * 5 + 2 for i in range(7)], ["월", "화", "수", "목", "금", "토", "일"])
    for i in range(1, 7):
        ax.axvline(i * 5 - 0.5, color="#dddcd6", lw=1)
    # 주말은 배경으로 구분 — 상권형이 뒤집히는 구간이라 눈이 먼저 가야 한다
    ax.axvspan(24.5, len(prof) - 0.5, color="#f4f3ef", zorder=0)
    ax.set_ylabel("주차 여유 지수\n(유형 내 평균 = 100)")
    ax.set_xlabel("요일 안에서는 오전 → 점심 → 오후 → 저녁 → 밤 순", fontsize=11, color=MUTED)
    ax.legend(fontsize=11, loc="upper left")
    ax.grid(axis="y", alpha=0.25)
    save(fig, "03_cluster_pattern")


# ─────────────────────────────────────────────────────────────
# 11번 슬라이드 — 가설 5: 시간대 조정 효과
# ─────────────────────────────────────────────────────────────
def fig_timeslot_effect() -> None:
    """개선율 분포 + 85.2%라는 실용 수치."""
    t = load("dong_timeslot.csv")
    # 원본은 비율(0.345)로 저장된다. 축을 %로 쓰므로 여기서 100을 곱한다
    pct = t.개선율 * 100
    med = pct.median()
    share = (pct >= 20).mean() * 100

    fig, ax = plt.subplots(figsize=FIGSIZE)
    bins = np.linspace(0, pct.quantile(0.97), 40)
    ax.hist(pct, bins=bins, color=ACCENT_LIGHT, edgecolor="white")
    ax.axvline(20, color=MUTED, ls=":", lw=1.5)
    ax.axvline(med, color=ALERT, ls="--", lw=2)
    ax.text(med, ax.get_ylim()[1] * 0.92, f"  중앙값 +{med:.1f}%",
            color=ALERT, fontsize=13, fontweight="bold")
    # 막대와 겹치지 않게 선 왼쪽 위 빈 공간에 둔다
    ax.text(19, ax.get_ylim()[1] * 0.80, "+20% 기준 ", color=MUTED, fontsize=11, ha="right")
    ax.set_xlabel("같은 동네에서 시점만 바꿨을 때의 주차 여유 개선율 (%)")
    ax.set_ylabel("행정동 수")
    ax.grid(axis="y", alpha=0.25)
    save(fig, "04_timeslot_effect")


# ─────────────────────────────────────────────────────────────
# 12번 슬라이드 — 가설 4: 추천 / 혼잡 주의
# ─────────────────────────────────────────────────────────────
def fig_recommend() -> None:
    """매력도 × 주차여유 평면. 네 등급이 어디에 있는지만 보이면 된다."""
    r = load("dong_recommend.csv")
    d = r[r.등급 != "공영주차 없음"]

    color = {"추천": ACCENT, "혼잡 주의": ALERT, "한산": ACCENT_LIGHT, "보통": NEUTRAL}
    fig, ax = plt.subplots(figsize=FIGSIZE)
    for g in ["보통", "한산", "혼잡 주의", "추천"]:
        sub = d[d.등급 == g]
        if sub.empty:
            continue
        ax.scatter(sub.appeal, sub.z_residual, s=34 if g in ("추천", "혼잡 주의") else 16,
                   color=color.get(g, NEUTRAL), alpha=0.85,
                   label=f"{g} {len(sub)}개", edgecolor="none", zorder=3 if g == "추천" else 2)

    ax.axhline(1, color=MUTED, ls=":", lw=1)
    ax.axhline(-1, color=MUTED, ls=":", lw=1)
    ax.axvline(60, color=MUTED, ls=":", lw=1)
    for nm, dx, dy in [("신촌동", 6, -4), ("논현2동", 6, 4)]:
        row = d[d.admi_nm == nm]
        if len(row):
            row = row.iloc[0]
            ax.annotate(nm, (row.appeal, row.z_residual), textcoords="offset points",
                        xytext=(dx, dy), fontsize=11, fontweight="bold", color=ALERT_STRONG)
    ax.set_xlabel("매력도 백분위 (음식점·카페·집객시설)")
    ax.set_ylabel("주차 여유\n(표준화 잔차)")
    ax.legend(fontsize=11, loc="upper left", framealpha=0.9)
    ax.grid(alpha=0.25)
    save(fig, "05_recommend")


# ─────────────────────────────────────────────────────────────
# 13번 슬라이드 — 가설 6: 아파트가 만드는 오탐
# ─────────────────────────────────────────────────────────────
def fig_false_positive() -> None:
    """생활인구 기준으로 '공급부족'인데 비아파트가 2~35호뿐인 동."""
    rd = load("dong_real_demand.csv")
    sub = rd[(rd.확충필요성 == "불필요") & rd.z_유동.notna()].nsmallest(6, "z_유동")
    sub = sub.sort_values("z_유동")

    fig, ax = plt.subplots(figsize=FIGSIZE)
    y = np.arange(len(sub))
    colors = [ALERT if v <= -1 else NEUTRAL for v in sub.z_유동]
    ax.barh(y, sub.z_유동, color=colors, height=0.6)
    ax.axvline(-1, color=ALERT_STRONG, ls="--", lw=1.6)
    ax.text(-1, -0.9, "공급부족 판정선", color=ALERT_STRONG, fontsize=11, ha="center")
    ax.set_yticks(y, [f"{r.sgg_nm} {r.admi_nm}\n비아파트 {r.non_apt_households:,.0f}호"
                      for _, r in sub.iterrows()], fontsize=11)
    ax.invert_yaxis()
    for i, (_, r) in enumerate(sub.iterrows()):
        # 막대가 0에서 왼쪽으로 뻗으므로 라벨은 왼쪽 끝의 '안쪽'에 둔다
        ax.text(r.z_유동 + 0.05, i, f"{r.z_유동:.2f}", va="center", ha="left",
                fontsize=11, fontweight="bold", color="white")
    ax.set_xlabel("생활인구 기준 표준화 잔차")
    ax.grid(axis="x", alpha=0.25)
    save(fig, "06_false_positive")


# ─────────────────────────────────────────────────────────────
# 14번 슬라이드 — 확충 우선순위 (자치구)
# ─────────────────────────────────────────────────────────────
def fig_priority() -> None:
    """자치구별 실수요 100가구당 공영주차면. 아래쪽이 확충 우선."""
    s = load("sgg_summary.csv") if (DATA_PROCESSED / "sgg_summary.csv").exists() else None
    s = pd.read_csv(DATA_PROCESSED / "sgg_summary.csv")
    s = s.sort_values("실수요100가구당")
    med = s.실수요100가구당.median()

    fig, ax = plt.subplots(figsize=(11.5, 5.0))
    colors = [ALERT if v < med else ACCENT_LIGHT for v in s.실수요100가구당]
    y = np.arange(len(s))
    ax.barh(y, s.실수요100가구당, color=colors, height=0.7)
    ax.axvline(med, color=INK, ls="--", lw=1.4)
    ax.text(med, len(s) + 0.2, f"서울 중앙값 {med:.1f}", fontsize=11, ha="center")
    ax.set_yticks(y, s.자치구, fontsize=10)
    ax.invert_yaxis()
    for i, v in enumerate(s.실수요100가구당):
        ax.text(v + 0.15, i, f"{v:.1f}", va="center", fontsize=9.5)
    ax.set_xlabel("비아파트 100가구당 공영주차면")
    ax.grid(axis="x", alpha=0.25)
    save(fig, "07_priority")


# ─────────────────────────────────────────────────────────────
# EDA 슬라이드 — 변수 간 상관 히트맵
# ─────────────────────────────────────────────────────────────
def fig_eda_corr() -> None:
    """EDA의 대표 산출물. 분석용(explore.py)은 10변수 정사각형이라 슬라이드에 크게 안 들어간다.

    핵심 6변수로 줄이고 값 글자를 키워, '천명당주차면 행이 전부 0 근처'라는
    한 가지만 읽히게 한다. 이것이 뒤에 나오는 가설 1·3 기각의 근거다.
    """
    panel = load("panel.csv")
    d = panel[(panel.weekday == "토") & (panel.timeslot == "오후") & panel.has_parking]
    cols = {"living_pop": "생활인구", "store_food": "음식점수", "facility_cnt": "집객시설수",
            "resident_pop": "상주인구", "worker_pop": "직장인구", "slots_per_1k": "천명당주차면"}
    sub = d[list(cols)].rename(columns=cols).dropna()
    r = sub.corr()

    fig, ax = plt.subplots(figsize=(9.0, 5.1))
    im = ax.imshow(r, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(r)), r.columns, rotation=30, ha="right", fontsize=11)
    ax.set_yticks(range(len(r)), r.index, fontsize=11)
    for i in range(len(r)):
        for j in range(len(r)):
            v = r.iloc[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=10.5,
                    fontweight="bold" if i != j and abs(v) < 0.2 else "normal",
                    color="white" if abs(v) > 0.55 else INK)
    # 결론이 걸린 줄을 테두리로 짚어준다
    ax.add_patch(plt.Rectangle((-0.5, len(r) - 1.5), len(r), 1, fill=False,
                               edgecolor=ALERT, lw=2.5))
    fig.colorbar(im, ax=ax, shrink=0.85)
    save(fig, "08_eda_corr")


def main() -> None:
    fig_eda_corr()
    fig_core_result()
    fig_hypothesis_13()
    fig_cluster_pattern()
    fig_timeslot_effect()
    fig_recommend()
    fig_false_positive()
    fig_priority()
    logger.info(f"발표용 그림 7종 완료 -> {OUT}")


if __name__ == "__main__":
    main()
