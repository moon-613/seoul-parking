"""카카오 로컬 API로 행정동별 POI(놀거리/음식점) 밀집도 수집 -> data/raw/poi_counts.csv

행정동 경계의 중심점(centroid) 기준 반경 내 카테고리별 장소 수를 집계한다.
개별 장소 목록 대신 응답 meta.total_count를 밀집도 지표로 사용 —
카카오 카테고리 검색은 최대 45건(3페이지)까지만 목록을 주지만 total_count는 전체 건수를 반환하므로,
요청 수를 (행정동 x 카테고리)로 최소화하면서 밀집도를 얻을 수 있다.

선행 조건: src/collect/fetch_dong_boundary.py 실행 (행정동 경계 필요)
"""
import time

import geopandas as gpd
import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils.logger import get_logger
from src.utils.settings import DATA_EXTERNAL, DATA_RAW, get_config, get_env

logger = get_logger(__name__)

REQUEST_INTERVAL_SEC = 0.05  # 카카오 API 초당 요청 제한 완화용


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _category_count(lon: float, lat: float, category_code: str, radius: int) -> int:
    cfg = get_config()["kakao_local"]
    resp = requests.get(
        f"{cfg['base_url']}/search/category.json",
        headers={"Authorization": f"KakaoAK {get_env('KAKAO_REST_API_KEY')}"},
        params={
            "category_group_code": category_code,
            "x": lon,
            "y": lat,
            "radius": radius,
            "size": 1,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["meta"]["total_count"]


def fetch_poi_counts() -> pd.DataFrame:
    cfg = get_config()["kakao_local"]
    boundary_path = DATA_EXTERNAL / "dong_boundary.geojson"
    if not boundary_path.exists():
        raise FileNotFoundError(
            "행정동 경계 파일이 없습니다. fetch_dong_boundary.py를 먼저 실행하세요."
        )

    gdf = gpd.read_file(boundary_path).to_crs("EPSG:4326")
    centroids = gdf.geometry.centroid

    records = []
    total = len(gdf)
    for i, (idx, row) in enumerate(gdf.iterrows(), start=1):
        point = centroids.loc[idx]
        record = {
            "adm_dong_cd": row.get("adm_cd"),
            "adm_dong_nm": row.get("adm_nm"),
            "lon": point.x,
            "lat": point.y,
        }
        for code, name in cfg["categories"].items():
            record[f"poi_{name}"] = _category_count(point.x, point.y, code, cfg["radius_m"])
            time.sleep(REQUEST_INTERVAL_SEC)

        records.append(record)
        if i % 25 == 0 or i == total:
            logger.info(f"POI 수집 진행 {i}/{total}")

    df = pd.DataFrame(records)
    poi_cols = [c for c in df.columns if c.startswith("poi_")]
    df["poi_total"] = df[poi_cols].sum(axis=1)
    return df


def main():
    df = fetch_poi_counts()
    out_path = DATA_RAW / "poi_counts.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {out_path} ({len(df)}행)")


if __name__ == "__main__":
    main()
