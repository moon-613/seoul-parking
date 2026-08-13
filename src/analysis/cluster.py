"""가설 2 — 동네 유형 분류와 유형별 주차 여유 패턴 -> data/processed/dong_cluster.csv

검증하는 것
----------
행정동이 상주·직장인구 구성으로 유형이 나뉘고,
**유형에 따라 주차가 여유로운 요일·시간대가 서로 다른가.**

뒤쪽 절반이 이 서비스에서 쓰이는 부분이다.
유형이 나뉜다는 사실 자체는 이용자에게 줄 것이 없지만,
"업무지구는 주말에 비고 주거지는 주말에 찬다"는 **가야 할 때가 달라진다**는 뜻이다.

군집 번호를 그대로 쓰지 않는 이유
------------------------------
K-means의 군집 번호는 실행할 때마다 순서가 바뀐다. 보고서에 "유형 3"이라고 쓰면
다음 실행에서 다른 동네 집합을 가리키게 된다.
그래서 군집의 평균 특성(주거지수·직장인구·음식점)으로 **이름을 붙여 고정**한다.

왜 절대량이 아니라 비율로 묶는가
----------------------------
생활인구·음식점·집객시설·상주·직장인구를 그대로 넣으면 이들이 서로 0.75~0.93으로
상관되어 PC1이 사실상 **동네 크기 축**이 된다(로딩 0.49/0.49/0.49).
그러면 '성격이 다른 동네'가 아니라 '큰 동네 vs 작은 동네'로 갈린다.
가설 2가 말하는 것은 상주·직장인구의 **비율**이므로, 규모를 나눠 없앤 지표를 쓴다.
  주거지수 = 상주 / (상주 + 직장)      1에 가까우면 주거지, 0에 가까우면 업무지구
  음식점·집객시설은 1,000명당 밀도로 환산

주차 여유가 시간에 따라 변하는 이유
--------------------------------
주차면수는 시간에 따라 변하지 않는다. `slots_per_1k`가 흔들리는 것은 전적으로
분모인 생활인구가 바뀌기 때문이다. 즉 여기서 보는 것은 '주차장이 늘고 준다'가 아니라
**'같은 주차장을 두고 경쟁하는 사람 수가 달라진다'** 이다.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.utils.logger import get_logger
from src.utils.plotstyle import use_korean_font
from src.utils.settings import DATA_PROCESSED, ROOT_DIR, get_config
from src.utils.timeslot import recommend_timeslots, timeslot_order

logger = get_logger(__name__)

FIG_DIR = ROOT_DIR / "reports" / "figures"
use_korean_font()

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

# 군집 입력 (모두 규모를 나눠 없앤 비율·밀도 지표)
FEATURES = {
    "home_index": "주거지수",
    "young_ratio": "20~30대비중",
    "slots_per_1k": "천명당주차면",
    "food_per_1k": "천명당음식점",
    "fac_per_1k": "천명당집객시설",
}

# 규모 지표는 군집에 넣지 않고 해석·출력용으로만 쓴다
SCALE_VARS = ["living_pop", "store_food", "facility_cnt", "resident_pop", "worker_pop"]

K_RANGE = range(2, 8)


def load_panel() -> pd.DataFrame:
    path = DATA_PROCESSED / "panel.csv"
    if not path.exists():
        raise FileNotFoundError("패널이 없습니다. build_panel.py를 먼저 실행하세요.")
    return pd.read_csv(path, dtype={"adm_cd": str, "admi_cd": str})


def baseline_slice(panel: pd.DataFrame) -> pd.DataFrame:
    """군집 기준 시점 단면 + 비율 지표 산출 (회귀와 같은 시점을 써서 결과를 맞춘다)."""
    cfg = get_config()["panel"]["regression_baseline"]
    d = panel[
        (panel.weekday == cfg["weekday"])
        & (panel.timeslot == cfg["timeslot"])
        & panel.has_parking
    ].dropna(subset=SCALE_VARS + ["young_ratio", "slots_per_1k"]).copy()

    d["home_index"] = d.resident_pop / (d.resident_pop + d.worker_pop)
    d["food_per_1k"] = d.store_food / (d.living_pop / 1000)
    d["fac_per_1k"] = d.facility_cnt / (d.living_pop / 1000)

    logger.info(f"군집 기준 {cfg['weekday']}요일 {cfg['timeslot']} / 행정동 {len(d)}개")
    return d


def choose_k(z: np.ndarray) -> tuple[int, dict[int, float]]:
    sil = {}
    for k in K_RANGE:
        lab = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(z)
        sil[k] = silhouette_score(z, lab)
    best = max(sil, key=sil.get)
    logger.info("실루엣 계수: " + " ".join(f"k={k}:{v:.3f}" for k, v in sil.items()))
    logger.info(f"선택 k={best}")
    return best, sil


def name_clusters(d: pd.DataFrame) -> dict[int, str]:
    """군집에 특성 기반 이름을 붙인다.

    K-means 군집 번호는 실행 순서에 따라 바뀌므로 번호를 그대로 쓰면
    보고서의 '유형 3'이 다음 실행에서 다른 동네를 가리키게 된다.
    주거지수가 낮은 군집부터 업무형 -> (혼합형) -> 주거형 순으로 고정한다.
    음식점 밀도가 전체 중앙값을 넘는 비주거 군집은 '상권형'으로 구분한다.
    """
    prof = d.groupby("cluster").agg(
        home=("home_index", "mean"), food=("food_per_1k", "mean")
    ).sort_values("home")
    med_food = d["food_per_1k"].median()

    order = list(prof.index)
    names: dict[int, str] = {}
    for rank, cid in enumerate(order):
        if rank == 0:
            names[cid] = "상권형" if prof.loc[cid, "food"] >= med_food else "업무형"
        elif rank == len(order) - 1:
            names[cid] = "주거형"
        else:
            names[cid] = "혼합형"

    # 이름이 겹치면 주거지수 순으로 번호를 붙여 구분한다
    dup = {n for n in names.values() if list(names.values()).count(n) > 1}
    seen: dict[str, int] = {}
    for cid in order:
        if names[cid] in dup:
            seen[names[cid]] = seen.get(names[cid], 0) + 1
            names[cid] = f"{names[cid]}{seen[names[cid]]}"
    return names


def timeslot_profile(panel: pd.DataFrame, labels: pd.Series) -> pd.DataFrame:
    """유형별 요일×시간대 주차 여유 프로파일 (유형 내 평균=100 지수)."""
    d = panel[panel.has_parking].merge(
        labels.rename("유형"), left_on="admi_cd", right_index=True, how="inner"
    )
    piv = d.pivot_table(index="유형", columns=["weekday", "timeslot"],
                        values="slots_per_1k", observed=True)
    piv = piv.reindex(columns=pd.MultiIndex.from_product(
        [WEEKDAYS, timeslot_order()], names=["weekday", "timeslot"]))
    return piv.div(piv.mean(axis=1), axis=0) * 100


def plot(d: pd.DataFrame, pca: PCA, sil: dict, prof_idx: pd.DataFrame) -> None:
    # 아래 히트맵은 유형 수만큼만 높이를 주어 과하게 늘어나지 않게 한다
    n_type = len(prof_idx)
    fig = plt.figure(figsize=(19, 5.5 + 0.55 * n_type))
    gs = fig.add_gridspec(2, 3, height_ratios=[5, 0.75 * n_type], hspace=0.45, wspace=0.28)

    # ① PCA 산점도
    ax = fig.add_subplot(gs[0, 0])
    for nm, sub in d.groupby("유형"):
        ax.scatter(sub.PC1, sub.PC2, s=20, alpha=0.75, label=nm)
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.0f}%)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.0f}%)")
    ax.set_title(f"행정동 유형 분류 (n={len(d)}, k={d.유형.nunique()})")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # ② 실루엣 계수
    ax = fig.add_subplot(gs[0, 1])
    ax.plot(list(sil), list(sil.values()), "o-", color="#4C78A8")
    best = max(sil, key=sil.get)
    ax.axvline(best, color="#D62728", ls="--", lw=1.2, label=f"선택 k={best}")
    ax.set_xlabel("군집 수 k")
    ax.set_ylabel("실루엣 계수")
    ax.set_title("군집 수 결정")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # ③ 유형별 특성 레이더 — 각 축은 유형 간 상대 위치(0~100), 절대값이 아니다
    ax = fig.add_subplot(gs[0, 2], projection="polar")
    prof = d.groupby("유형")[list(FEATURES)].mean()
    prof.columns = [FEATURES[c] for c in prof.columns]
    rng = (prof.max() - prof.min()).replace(0, 1)
    norm = (prof - prof.min()) / rng * 100

    labels = list(norm.columns)
    ang = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    ang += ang[:1]
    for nm, row in norm.iterrows():
        vals = row.tolist() + [row.iloc[0]]
        ax.plot(ang, vals, lw=1.8, label=nm)
        ax.fill(ang, vals, alpha=0.18)
    ax.set_xticks(ang[:-1], labels, fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 50, 100], ["0", "50", "100"], fontsize=7)
    ax.set_title("유형별 특성 비교 (유형 간 상대 위치)", pad=18)
    ax.legend(fontsize=8, loc="upper right", bbox_to_anchor=(1.18, 1.15))

    # ④ 유형별 요일×시간대 프로파일 (가설 2의 핵심)
    ax = fig.add_subplot(gs[1, :])
    im = ax.imshow(prof_idx.values, cmap="RdYlBu", aspect="auto")
    ax.set_yticks(range(len(prof_idx)), prof_idx.index)
    xlab = [f"{w}\n{t}" for w, t in prof_idx.columns]
    ax.set_xticks(range(len(xlab)), xlab, fontsize=6.5)
    for i in range(prof_idx.shape[0]):
        for j in range(prof_idx.shape[1]):
            ax.text(j, i, f"{prof_idx.iloc[i, j]:.0f}", ha="center", va="center", fontsize=5.5)
    ax.set_title("유형별 주차 여유 프로파일 — 유형 내 평균=100 (높을수록 그 시점에 여유)", pad=10)
    fig.colorbar(im, ax=ax, shrink=0.85, pad=0.01)

    fig.savefig(FIG_DIR / "cluster.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("저장: cluster.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    panel = load_panel()
    d = baseline_slice(panel)

    # 비율·밀도 지표라 로그 변환 없이 Z-score만 적용한다
    z = StandardScaler().fit_transform(d[list(FEATURES)].to_numpy())

    k, sil = choose_k(z)
    d["cluster"] = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(z)

    pca = PCA(n_components=2, random_state=0)
    d[["PC1", "PC2"]] = pca.fit_transform(z)

    d["유형"] = d.cluster.map(name_clusters(d))
    logger.info("유형별 동 수: " + " / ".join(
        f"{k_}: {v}" for k_, v in d.유형.value_counts().items()))

    labels = d.set_index("admi_cd")["유형"]
    prof_idx = timeslot_profile(panel, labels)
    plot(d, pca, sil, prof_idx)

    cols = ["adm_cd", "admi_cd", "sgg_nm", "admi_nm", "유형",
            *FEATURES, *SCALE_VARS, "PC1", "PC2"]
    dest = DATA_PROCESSED / "dong_cluster.csv"
    d[cols].sort_values(["유형", "admi_nm"]).to_csv(dest, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {dest} ({len(d)}행)")

    # ── 보고서에 옮길 수치 ────────────────────────────────────
    prof = d.groupby("유형").agg(
        동수=("admi_cd", "size"), 주거지수=("home_index", "mean"),
        천명당음식점=("food_per_1k", "mean"), 생활인구=("living_pop", "mean"),
        음식점=("store_food", "mean"), 천명당주차면=("slots_per_1k", "mean"),
    ).sort_values("주거지수")
    print("\n=== 유형별 특성 ===")
    print(prof.to_string(float_format="%.2f"))

    print("\n=== 유형별 대표 행정동 (생활인구 상위 4) ===")
    for nm, sub in d.groupby("유형"):
        print(f"  {nm:8} {', '.join(sub.nlargest(4, 'living_pop').admi_nm)}")

    # 히트맵에는 아침도 그대로 두어 패턴을 보여 주되, '가장 여유로운 때'로 내미는
    # 것은 실행 가능한 시간대 중에서만 고른다. 아침을 후보에 넣으면 상권형의 최적이
    # '일·아침'으로 잡히는데, 사람이 없어서 빈 것이라 나들이 추천이 되지 않는다.
    pick = prof_idx[[c for c in prof_idx.columns if c[1] in set(recommend_timeslots())]]
    print("\n=== 유형별 가장 여유로운 때 / 가장 빠듯한 때 (유형 내 평균=100, 아침 제외) ===")
    for nm, row in pick.iterrows():
        b, w = row.idxmax(), row.idxmin()
        print(f"  {nm:8} 여유 {b[0]}·{b[1]} ({row.max():.0f})"
              f"   빠듯 {w[0]}·{w[1]} ({row.min():.0f})"
              f"   격차 {row.max()/row.min()-1:+.1%}")

    wk = prof_idx.T.groupby(level="weekday").mean().T[WEEKDAYS]
    print("\n=== 유형별 평일/주말 대비 ===")
    cmp = pd.DataFrame({
        "평일": wk[["월", "화", "수", "목", "금"]].mean(axis=1),
        "주말": wk[["토", "일"]].mean(axis=1),
    })
    cmp["주말/평일"] = cmp.주말 / cmp.평일
    print(cmp.to_string(float_format="%.2f"))


if __name__ == "__main__":
    main()
