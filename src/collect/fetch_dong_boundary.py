"""SGIS 통계지리정보서비스에서 서울시 행정동 경계 수집 -> data/external/dong_boundary.geojson

SGIS는 consumer_key/secret으로 access_token을 먼저 발급받아야 함.
https://sgis.kostat.go.kr/developer 문서 참고 (인증키는 무료 발급, 하루 트래픽 제한 있음).
"""
import geopandas as gpd
import requests

from src.utils.logger import get_logger
from src.utils.settings import DATA_EXTERNAL, get_config, get_env

logger = get_logger(__name__)

SEOUL_ADM_CD = "11"  # 시도코드: 서울특별시


def get_access_token() -> str:
    cfg = get_config()["sgis"]
    resp = requests.get(
        f"{cfg['base_url']}/auth/authentication.json",
        params={
            "consumer_key": get_env("SGIS_CONSUMER_KEY"),
            "consumer_secret": get_env("SGIS_CONSUMER_SECRET"),
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["result"]["accessToken"]


def fetch_dong_boundary() -> gpd.GeoDataFrame:
    cfg = get_config()["sgis"]
    token = get_access_token()
    resp = requests.get(
        f"{cfg['base_url']}/boundary/hadmarea.geojson",
        params={"accessToken": token, "cd": SEOUL_ADM_CD, "year": "2024"},
        timeout=30,
    )
    resp.raise_for_status()
    return gpd.read_file(resp.text)


def main():
    gdf = fetch_dong_boundary()
    out_path = DATA_EXTERNAL / "dong_boundary.geojson"
    gdf.to_file(out_path, driver="GeoJSON")
    logger.info(f"저장 완료: {out_path} ({len(gdf)}개 행정동)")


if __name__ == "__main__":
    main()
