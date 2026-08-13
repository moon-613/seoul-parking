"""지도 페이지 (주차 정책) — 자치구 주차 정책 담당자가 볼 지표 5개만.

이 다섯은 전부 static=True다. 그래서 이 페이지에서는 사이드바의 요일·시간대와
'표시 방식' 라디오를 아예 띄우지 않는다. 예전에는 정책 지표를 고를 때마다
라디오가 비활성으로 남고 "시간에 따라 변하지 않습니다" 안내가 매번 떴는데,
쓰지 않는 조건이 화면에 있으면 바꿔도 결과가 안 변해 이용자가 혼란스럽다.
"""
from map_render import BASIS_TIMESLOT, BASIS_WEEKDAY, POLICY_METRICS, render_map

render_map(
    POLICY_METRICS,
    title="🗺️ 공급 진단 지도",
    lead="공영주차를 어디에 지어야 하는지 봅니다. "
         f"모두 시간에 따라 변하지 않는 지표라 요일·시간대를 묻지 않습니다 "
         f"(기준 시점 {BASIS_WEEKDAY}요일 {BASIS_TIMESLOT}).",
    time_aware=False,
)
