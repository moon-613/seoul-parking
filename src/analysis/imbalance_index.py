"""행정동별 주차수급 불균형 지수 산출 및 취약지역 도출 -> data/processed/imbalance_index.csv

지수 정의 (config.yaml의 imbalance_index 파라미터 참고):
  parking_demand  = 생활인구 기반 추정 주차수요 (야간 상주인구 + 주간 체류인구 가중합 등)
  parking_supply  = 행정동 내 주차면수 (노상+노외+부설 합산)
  imbalance_ratio = parking_demand / parking_supply  (높을수록 공급 부족)
  vulnerable      = imbalance_ratio가 상위 vulnerable_percentile_threshold 이상인 행정동
"""
import pandas as pd

from src.utils.logger import get_logger
from src.utils.settings import DATA_PROCESSED, get_config

logger = get_logger(__name__)


def compute_demand(df: pd.DataFrame) -> pd.Series:
    cfg = get_config()["imbalance_index"]
    return (
        df["living_pop_day"] * cfg["demand_weight_day"]
        + df["living_pop_night"] * cfg["demand_weight_night"]
    )


def compute_imbalance(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["parking_demand"] = compute_demand(df)
    df["imbalance_ratio"] = df["parking_demand"] / df["parking_supply"].replace(0, pd.NA)

    threshold = get_config()["imbalance_index"]["vulnerable_percentile_threshold"]
    cutoff = df["imbalance_ratio"].quantile(threshold)
    df["is_vulnerable"] = df["imbalance_ratio"] >= cutoff
    return df


def main():
    master_path = DATA_PROCESSED / "dong_master.csv"
    df = pd.read_csv(master_path)
    result = compute_imbalance(df)

    out_path = DATA_PROCESSED / "imbalance_index.csv"
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {out_path} (취약지역 {result['is_vulnerable'].sum()}개 행정동)")


if __name__ == "__main__":
    main()
