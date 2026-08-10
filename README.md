# 서울시 생활인구 기반 행정동별 주차수급 불균형 진단 및 취약지역 도출

서울시 생활인구 데이터를 활용해 행정동 단위의 주차 수요-공급 불균형을 진단하고, 주차 취약지역을 도출하는 데이터 분석 프로젝트.

## 파이프라인

```
OpenAPI 수집 (src/collect) → 전처리/병합 (src/preprocess) → 분석 (src/analysis)
  → 보고서 (reports) / 대시보드 (dashboard, Streamlit)
```

## 프로젝트 구조

```
├── config/config.yaml        # 프로젝트 전역 설정 (API 서비스명, 분석 파라미터 등)
├── .env.example               # API 인증키 템플릿 (.env로 복사해서 사용)
├── data/
│   ├── raw/                   # OpenAPI 원본 응답 (버전관리 제외)
│   ├── interim/                # 중간 가공 데이터
│   ├── processed/              # 분석용 최종 테이블 (dong_master, imbalance_index)
│   └── external/                # 행정동 경계 등 외부 참조 데이터
├── src/
│   ├── collect/                # OpenAPI 수집 스크립트
│   ├── preprocess/             # 정제 및 행정동 단위 병합
│   ├── analysis/               # 불균형 지수 산출, 취약지역 도출
│   └── utils/                  # 공통 API 클라이언트, 설정, 로거
├── notebooks/                  # 탐색적 분석(EDA) 노트북
├── dashboard/                  # Streamlit 대시보드 (app.py + pages/)
├── reports/                    # 분석 보고서, 산출 figure
├── docs/data_dictionary.md     # 데이터 사전
└── tests/                      # 단위 테스트
```

## 문서
- [PROGRESS.md](./PROGRESS.md) — 일자별 진행 내용 / 트러블슈팅 / 남은 작업
- [docs/data_sources.md](./docs/data_sources.md) — 수집 데이터 6종 명세, 최종 테이블 스키마, 대시보드 매핑

## 시작하기

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

copy .env.example .env         # 이후 .env에 발급받은 API 키 입력
```

필요한 API 키:
- **서울 열린데이터광장** (`SEOUL_OPENAPI_KEY`): https://data.seoul.go.kr → 생활인구, 주차장 정보, 등록차량 현황
- **SGIS 통계지리정보서비스** (`SGIS_CONSUMER_KEY/SECRET`): https://sgis.kostat.go.kr → 행정동 경계 데이터

## 파이프라인 실행

```bash
# 1. 데이터 수집
python -m src.collect.fetch_living_population --date 20260601
python -m src.collect.fetch_parking_lots
python -m src.collect.fetch_registered_vehicles
python -m src.collect.fetch_dong_boundary

# 2. 전처리 (행정동 단위 병합)
python -m src.preprocess.clean_merge

# 3. 분석 (불균형 지수 산출 및 취약지역 도출)
python -m src.analysis.imbalance_index

# 4. 테스트
pytest

# 5. 대시보드 실행
streamlit run dashboard/app.py
```

## 현재 상태

프로젝트 기본 골격만 구성된 상태. `src/collect`의 서비스명·파라미터는 실제 OpenAPI 응답을 확인하며 조정이 필요하고, `src/preprocess/clean_merge.py`의 병합 로직과 `dashboard`의 컬럼명은 실제 수집 데이터 구조에 맞춰 구현해야 함 (`TODO` 표시).

## 다음 단계
1. API 키 발급 및 `.env` 설정
2. `src/collect` 스크립트로 원본 데이터 1회 수집 → 응답 구조 확인 후 `docs/data_dictionary.md` 업데이트
3. `src/preprocess/clean_merge.py` 실제 병합 로직 구현
4. `src/analysis/imbalance_index.py`로 불균형 지수/취약지역 산출
5. `reports/report.md` 작성, `dashboard` 완성
