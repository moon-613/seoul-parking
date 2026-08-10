"""서울시 행정동별 주차수급 불균형 대시보드 (홈)

실행: streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.utils.settings import DATA_PROCESSED  # noqa: E402

st.set_page_config(page_title="서울시 주차수급 불균형 대시보드", page_icon="🅿️", layout="wide")


@st.cache_data
def load_data() -> pd.DataFrame:
    path = DATA_PROCESSED / "imbalance_index.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def main():
    st.title("🅿️ 서울시 생활인구 기반 주차수급 불균형 대시보드")
    st.caption("행정동별 주차수요(생활인구 기반) 대비 주차공급(주차면수) 불균형 진단 및 취약지역 도출")

    df = load_data()
    if df.empty:
        st.warning(
            "분석 데이터가 없습니다. src/collect -> src/preprocess -> src/analysis 파이프라인을 먼저 실행하세요."
        )
        st.code(
            "python -m src.collect.fetch_living_population\n"
            "python -m src.collect.fetch_parking_lots\n"
            "python -m src.collect.fetch_registered_vehicles\n"
            "python -m src.collect.fetch_dong_boundary\n"
            "python -m src.preprocess.clean_merge\n"
            "python -m src.analysis.imbalance_index"
        )
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("분석 대상 행정동 수", f"{len(df):,}개")
    col2.metric("취약지역 수", f"{int(df['is_vulnerable'].sum()):,}개")
    col3.metric("평균 불균형 지수", f"{df['imbalance_ratio'].mean():.2f}")

    st.subheader("행정동별 불균형 지수 상위 20개")
    top20 = df.sort_values("imbalance_ratio", ascending=False).head(20)
    fig = px.bar(top20, x="imbalance_ratio", y="adm_dong_nm", orientation="h")
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("원본 데이터")
    st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
