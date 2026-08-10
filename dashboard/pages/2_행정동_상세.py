"""개별 행정동을 선택해 시간대별 생활인구 vs 주차공급을 비교하는 상세 페이지."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils.settings import DATA_PROCESSED  # noqa: E402

st.set_page_config(page_title="행정동 상세 | 주차수급 불균형", page_icon="🔎", layout="wide")
st.title("🔎 행정동 상세 진단")


@st.cache_data
def load_data() -> pd.DataFrame:
    path = DATA_PROCESSED / "imbalance_index.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


df = load_data()
if df.empty:
    st.warning("분석 데이터가 없습니다. 파이프라인을 먼저 실행하세요.")
else:
    dong = st.selectbox("행정동 선택", sorted(df["adm_dong_nm"].unique()))
    row = df[df["adm_dong_nm"] == dong].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("추정 주차수요", f"{row['parking_demand']:,.0f}")
    c2.metric("주차공급(면수)", f"{row['parking_supply']:,.0f}")
    c3.metric("불균형 지수", f"{row['imbalance_ratio']:.2f}", delta="취약" if row["is_vulnerable"] else "양호")
