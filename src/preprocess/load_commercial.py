"""상권분석 CSV 4종을 읽어 행정동 단위로 병합 -> data/interim/commercial_dong.csv

수동 다운로드 대상 (서울 열린데이터광장, "-행정동" 버전 = OA-22xxx):
  점포_행정동.csv       음식점·카페 점포 수
  집객시설_행정동.csv    영화관·문화시설 수
  상주인구_행정동.csv    동네 성격 구분 변수
  직장인구_행정동.csv    동네 성격 구분 변수

배치 위치: data/external/commercial/  (파일명은 config.yaml 의 commercial.files 참고)

주의: "-상권"(OA-15xxx) 버전은 공간 단위가 달라 행정동 조인이 되지 않는다.
      2024년부터 표준단위구역으로 전환, 2026-07-03부터 2021년 이후 자료만 제공되므로
      여러 분기를 병합할 때는 컬럼 구조를 먼저 대조할 것.
"""
from pathlib import Path

import pandas as pd

from src.utils.logger import get_logger
from src.utils.settings import DATA_INTERIM, ROOT_DIR, get_config

logger = get_logger(__name__)


def _read(path: Path) -> pd.DataFrame:
    """상권분석 CSV는 인코딩이 파일마다 다를 수 있어 순차 시도한다."""
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"인코딩을 판별하지 못했습니다: {path}")


def load_all() -> dict[str, pd.DataFrame]:
    cfg = get_config()["commercial"]
    base = ROOT_DIR / cfg["dir"]

    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for key, filename in cfg["files"].items():
        path = base / filename
        if not path.exists():
            missing.append(str(path))
            continue
        df = _read(path)
        frames[key] = df
        logger.info(f"{key}: {path.name} — {len(df):,}행 / 컬럼 {len(df.columns)}개")

    if missing:
        logger.warning("아래 파일이 없습니다. 서울 열린데이터광장에서 받아 배치하세요:")
        for m in missing:
            logger.warning(f"  - {m}")

    return frames


def main():
    frames = load_all()
    if not frames:
        logger.error("읽은 파일이 없습니다. data/external/commercial/ 에 CSV를 배치하세요.")
        return

    # 실제 컬럼명은 분기별로 달라질 수 있어, 먼저 구조를 출력해 확인한 뒤 병합 로직을 확정한다.
    for key, df in frames.items():
        logger.info(f"[{key}] 컬럼: {list(df.columns)[:12]}")

    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    logger.info("컬럼 구조 확인 후 행정동 기준 병합 로직 구현 예정 (TODO)")


if __name__ == "__main__":
    main()
