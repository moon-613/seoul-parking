"""matplotlib 한글 폰트 설정 — 머신마다 다른 폰트를 자동으로 고른다.

왜 필요한가
----------
분석 스크립트가 폰트를 `Malgun Gothic`(Windows 기본)으로 박아두면
macOS에서 그림을 다시 그릴 때 축·범례·행정동 이름이 전부 두부(□□□)로 나온다.
경고만 뜨고 그림 자체는 저장되므로 **깨진 걸 모르고 보고서에 넣기 쉽다.**

설치된 폰트 중 후보 목록의 첫 번째를 골라 쓴다.
어느 폰트가 선택됐는지 로그로 남겨 그림이 이상할 때 원인을 바로 찾게 한다.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib import font_manager

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 앞에 있는 것부터 우선 사용 (Windows -> macOS -> 나눔)
FONT_CANDIDATES = [
    "Malgun Gothic",        # Windows 기본
    "Apple SD Gothic Neo",  # macOS 기본 (AppleGothic보다 자소 렌더링이 깔끔)
    "AppleGothic",          # macOS 구형
    "NanumGothic",          # 수동 설치 (Linux/CI 포함)
]


def pick_korean_font() -> str | None:
    """설치된 한글 폰트 중 첫 번째 후보 이름. 없으면 None."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in FONT_CANDIDATES:
        if name in installed:
            return name
    return None


def annotate_spread(ax, points, *, fontsize=8, color=None, max_shift=5):
    """겹치지 않게 점 라벨을 붙인다. points = [(x, y, text), ...]

    왜 필요한가
    ----------
    잔차 하위 동네들은 좌표가 거의 같다(주차면 1~5면 · 생활인구도 비슷).
    그대로 annotate 하면 이름이 서로 포개져 한 덩어리로 뭉개진다.

    방법: 후보 오프셋을 순서대로 시도해 이미 놓인 라벨과 화면 좌표에서
    겹치지 않는 첫 자리에 놓는다. 끝까지 자리가 없으면 그 라벨은 건너뛴다
    (겹쳐서 둘 다 못 읽느니 하나만 읽히는 편이 낫다).
    """
    ax.figure.canvas.draw()
    placed = []
    # (dx, dy) 후보 — 오른쪽 위부터 시계 방향으로 벌려 나간다
    offsets = [(5, 4), (5, -10), (-5, 4), (-5, -10), (5, 14), (5, -20), (-5, 14), (-5, -20)]

    for x, y, text in points:
        for dx, dy in offsets[:max_shift + 3]:
            ann = ax.annotate(text, (x, y), fontsize=fontsize, color=color,
                              xytext=(dx, dy), textcoords="offset points",
                              ha="left" if dx > 0 else "right")
            ax.figure.canvas.draw()
            bb = ann.get_window_extent()
            if not any(bb.overlaps(p) for p in placed):
                placed.append(bb)
                break
            ann.remove()


def use_korean_font() -> str | None:
    """matplotlib 전역 설정에 한글 폰트를 적용한다.

    분석 스크립트 상단에서 한 번만 호출하면 된다.
    """
    font = pick_korean_font()
    if font:
        plt.rcParams["font.family"] = font
        logger.info(f"한글 폰트: {font}")
    else:
        logger.warning(
            "한글 폰트를 찾지 못했습니다. 그림의 한글이 깨집니다(□□□). "
            f"후보 중 하나를 설치하세요: {', '.join(FONT_CANDIDATES)}"
        )
    # 마이너스 기호를 유니코드로 그리면 한글 폰트에 글리프가 없어 깨진다
    plt.rcParams["axes.unicode_minus"] = False
    return font
