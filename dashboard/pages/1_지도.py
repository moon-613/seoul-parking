"""행정동 경계에 불균형 지수를 색상으로 표시하는 지도 페이지."""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils.settings import DATA_EXTERNAL, DATA_PROCESSED  # noqa: E402

st.set_page_config(page_title="지도 | 주차수급 불균형", page_icon="🗺️", layout="wide")
st.title("🗺️ 행정동별 주차수급 불균형 지도")


@st.cache_data
def load_map_data():
    idx_path = DATA_PROCESSED / "imbalance_index.csv"
    boundary_path = DATA_EXTERNAL / "dong_boundary.geojson"
    if not idx_path.exists() or not boundary_path.exists():
        return None, None
    return pd.read_csv(idx_path), gpd.read_file(boundary_path)


df, boundary = load_map_data()
if df is None:
    st.warning("분석 데이터 또는 행정동 경계 파일이 없습니다. 파이프라인을 먼저 실행하세요.")
else:
    merged = boundary.merge(df, on="adm_dong_cd", how="left")
    fig = px.choropleth_mapbox(
        merged,
        geojson=merged.geometry.__geo_interface__,
        locations=merged.index,
        color="imbalance_ratio",
        color_continuous_scale="OrRd",
        mapbox_style="carto-positron",
        center={"lat": 37.5665, "lon": 126.9780},
        zoom=10,
        opacity=0.7,
        hover_name="adm_dong_nm",
    )
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=700)
    st.plotly_chart(fig, use_container_width=True)
