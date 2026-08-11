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
