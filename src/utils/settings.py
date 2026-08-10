"""환경변수(.env)와 config/config.yaml을 읽어 프로젝트 전역 설정을 제공."""
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT_DIR / "config" / "config.yaml"

load_dotenv(ROOT_DIR / ".env")


@lru_cache
def get_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_env(key: str, required: bool = True) -> str:
    value = os.getenv(key)
    if required and not value:
        raise RuntimeError(
            f"환경변수 '{key}'가 설정되지 않았습니다. .env 파일을 .env.example 기준으로 생성하세요."
        )
    return value


# 자주 쓰는 경로
DATA_RAW = ROOT_DIR / "data" / "raw"
DATA_INTERIM = ROOT_DIR / "data" / "interim"
DATA_PROCESSED = ROOT_DIR / "data" / "processed"
DATA_EXTERNAL = ROOT_DIR / "data" / "external"
