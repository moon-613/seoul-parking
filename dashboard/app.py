"""서울 공영주차 대시보드 진입점 — 실행: streamlit run dashboard/app.py

페이지를 pages/ 자동 탐색이 아니라 st.navigation으로 등록하는 이유
--------------------------------------------------------------
① 사이드바 라벨이 파일명에서 풀려난다.
   전에는 `2_코스추천.py` 가 그대로 라벨이 됐는데, 그 페이지에는 코스(여러 곳을
   잇는 동선)가 없고 동네 추천과 방문 시간대만 있어 이름이 내용과 어긋났다.
② 두 사용자를 사이드바에서 나눠 보여줄 수 있다.
   기획서가 주 사용자(나들이객)와 부 사용자(자치구 주차 정책 담당)를 나눠 두었는데,
   화면에서는 다섯 페이지가 평평하게 나열돼 누구를 위한 화면인지 드러나지 않았다.
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from common import mark_korean  # noqa: E402

st.set_page_config(page_title="서울 공영주차 진단", page_icon="🅿️", layout="wide")
mark_korean()

nav = st.navigation({
    "나들이 계획": [
        st.Page("views/overview.py", title="현황", icon="🅿️", default=True),
        st.Page("views/map.py", title="지도", icon="🗺️"),
        st.Page("views/recommend.py", title="동네 추천", icon="🎯"),
        st.Page("views/types.py", title="동네 유형", icon="🧩"),
    ],
    "주차 정책": [
        st.Page("views/expansion.py", title="확충 우선순위", icon="🏗️"),
    ],
})
nav.run()
