# 제출물

서울시 생활인구 기반 행정동별 주차수급 불균형 진단 및 취약지역 도출

## 배포된 대시보드

**https://seoul-parking.streamlit.app/**

설치 없이 바로 열람 가능합니다. 소스는 드라이브에 올린 `seoul-parking.zip` 과 동일합니다.

## 폴더 구성

| 폴더 | 담을 것 | 상태 |
|---|---|---|
| `01_보고서/` | 분석 아이디어 기획서 (DOCX) | ✅ |
| `02_발표자료/` | 발표용 슬라이드 (PPTX/PDF) — `src/report/build_deck.py`로 생성 | ✅ |
| `03_최종데이터/` | 최종 분석 테이블 8종 + 컬럼 설명 README | ✅ |
| `04_스크린샷/` | 대시보드 5페이지 전체 캡처 + README | ✅ |
| `seoul-parking.zip` | 전체 소스 (대시보드·수집·전처리·분석) + 구동용 데이터 · 드라이브 업로드 | ✅ |

## 제출 체크리스트

- [x] 보고서 — 배경/데이터/방법론/결과/결론 (`reports/report.md` → PPT로 통합)
- [x] 발표자료
- [x] 최종 데이터셋 — `panel.csv` 외 7종 (`03_최종데이터/README.md`에 컬럼 명세)
- [x] 대시보드 스크린샷 — 현황(KPI·시간대 곡선·자치구 막대) / 지도 / 동네추천 / 동네유형(PCA 군집) / 확충 우선순위
- [x] 소스코드 — `seoul-parking.zip` (드라이브 업로드, 배포 URL과 같은 저장소)
- [x] README (실행 방법 포함) — zip 안 루트 `README.md` 「시작하기」

## 소스코드 zip 구성

`python -m src.report.make_zip` 으로 생성합니다 (94개 파일, 6.3MB).
git 추적 파일만 담아 `.env`·`.venv`·`__pycache__` 는 제외되고,
한글 파일명이 Windows 에서 깨지지 않도록 UTF-8 플래그를 확인한 뒤 저장합니다.
압축을 풀면 `seoul-parking/` 폴더 하나가 나옵니다.

| 경로 | 내용 |
|---|---|
| `dashboard/` | Streamlit 앱 — `app.py` + `common.py` + `map_render.py` + `views/` 6페이지 |
| `src/` | 수집·전처리·분석·보고서 생성 스크립트 |
| `data/processed/`, `data/external/` | 대시보드 구동에 필요한 CSV 7종 + 행정동 경계 geojson |
| `config/config.yaml`, `.streamlit/` | 설정·테마 |
| `requirements.txt` | 대시보드 실행용 (dev 는 `requirements-dev.txt`) |

로컬 실행:

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py
```

## 주의

- ⚠️ **`.env` 파일은 절대 포함하지 말 것** (API 키 유출). 제출 시 `.env.example`만 포함.
- 최종 데이터가 크면 원본 대신 집계본만 포함하고, 원본은 재현 스크립트로 대체.
