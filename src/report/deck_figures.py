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
from src.utils.timeslot import recommend_timeslots

logger = get_logger(__name__)

OUT = ROOT_DIR / "reports" / "figures" / "deck"
# --transparent 로 켜면 배경을 투명하게 저장한다.
# 슬라이드 배경색이 흰색이 아니거나 직접 PPT를 만들 때 그림이 흰 사각형으로 얹히지 않는다.
TRANSPARENT = False
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
    fig.savefig(OUT / f"{name}.png", dpi=DPI, bbox_inches="tight",
                facecolor="none" if TRANSPARENT else "white",
                transparent=TRANSPARENT)
    plt.close(fig)
    logger.info(f"저장: {OUT.name}/{name}.png")


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

    # 추천 대상 시간대만 그린다. 아침(06-10)은 패널에 있지만 여기서 빠진다 —
    # 사람이 없어서 빈 시간이라 '유형별로 언제가 여유로운가'의 답이 될 수 없다.
    # 예전에는 5개를 그대로 박아 뒀는데, config에서 구간을 바꾸면 이 그림만
    # 조용히 어긋나므로 아래 눈금·구분선까지 모두 이 목록에서 끌어 쓴다.
    order = recommend_timeslots()
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
    n = len(order)   # 요일 한 칸에 들어가는 시간대 수
    ax.set_xticks([i * n + n // 2 for i in range(7)], ["월", "화", "수", "목", "금", "토", "일"])
    for i in range(1, 7):
        ax.axvline(i * n - 0.5, color="#dddcd6", lw=1)
    # 주말 구간 표시. 예전에는 배경을 회색으로 칠했는데, 투명 배경으로 저장하면
    # 거기만 불투명한 사각형으로 남는다. 경계선과 라벨로 대신한다
    weekend_x = 5 * n - 0.5   # 평일 5일이 끝나는 지점
    ax.axvline(weekend_x, color=MUTED, lw=1.6)
    ax.text((weekend_x + len(prof) - 0.5) / 2, ax.get_ylim()[1] * 0.995, "주말",
            ha="center", va="top", fontsize=12, color=MUTED, fontweight="bold")
    ax.set_ylabel("주차 여유 지수\n(유형 내 평균 = 100)")
    ax.set_xlabel("요일 안에서는 " + " → ".join(order) + " 순", fontsize=11, color=MUTED)
    ax.legend(fontsize=11, loc="upper left", frameon=False)
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
    ax.legend(fontsize=11, loc="upper left", frameon=False)
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


# ─────────────────────────────────────────────────────────────
# EDA 슬라이드 — 무엇을 1번째로 보고 5번째로 봤는가 (순서 + 히트맵)
# ─────────────────────────────────────────────────────────────
# 모의 발표에서 "다섯 단계를 말하는데 화면엔 히트맵만 있어 눈 둘 곳이 없다"는
# 지적을 받았다. 히트맵은 다섯 번째 단계일 뿐인데 슬라이드가 그것만 보여준다.
# 그래서 왼쪽에 다섯 단계를, 오른쪽에 그 마지막 단계의 산출물을 나란히 둔다.
# 발표자는 왼쪽을 위에서 아래로 짚어 내려오다가 ⑤에서 오른쪽으로 넘어간다.
EDA_STEPS = [
    ("결측 · 이상치", "서교동 117,158명은 오류가 아니라 실제 번화가",
     "이상치를 지우지 않고 Z-score 표준화"),
    ("날짜축 56일", "평일인데 인구가 떨어진 2일 = 공휴일",
     "공휴일 제외 · 변동계수 2.01% → 0.19%"),
    ("요일 × 시간대", "을지로동 일요일 06시 30 / 11시 86 / 13시 100",
     "한 구간 안 3배 차이 → 시간대 6구간 재설계"),
    ("자치구 분포", "천명당 주차면 중앙값 금천 19.0 ↔ 노원 2.8",
     "0면 동 109개 발견 → API 보충으로 66개"),
    ("변수 간 상관", "주차만 아무 지표와도 붙지 않는다",
     "가설 1 기각의 근거 →"),
]


def fig_eda_steps() -> None:
    """EDA 슬라이드 교체용. 왼쪽 다섯 단계 + 오른쪽 상관 히트맵 한 장."""
    panel = load("panel.csv")
    d = panel[(panel.weekday == "토") & (panel.timeslot == "오후") & panel.has_parking]
    cols = {"living_pop": "생활인구", "store_food": "음식점수", "facility_cnt": "집객시설수",
            "resident_pop": "상주인구", "worker_pop": "직장인구", "slots_per_1k": "천명당주차면"}
    sub = d[list(cols)].rename(columns=cols).dropna()
    r = sub.corr()

    fig, (ax, hx) = plt.subplots(
        1, 2, figsize=(13.0, 5.0), gridspec_kw={"width_ratios": [1.42, 1], "wspace": 0.06})

    # ── 왼쪽: 다섯 단계 ──────────────────────────────────
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    top, row_h = 95.0, 18.4
    for i, (what, found, acted) in enumerate(EDA_STEPS):
        y = top - i * row_h
        last = i == len(EDA_STEPS) - 1
        tone = ALERT if last else ACCENT
        # 번호 배지
        ax.text(3.2, y - 5.2, f"{i + 1}", ha="center", va="center",
                fontsize=12.5, fontweight="bold", color="white",
                bbox=dict(boxstyle="circle,pad=0.42", fc=tone, ec="none"))
        ax.text(10, y - 1.4, what, fontsize=13.5, fontweight="bold",
                color=INK, va="center")
        ax.text(10, y - 7.4, found, fontsize=10.8, color=MUTED, va="center")
        ax.text(10, y - 13.0, acted, fontsize=11.2, fontweight="bold",
                color=tone, va="center")
        if not last:  # 단계 사이 구분선
            ax.plot([2.4, 99], [y - 16.6, y - 16.6], color=NEUTRAL, lw=0.8, alpha=0.65)

    # ── 오른쪽: 다섯 번째 단계의 산출물 ───────────────────
    im = hx.imshow(r, cmap="RdBu_r", vmin=-1, vmax=1)
    hx.set_xticks(range(len(r)), r.columns, rotation=35, ha="right", fontsize=9)
    hx.set_yticks(range(len(r)), r.index, fontsize=9)
    for i in range(len(r)):
        for j in range(len(r)):
            v = r.iloc[i, j]
            hx.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8.6,
                    fontweight="bold" if i != j and abs(v) < 0.2 else "normal",
                    color="white" if abs(v) > 0.55 else INK)
    # 결론이 걸린 줄
    hx.add_patch(plt.Rectangle((-0.5, len(r) - 1.5), len(r), 1, fill=False,
                               edgecolor=ALERT, lw=2.5))
    hx.set_title("⑤ 변수 간 피어슨 상관  ·  토 · 오후 n=351",
                 fontsize=10.5, color=MUTED, pad=8)
    fig.colorbar(im, ax=hx, shrink=0.72, pad=0.02).ax.tick_params(labelsize=8)
    save(fig, "10_eda_steps")


# ─────────────────────────────────────────────────────────────
# 데이터 슬라이드 — 7종을 한 표로 접는 과정 (엑셀 시트 모양)
# ─────────────────────────────────────────────────────────────
# 원본 시트에 넣는 표본은 실제 원본 파일에서 그대로 옮긴 값이다.
#   생활인구  data/raw/living_population/20260606.csv (토) · 종로1.2.3.4가동(11110615)
#   주차장    data/raw/parking_standard.csv 상위 행
#   점포      data/external/commercial/점포_행정동.csv 20261 · 종로1.2.3.4가동
#   가구      data/external/census/거처종류별가구_행정동.csv 상위 행
# 원본은 저장소에 없을 수 있어(총조사는 수동 다운로드) 표본만 코드에 적어 둔다.
# 최종 시트는 panel.csv에서 직접 읽으므로 숫자가 어긋날 일이 없다.
SRC_COLOR = {
    "생활인구": "#dceafa", "주차장": "#fbdedd", "상권": "#fdeed3",
    "가구": "#dff0e2", "키": "#ebebe8", "파생": "#e6e0f7",
}


def _sheet(ax, x, y, widths, header, rows, hcolors=None, rowh=3.0, fs=8.6):
    """엑셀 시트 한 덩어리. (x, y)는 헤더 행의 좌상단, y는 아래로 증가."""
    xs = np.concatenate([[x], x + np.cumsum(widths)])
    for j, (w, h) in enumerate(zip(widths, header)):
        ax.add_patch(plt.Rectangle((xs[j], y), w, rowh,
                                   facecolor=(hcolors[j] if hcolors else "#ebebe8"),
                                   edgecolor="#b0b0ac", lw=0.8))
        ax.text(xs[j] + w / 2, y + rowh / 2, h, ha="center", va="center",
                fontsize=fs, fontweight="bold", color=INK)
    for i, row in enumerate(rows):
        yy = y + rowh * (i + 1)
        for j, (w, v) in enumerate(zip(widths, row)):
            ax.add_patch(plt.Rectangle((xs[j], yy), w, rowh, facecolor="white",
                                       edgecolor="#d5d5d1", lw=0.7))
            # 숫자는 오른쪽, 글자는 왼쪽 — 엑셀 기본 정렬
            num = v.replace(",", "").replace(".", "").replace("%", "").isdigit()
            ax.text(xs[j] + (w - 0.7 if num else 0.7), yy + rowh / 2, v,
                    ha="right" if num else "left", va="center", fontsize=fs, color="#1b1b1b")
    return y + rowh * (len(rows) + 1)


def fig_panel_merge() -> None:
    """슬라이드 10 — '엑셀로 했다면' 을 그대로 보인 그림.

    파일마다 한 행의 뜻이 다르다는 것이 이 슬라이드의 전부다.
    전부 '행정동 1행'으로 접은 뒤에야 옆으로 붙일 수 있다.
    """
    p = load("panel.csv")
    pick = [("종로1.2.3.4가동", "토", "오후"), ("종로1.2.3.4가동", "화", "오전"),
            ("신촌동", "토", "오후"), ("논현2동", "토", "오후")]
    fin = [p[(p.admi_nm == nm) & (p.weekday == wd) & (p.timeslot == ts)].iloc[0]
           for nm, wd, ts in pick]

    fig, ax = plt.subplots(figsize=(13.2, 5.8))
    ax.set_xlim(0, 100)
    ax.set_ylim(78, 0)
    ax.axis("off")

    W, GAP = 22.9, 2.7
    srcs = [
        ("생활인구.csv  (56개 파일)", "생활인구", [0.20, 0.44, 0.36],
         ["시간", "행정동코드", "생활인구"],
         [["13", "11110615", "80,625.7"], ["14", "11110615", "86,048.5"],
          ["15", "11110615", "89,132.4"]],
         "한 행 = 동 × 시간 × 날짜\n569,856행 (424동×24시간×56일)",
         "56일 평균 → 24시간을 6구간으로\n(피벗테이블)"),
        ("주차장_표준데이터.csv", "주차장", [0.40, 0.40, 0.20],
         ["주차장명", "주소", "면수"],
         [["덕원주차장", "동대문구 장한로6길", "77"],
          ["정릉천복개공영", "동대문구 정릉천동로", "143"],
          ["신원동제1공영", "관악구 남부순환로", "23"]],
         "한 행 = 주차장 1곳\n856개소 · 행정동 칸 없음",
         "주소 → 행정동 (지오코딩)\n동별 면수 SUM"),
        ("점포_행정동.csv", "상권", [0.42, 0.36, 0.22],
         ["행정동", "업종", "점포수"],
         [["종로1.2.3.4가동", "한식음식점", "1,112"],
          ["종로1.2.3.4가동", "커피-음료", "475"],
          ["종로1.2.3.4가동", "조명용품", "798"]],
         "한 행 = 동 × 업종\n176,531행 (업종 100종)",
         "음식점 8·카페 2 업종만 필터\n→ 동별 SUM"),
        ("거처종류별가구.csv", "가구", [0.40, 0.32, 0.28],
         ["행정동", "일반가구", "아파트"],
         [["사직동", "4,004", "1,511"], ["삼청동", "906", "X"],
          ["부암동", "3,715", "121"]],
         "한 행 = 행정동 1개\n427행 · 비공개는 X",
         "이미 동 단위 → 그대로\n(X는 결측 처리)"),
    ]

    for i, (title, key, wr, head, rows, note, todo) in enumerate(srcs):
        x = i * (W + GAP)
        ax.text(x + 0.3, 3.4, title, fontsize=10.5, fontweight="bold", color=INK, va="bottom")
        widths = np.array(wr) * W
        bot = _sheet(ax, x, 4.4, widths, head, rows, hcolors=[SRC_COLOR[key]] * len(head))
        ax.text(x + 0.3, bot + 1.6, "⋮", fontsize=11, color=MUTED)
        ax.text(x + 0.3, bot + 3.4, note, fontsize=9.5, color=MUTED, va="top", linespacing=1.5)
        # 접는 방법 + 화살표
        ax.text(x + W / 2, 26.6, todo, fontsize=9.6, color=ACCENT, ha="center", va="top",
                linespacing=1.5, fontweight="bold")
        ax.annotate("", xy=(x + W / 2, 38.8), xytext=(x + W / 2, 33.4),
                    arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=2))

    # ── 접은 뒤 옆으로 붙이는 단계
    ax.add_patch(plt.Rectangle((0, 39.5), 98, 5.6, facecolor="#f4f7fb",
                               edgecolor=ACCENT, lw=1.2))
    ax.text(1.4, 42.3, "행정동 코드로 VLOOKUP", fontsize=11.5, fontweight="bold",
            color=ACCENT, va="center")
    ax.text(23.5, 42.3, "코드 체계가 달라 424동 중 32동(7.5%)만 매칭됐다 "
                        "→ 행정동 코드 변환표를 하나 더 붙여 100%", fontsize=10.5,
            color=ALERT_STRONG, va="center")

    # ── 최종 시트
    ax.text(0.3, 49.5, "panel.csv  —  17,808행 × 31열  (424동 × 7요일 × 6시간대)",
            fontsize=12, fontweight="bold", color=INK, va="bottom")
    cols = [("행정동", "키", 0.135), ("요일", "키", 0.048), ("시간대", "키", 0.058),
            ("생활인구", "생활인구", 0.088), ("주차면", "주차장", 0.068),
            ("음식점", "상권", 0.068), ("카페", "상권", 0.058),
            ("일반가구", "가구", 0.078), ("아파트", "가구", 0.068),
            ("천명당\n주차면", "파생", 0.088), ("비아파트\n100가구당", "파생", 0.11)]
    widths = np.array([c[2] for c in cols]) * 98
    rows = []
    for r in fin:
        rows.append([r.admi_nm, r.weekday, r.timeslot, f"{r.living_pop:,.0f}",
                     f"{r.parking_slots:,.0f}", f"{r.store_food:,.0f}", f"{r.store_cafe:,.0f}",
                     f"{r.households:,.0f}", f"{r.apartment:,.0f}",
                     f"{r.slots_per_1k:.2f}", f"{r.slots_per_100_nonapt:.2f}"])
    bot = _sheet(ax, 0, 50.5, widths, [c[0] for c in cols], rows,
                 hcolors=[SRC_COLOR[c[1]] for c in cols], rowh=4.0, fs=9.6)
    ax.text(0.7, bot + 1.8, "⋮", fontsize=12, color=MUTED)

    # 같은 동인데 요일·시간대가 다른 두 행 — 패널 구조를 한눈에 (표 아래에 설명)
    xs = np.concatenate([[0], np.cumsum(widths)])
    ax.add_patch(plt.Rectangle((0, 54.5), widths[:3].sum(), 8.0, fill=False,
                               edgecolor=ACCENT, lw=2))
    ax.annotate("같은 동이어도 요일·시간대가 다르면 생활인구가 바뀌고, 파생변수도 같이 바뀐다\n"
                "(주차면·음식점·가구 수는 그대로)", xy=(widths[:3].sum() / 2, 71.0),
                xytext=(4.0, 73.4), fontsize=10.5, color=ACCENT, va="top",
                linespacing=1.5, arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=1.4))
    # 파생변수 열 — 표 위쪽 오른편에 라벨
    ax.add_patch(plt.Rectangle((xs[9], 50.5), widths[9:].sum(), 20.0, fill=False,
                               edgecolor="#6b4fbb", lw=2))
    ax.text(xs[9] + widths[9:].sum() / 2, 48.6,
            "나눗셈으로 만든 열 = 파생변수", fontsize=10.5, color="#6b4fbb",
            ha="center", va="bottom", fontweight="bold")
    ax.annotate("", xy=(xs[9] + widths[9:].sum() / 2, 50.4),
                xytext=(xs[9] + widths[9:].sum() / 2, 48.4),
                arrowprops=dict(arrowstyle="-|>", color="#6b4fbb", lw=1.4))

    save(fig, "09_panel_merge")


