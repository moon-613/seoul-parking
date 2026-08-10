"""SGIS 통계지리정보서비스에서 서울시 행정동 경계 수집 -> data/external/dong_boundary.geojson

SGIS는 consumer_key/secret으로 access_token을 먼저 발급받아야 함.
https://sgis.mods.go.kr 문서 참고 (인증키 무료 발급, 하루 트래픽 제한 있음).

좌표계 주의
---------
SGIS의 hadmarea.geojson은 헤더에 CRS84(=WGS84 경위도)라고 선언하지만
실제 좌표는 **UTM-K(EPSG:5179) 미터 단위**다.
  선언: CRS84          실제: X 953,230 / Y 1,952,854 (미터)
이대로 지도에 그리면 경도 953,553도 위치가 되어 화면 밖으로 나간다.
따라서 5179로 명시한 뒤 4326으로 재투영해서 저장한다.
"""
import geopandas as gpd
import requests

from src.utils.logger import get_logger
from src.utils.settings import DATA_EXTERNAL, get_config, get_env

logger = get_logger(__name__)

SEOUL_ADM_CD = "11"   # 시도코드: 서울특별시
SGIS_CRS = "EPSG:5179"   # SGIS 응답의 실제 좌표계 (UTM-K)
OUTPUT_CRS = "EPSG:4326"  # 지도 표시용 (WGS84 경위도)


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
    # low_search=2 여야 행정동(426개)이 나온다. 기본값 1은 자치구(25개)까지만 내려간다.
    resp = requests.get(
        f"{cfg['base_url']}/boundary/hadmarea.geojson",
        params={
            "accessToken": token,
            "adm_cd": SEOUL_ADM_CD,
            "year": cfg["boundary_year"],
            "low_search": 2,
        },
        timeout=90,
    )
    resp.raise_for_status()
    gdf = gpd.read_file(resp.text)

    # 선언된 CRS를 믿지 말고 좌표값으로 판단한다.
    # 경위도라면 |x| <= 180 이어야 하는데, 미터 좌표면 수십만 단위로 나온다.
    max_x = gdf.geometry.bounds["maxx"].max()
    if max_x > 180:
        logger.info(f"미터 좌표 감지 (maxx={max_x:,.0f}) — {SGIS_CRS} → {OUTPUT_CRS} 재투영")
        gdf = gdf.set_crs(SGIS_CRS, allow_override=True).to_crs(OUTPUT_CRS)
    else:
        logger.info("이미 경위도 좌표 — 재투영 생략")
        gdf = gdf.set_crs(OUTPUT_CRS, allow_override=True)

    return gdf


def main():
    gdf = fetch_dong_boundary()
    out_path = DATA_EXTERNAL / "dong_boundary.geojson"
    gdf.to_file(out_path, driver="GeoJSON")

    b = gdf.total_bounds
    logger.info(f"저장 완료: {out_path} ({len(gdf)}개 행정동)")
    logger.info(f"  좌표 범위: 경도 {b[0]:.4f}~{b[2]:.4f} / 위도 {b[1]:.4f}~{b[3]:.4f}")


if __name__ == "__main__":
    main()
