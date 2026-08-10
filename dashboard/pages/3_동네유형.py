"""동네 유형 페이지 — PCA로 차원을 줄이고 K-means로 행정동을 유형화한다.

군집 수 k는 실루엣 계수로 결정한다(사용자가 직접 지정할 수도 있음).
선택한 요일·시간대의 값으로 다시 계산되므로 조건을 바꾸면 결과도 바뀐다.
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from common import TIMESLOT_LABEL, apply_filters, page_header, require_data, sidebar_filters

st.set_page_config(page_title="동네 유형 | 서울 나들이 주차", page_icon="🧩", layout="wide")

df = require_data()
f = sidebar_filters(df)
d = apply_filters(df, f, apply_gu=False)

page_header(
    "🧩 동네 유형 분류",
    "여러 변수를 한꺼번에 고려해 비슷한 성격의 행정동을 묶습니다. "
    "선택한 요일·시간대 값으로 다시 계산됩니다.",
)

FEATURES = {
    "living_pop": "생활인구",
    "young_ratio": "20~30대비중",
    "slots_per_1k": "천명당주차면",
    "store_food": "음식점수",
    "facility_cnt": "집객시설수",
    "resident_pop": "상주인구",
    "worker_pop": "직장인구",
}

use = d.dropna(subset=list(FEATURES)).copy()
if len(use) < 30:
    st.warning(f"분석 가능한 행정동이 {len(use)}개뿐입니다. 조건을 완화하세요.")
    st.stop()


@st.cache_data
def run_cluster(values: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray, PCA, np.ndarray]:
    """Z-score 표준화 -> PCA -> K-means.

    Min-Max 대신 Z-score를 쓰는 이유: 명동·강남 같은 극단값이 있어
    Min-Max로는 나머지 지역의 분포가 눌린다.
    """
    z = StandardScaler().fit_transform(values)
    pca = PCA(n_components=2, random_state=0)
    coords = pca.fit_transform(z)
    labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(z)
    return coords, labels, pca, z


X = np.log1p(use[list(FEATURES)].clip(lower=0).to_numpy())

# ── 군집 수 결정 ───────────────────────────────────────────────
c1, c2 = st.columns([1, 2])
auto = c1.checkbox("실루엣 계수로 자동 결정", value=True)

zs = StandardScaler().fit_transform(X)
sil = {}
for kk in range(2, 8):
    lab = KMeans(n_clusters=kk, n_init=10, random_state=0).fit_predict(zs)
    sil[kk] = silhouette_score(zs, lab)
best_k = max(sil, key=sil.get)

k = best_k if auto else c1.slider("군집 수 k", 2, 7, best_k)

with c2:
    st.markdown(f"**군집 수별 실루엣 계수** — 최적 k = {best_k}")
    sil_df = pd.DataFrame({"k": list(sil), "실루엣계수": list(sil.values())})
    figs = px.line(sil_df, x="k", y="실루엣계수", markers=True)
    figs.add_vline(x=k, line_dash="dash", line_color="#D62728",
                   annotation_text=f"선택 k={k}", annotation_position="top")
    figs.update_layout(height=230, margin=dict(t=30, b=10, l=10, r=10))
    figs.update_xaxes(tickmode="linear", dtick=1)
    st.plotly_chart(figs, use_container_width=True)
    st.caption("값이 클수록 군집이 잘 나뉜 것입니다.")

coords, labels, pca, _ = run_cluster(X, k)
use["PC1"], use["PC2"] = coords[:, 0], coords[:, 1]
use["군집"] = [f"유형 {i+1}" for i in labels]

st.caption(
    f"PC1이 전체 분산의 {pca.explained_variance_ratio_[0]*100:.1f}%, "
    f"PC2가 {pca.explained_variance_ratio_[1]*100:.1f}%를 설명합니다 "
    f"(합계 {pca.explained_variance_ratio_[:2].sum()*100:.1f}%)."
)

st.divider()

# ── PCA 산점도 + 로딩 ──────────────────────────────────────────
g1, g2 = st.columns([3, 2])

with g1:
    st.subheader("행정동 분포")
    fig = px.scatter(
        use, x="PC1", y="PC2", color="군집", hover_name="admi_nm",
        hover_data={"sgg_nm": True, "living_pop": ":,.0f", "slots_per_1k": ":.1f",
                    "store_food": ":,.0f", "PC1": False, "PC2": False},
        labels={"sgg_nm": "자치구", "living_pop": "생활인구",
                "slots_per_1k": "천명당주차면", "store_food": "음식점수"},
    )
    fig.update_traces(marker=dict(size=9, opacity=0.8))
    fig.update_layout(height=460, margin=dict(t=10, b=10),
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

with g2:
    st.subheader("주성분 구성")
    load = pd.DataFrame(
        pca.components_[:2].T, index=[FEATURES[c] for c in FEATURES], columns=["PC1", "PC2"]
    )
    figl = px.imshow(load, text_auto=".2f", color_continuous_scale="RdBu_r",
                     zmin=-0.7, zmax=0.7, aspect="auto",
                     labels=dict(color="로딩"))
    figl.update_layout(height=460, margin=dict(t=10, b=10), coloraxis_showscale=False)
    st.plotly_chart(figl, use_container_width=True)
    st.caption("값이 클수록 그 주성분을 강하게 끌어올리는 변수입니다. "
               "부호는 임의로 뒤집힐 수 있으니 방향보다 **크기**로 해석하세요.")

st.divider()

# ── 군집별 특성 ────────────────────────────────────────────────
st.subheader("유형별 특성 비교")

prof = use.groupby("군집")[list(FEATURES)].mean()
prof.columns = [FEATURES[c] for c in prof.columns]
# 레이더 비교를 위해 0~100으로 정규화
norm = (prof - prof.min()) / (prof.max() - prof.min()).replace(0, 1) * 100

r1, r2 = st.columns([2, 3])

with r1:
    figr = go.Figure()
    for name, row in norm.iterrows():
        figr.add_trace(go.Scatterpolar(
            r=row.tolist() + [row.iloc[0]],
            theta=norm.columns.tolist() + [norm.columns[0]],
            fill="toself", name=name, opacity=0.55,
        ))
    figr.update_layout(height=430, margin=dict(t=30, b=10),
                       polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                       legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(figr, use_container_width=True)
    st.caption("각 축은 유형 간 상대 위치(0~100)입니다. 절대값이 아닙니다.")

with r2:
    cnt = use["군집"].value_counts().sort_index()
    tbl = prof.copy()
    tbl.insert(0, "동수", cnt)
    st.dataframe(
        tbl.style.format({"동수": "{:.0f}", "생활인구": "{:,.0f}", "20~30대비중": "{:.3f}",
                          "천명당주차면": "{:.1f}", "음식점수": "{:,.0f}", "집객시설수": "{:,.0f}",
                          "상주인구": "{:,.0f}", "직장인구": "{:,.0f}"}),
        use_container_width=True,
    )

    st.markdown("**유형별 대표 행정동**")
    for name in sorted(use["군집"].unique()):
        sub = use[use["군집"] == name].nlargest(4, "living_pop")
        st.caption(f"**{name}** ({cnt[name]}개) — " + ", ".join(sub["admi_nm"]))

st.info(
    "군집 번호는 실행할 때마다 순서가 바뀔 수 있습니다. **번호가 아니라 특성으로** 해석하세요. "
    "예: 직장인구·집객시설이 높으면 도심 업무형, 상주인구가 높고 음식점이 적으면 주거형.",
    icon="💡",
)