# ─────────────────────────────────────────────────────────────
# 데이터 슬라이드 — 파생변수: 매력도는 어떻게 만들어졌는가
# ─────────────────────────────────────────────────────────────
def fig_derived_vars() -> None:
    """'매력도'를 말로만 설명하면 안 들린다. 만들어지는 과정을 두 장면으로 보인다.

    ① 로딩 — 5개 변수를 넣었더니 축 2개로 갈라졌다. 축 이름은 이 표를 보고 붙였다.
    ② 기하평균 — 한쪽만 높은 동네가 왜 떨어지는지, 실제 동네 3곳으로 보인다.
    """
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    d = load("dong_suitability.csv")
    cols = {"store_food": "음식점 수", "store_cafe": "카페 수", "facility_cnt": "집객시설 수",
            "slots_per_1k": "천명당 주차면", "z_residual": "주차 여유(잔차)"}
    log_vars = ["store_food", "store_cafe", "facility_cnt", "slots_per_1k"]

    X = d[list(cols)].copy()
    for c in log_vars:
        X[c] = np.log1p(X[c])
    pca = PCA(random_state=0).fit(StandardScaler().fit_transform(X))
    comp = pca.components_[:2].copy()
    # suitability.py와 같은 부호 고정 (음식점·천명당주차면 로딩이 양수)
    for pc, anchor in {0: "store_food", 1: "slots_per_1k"}.items():
        if comp[pc, list(cols).index(anchor)] < 0:
            comp[pc] *= -1
    ev = pca.explained_variance_ratio_

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.5),
                             gridspec_kw={"width_ratios": [1, 1.25]})

    # ① 로딩 — 두 축이 갈라진 모습 자체가 근거다
    ax = axes[0]
    L = comp.T
    ax.imshow(L, cmap="RdBu_r", vmin=-0.8, vmax=0.8, aspect="auto")
    ax.set_xticks(range(2), [f"매력도 축\n(정보의 {ev[0]:.0%})", f"주차 여유 축\n(정보의 {ev[1]:.0%})"],
                  fontsize=12, fontweight="bold")
    ax.set_yticks(range(len(cols)), list(cols.values()), fontsize=11.5)
    for i in range(L.shape[0]):
        for j in range(2):
            ax.text(j, i, f"{L[i, j]:+.2f}", ha="center", va="center", fontsize=12,
                    fontweight="bold" if abs(L[i, j]) > 0.5 else "normal",
                    color="white" if abs(L[i, j]) > 0.5 else INK)
    ax.add_patch(plt.Rectangle((-0.5, -0.5), 1, 3, fill=False, edgecolor=ALERT, lw=2.5))
    ax.add_patch(plt.Rectangle((0.5, 2.5), 1, 2, fill=False, edgecolor=ACCENT, lw=2.5))
    ax.tick_params(length=0)
    ax.set_xlabel("놀거리 3종과 주차 2종이 서로 다른 축으로 갈렸다", fontsize=11.5, color=MUTED)

    # ② 기하평균 — 약한 쪽이 병목
    ax = axes[1]
    pick = ["종로1.2.3.4가동", "신촌동", "면목5동"]
    sub = d.set_index("admi_nm").loc[pick]
    y = np.arange(len(pick))[::-1]
    ax.barh(y + 0.19, sub.매력도지수_pct, height=0.34, color="#F58518", label="매력도 백분위")
    ax.barh(y - 0.19, sub.주차여유지수_pct, height=0.34, color=ACCENT, label="주차 여유 백분위")
    for yy, (_, r) in zip(y, sub.iterrows()):
        for off, v in ((0.19, r.매력도지수_pct), (-0.19, r.주차여유지수_pct)):
            ax.text(v + 1.5, yy + off, f"{v:.0f}", va="center", fontsize=11)
        ax.text(118, yy, f"적합도 {r.나들이적합도:.0f}", va="center", ha="right",
                fontsize=13, fontweight="bold",
                color=INK if r.나들이적합도 > 50 else ALERT)
    ax.set_yticks(y, [f"{r.sgg_nm}\n{nm}" for nm, r in sub.iterrows()], fontsize=11.5)
    ax.set_xlim(0, 120)
    ax.set_xticks([0, 50, 100])
    ax.legend(fontsize=11, loc="lower right", frameon=False, ncol=2,
              bbox_to_anchor=(1.0, -0.28))
    ax.grid(axis="x", alpha=0.25)
    ax.set_xlabel("적합도 = 두 백분위의 기하평균 — 한쪽이 낮으면 같이 내려간다",
                  fontsize=11.5, color=MUTED)

    save(fig, "09_derived_vars")


def _cli() -> None:
    """저장 위치와 배경 투명 여부를 인자로 받는다."""
    global OUT, TRANSPARENT
    import argparse
    from pathlib import Path
    ap = argparse.ArgumentParser()
    ap.add_argument("--transparent", action="store_true", help="배경을 투명하게 저장")
    ap.add_argument("--out", help="저장 폴더 (기본 reports/figures/deck)")
    a = ap.parse_args()
    TRANSPARENT = a.transparent
    if a.out:
        OUT = Path(a.out)
    logger.info(f"저장 위치 {OUT} · 배경 {'투명' if TRANSPARENT else '흰색'}")


def main() -> None:
    fig_eda_corr()
    fig_eda_steps()
    fig_core_result()
    fig_hypothesis_13()
    fig_cluster_pattern()
    fig_timeslot_effect()
    fig_recommend()
    fig_false_positive()
    fig_priority()
    fig_panel_merge()
    fig_derived_vars()
    logger.info(f"발표용 그림 11종 완료 -> {OUT}")


if __name__ == "__main__":
    _cli()
    main()
