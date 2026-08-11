"""공간 분포 지도 -> reports/figures/map_*.png

왜 필요한가
----------
지금까지의 산출물은 순위표와 산점도뿐이라 **어디에 몰려 있는지**가 보이지 않는다.
"관악·성북·중랑에 확충 후보가 몰려 있다" 같은 공간 패턴은 지도라야 한 눈에 전달된다.
보고서·발표에서 가장 먼저 보게 될 그림이다.

좌표계 주의
---------
SGIS 경계는 헤더에 CRS84(경위도)라고 선언하지만 실제로는 UTM-K(EPSG:5179) 미터 좌표를 준다.
이미 fetch_dong_boundary.py에서 EPSG:4326으로 재투영해 저장했으므로 여기서는 그대로 쓰되,
좌표값 범위로 한 번 더 확인한다(경도가 1,000을 넘으면 미터 좌표라는 뜻).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.utils.logger import get_logger
from src.utils.plotstyle import use_korean_font
from src.utils.settings import DATA_EXTERNAL, DATA_PROCESSED, ROOT_DIR, get_config

logger = get_logger(__name__)

FIG_DIR = ROOT_DIR / "reports" / "figures"
use_korean_font()

BOUNDARY = DATA_EXTERNAL / "dong_boundary.geojson"


def load_geo() -> gpd.GeoDataFrame:
    if not BOUNDARY.exists():
        raise FileNotFoundError(f"경계 파일이 없습니다: {BOUNDARY}")
    g = gpd.read_file(BOUNDARY)
    max_x = g.total_bounds[2]
    if max_x > 1000:                                  # 경도가 1,000을 넘을 수 없다
        logger.warning(f"미터 좌표 감지 (maxx={max_x:,.0f}) — EPSG:5179 → 4326 재투영")
        g = g.set_crs("EPSG:5179", allow_override=True).to_crs("EPSG:4326")
    logger.info(f"경계 {len(g)}개 폴리곤 / 컬럼 {list(g.columns)[:6]}")
    return g


def attach(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """경계에 분석 결과를 붙인다. 경계는 SGIS 코드(adm_cd) 체계."""
    cfg = get_config()["panel"]["regression_baseline"]
    panel = pd.read_csv(DATA_PROCESSED / "panel.csv", dtype={"adm_cd": str, "admi_cd": str})
    base = panel[(panel.weekday == cfg["weekday"]) & (panel.timeslot == cfg["timeslot"])]

    keep = ["adm_cd", "admi_cd", "sgg_nm", "admi_nm", "slots_per_1k",
            "non_apt_households", "apt_ratio", "parking_slots", "has_parking"]
    d = base[keep].copy()

    for name, cols in [("dong_real_demand.csv", ["admi_cd", "확충필요성", "판정_정주", "z_정주"]),
                       ("dong_suitability.csv", ["admi_cd", "나들이적합도"])]:
        path = DATA_PROCESSED / name
        if path.exists():
            d = d.merge(pd.read_csv(path, dtype={"adm_cd": str, "admi_cd": str})[cols],
                        on="admi_cd", how="left")
        else:
            logger.warning(f"{name} 없음 — 관련 지도를 건너뜁니다")

    key = "adm_cd" if "adm_cd" in g.columns else g.columns[0]
    out = g.merge(d, left_on=key, right_on="adm_cd", how="left")
    logger.info(f"경계 결합 {out.admi_nm.notna().sum()}/{len(out)}개")
    return out


def _base(ax, g):
    g.plot(ax=ax, color="#F2F2F2", edgecolor="white", linewidth=0.3)
    ax.set_axis_off()


def draw(g: gpd.GeoDataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(19, 7))

    # ① 나들이 적합도 (주 사용자)
    ax = axes[0]
    _base(ax, g)
    sub = g[g.나들이적합도.notna()]
    sub.plot(ax=ax, column="나들이적합도", cmap="RdYlGn", legend=True,
             edgecolor="white", linewidth=0.3,
             legend_kwds={"shrink": 0.55, "pad": 0.01, "label": "나들이 적합도"})
    for _, r in sub.nlargest(6, "나들이적합도").iterrows():
        c = r.geometry.representative_point()
        ax.annotate(r.admi_nm, (c.x, c.y), fontsize=7.5, ha="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
    ax.set_title("나들이 적합도 — 놀거리와 주차를 함께 갖춘 동네", fontsize=12)

    # ② 실수요 대비 공영주차 부족 (부 사용자)
    ax = axes[1]
    _base(ax, g)
    sub = g[g.z_정주.notna()]
    sub.plot(ax=ax, column="z_정주", cmap="RdYlBu", legend=True,
             edgecolor="white", linewidth=0.3, vmin=-3, vmax=3,
             legend_kwds={"shrink": 0.55, "pad": 0.01, "label": "정주수요 기준 잔차"})
    cand = g[g.판정_정주 == "공급부족"]
    cand.plot(ax=ax, facecolor="none", edgecolor="#7A0C0C", linewidth=1.1)
    for _, r in cand.nsmallest(6, "z_정주").iterrows():
        c = r.geometry.representative_point()
        ax.annotate(r.admi_nm, (c.x, c.y), fontsize=7.5, ha="center", color="#7A0C0C",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
    ax.set_title(f"확충 후보 {len(cand)}개 동 (굵은 테두리) — 실수요 기준", fontsize=12)

    # ③ 공급 상태 구분 (0면 / 확충 불필요 / 후보)
    ax = axes[2]
    _base(ax, g)
    layers = [
        (g[g.has_parking == False], "#7A0C0C", "공영주차 0면"),
        (g[g.확충필요성 == "불필요"], "#C7C7C7", "확충 불필요(아파트 밀집)"),
        (g[g.판정_정주 == "공급부족"], "#D62728", "확충 후보"),
        (g[(g.판정_정주 == "보통")], "#4C78A8", "보통"),
    ]
    for sub, color, label in layers:
        if len(sub):
            sub.plot(ax=ax, color=color, edgecolor="white", linewidth=0.3, label=f"{label} ({len(sub)})")
    handles = [plt.Rectangle((0, 0), 1, 1, fc=c) for _, c, _ in layers]
    ax.legend(handles, [f"{l} ({len(s)})" for s, _, l in layers], fontsize=9, loc="lower left")
    ax.set_title("공영주차 공급 상태", fontsize=12)

    fig.tight_layout(w_pad=3)
    fig.savefig(FIG_DIR / "map_overview.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("저장: map_overview.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    g = attach(load_geo())
    draw(g)

    print("\n=== 확충 후보의 공간 분포 (자치구별) ===")
    cand = g[g.판정_정주 == "공급부족"]
    vc = cand.sgg_nm.value_counts()
    for k, v in vc.items():
        print(f"  {k:6} {v}개 — {', '.join(cand[cand.sgg_nm == k].nsmallest(4, 'z_정주').admi_nm)}")
    print(f"\n  총 {len(cand)}개 동 / {vc.nunique() and len(vc)}개 자치구에 분포")


if __name__ == "__main__":
    main()
