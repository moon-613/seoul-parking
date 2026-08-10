"""raw 데이터를 정제하여 행정동 단위 마스터 테이블 생성 -> data/processed/dong_master.csv

병합 기준: 행정동코드(adm_dong_cd)
- 생활인구: data/raw/living_population_*.csv (일별 -> 시간대별 평균/피크로 집계)
- 주차장: data/raw/parking_lots.csv (위경도 -> 행정동 공간조인으로 배분, 주차면수 합산)
- 등록차량: data/raw/registered_vehicles.csv (자치구 단위, 필요 시 인구비례로 행정동 배분)
- 행정동 경계: data/external/dong_boundary.geojson
"""
import geopandas as gpd
import pandas as pd

from src.utils.logger import get_logger
from src.utils.settings import DATA_EXTERNAL, DATA_PROCESSED, DATA_RAW, get_config

logger = get_logger(__name__)


def load_living_population() -> pd.DataFrame:
    files = sorted(DATA_RAW.glob("living_population_*.csv"))
    if not files:
        raise FileNotFoundError("생활인구 raw 파일이 없습니다. fetch_living_population.py를 먼저 실행하세요.")
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    return df


def load_parking_lots() -> gpd.GeoDataFrame:
    df = pd.read_csv(DATA_RAW / "parking_lots.csv")
    cfg = get_config()["project"]
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["LOT"], df["LAT"]),
        crs=cfg["crs_display"],
    )
    return gdf


def join_parking_to_dong(parking_gdf: gpd.GeoDataFrame, dong_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """주차장 포인트를 행정동 폴리곤에 공간조인하여 행정동별 주차면수 합산."""
    joined = gpd.sjoin(parking_gdf.to_crs(dong_gdf.crs), dong_gdf, how="left", predicate="within")
    return joined


def build_dong_master() -> pd.DataFrame:
    dong_gdf = gpd.read_file(DATA_EXTERNAL / "dong_boundary.geojson")
    pop_df = load_living_population()
    parking_gdf = load_parking_lots()

    parking_joined = join_parking_to_dong(parking_gdf, dong_gdf)

    # TODO: 실제 API 응답 컬럼명 확정 후 groupby/집계 로직 구현
    logger.info("dong_master 병합 로직은 실제 컬럼명 확인 후 구현 필요 (TODO)")

    return pd.DataFrame()


def main():
    master = build_dong_master()
    out_path = DATA_PROCESSED / "dong_master.csv"
    master.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {out_path}")


if __name__ == "__main__":
    main()
