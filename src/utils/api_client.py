"""서울 열린데이터광장 OpenAPI 공통 클라이언트.

URL 규격: {base_url}/{KEY}/json/{서비스명}/{시작인덱스}/{종료인덱스}/[추가 파라미터...]
https://data.seoul.go.kr 문서 참고.
"""
from __future__ import annotations

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils.logger import get_logger
from src.utils.settings import get_config, get_env

logger = get_logger(__name__)


class SeoulOpenApiError(RuntimeError):
    pass


class SeoulOpenApiClient:
    def __init__(self):
        cfg = get_config()["seoul_openapi"]
        self.base_url = cfg["base_url"]
        self.page_size = cfg["page_size"]
        self.api_key = get_env("SEOUL_OPENAPI_KEY")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _request_page(self, service: str, start: int, end: int, extra_path: list[str] | None = None) -> dict:
        path_parts = [self.base_url, self.api_key, "json", service, str(start), str(end)]
        if extra_path:
            path_parts += [str(p) for p in extra_path]
        url = "/".join(path_parts)
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def fetch_all(self, service: str, extra_path: list[str] | None = None, max_rows: int | None = None) -> list[dict]:
        """서비스의 전체 행을 페이지네이션하며 수집."""
        rows: list[dict] = []
        start = 1
        while True:
            end = start + self.page_size - 1
            payload = self._request_page(service, start, end, extra_path)

            root_key = next((k for k in payload if k != "RESULT"), None)
            if root_key is None:
                raise SeoulOpenApiError(f"{service} 응답에 데이터 필드가 없습니다: {payload}")

            body = payload[root_key]
            result_code = body.get("RESULT", {}).get("CODE", "")
            if result_code and result_code not in ("INFO-000",):
                if result_code == "INFO-200":  # 더 이상 데이터 없음
                    break
                raise SeoulOpenApiError(f"{service} API 오류 [{result_code}]: {body.get('RESULT', {}).get('MESSAGE')}")

            page_rows = body.get("row", [])
            rows.extend(page_rows)
            logger.info(f"{service}: {start}~{end} 수집 ({len(page_rows)}건, 누적 {len(rows)}건)")

            if len(page_rows) < self.page_size:
                break
            if max_rows and len(rows) >= max_rows:
                rows = rows[:max_rows]
                break
            start = end + 1

        return rows
