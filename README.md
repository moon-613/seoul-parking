# 서울시 생활인구 기반 행정동별 공영주차 접근성 진단

주말 나들이 때 **목적지를 정하기 전에** "어느 동네를 몇 시에 가야 주차가 덜 막힐까"를 판단할 근거를 만드는 프로젝트.

기존 주차 서비스(모두의주차장·서울주차정보)는 **목적지가 이미 정해진** 사람에게 주변 빈자리를 찾아줍니다. 이 프로젝트는 그 **이전 단계**를 다룹니다.

**분석 단위: 행정동 × 요일 × 시간대 = 11,872행** (424 × 7 × 4)

---

## 진행 단계

```
① 기획  →  ② 수집  →  ③ 전처리  →  ④ 분석  →  ⑤ 보고서  →  ⑥ 대시보드  →  ⑦ 발표
  ✅        ✅         ✅          ✅         ⬜          ✅           ⬜
```

---

### ① 기획 ✅

- **문제 정의**: 주차 만차로 낭비하는 시간 → 코스 결정 전에 판단할 근거 제공
- **분석 단위 확정**: 행정동 단독 → **행정동 × 요일 × 시간대** 패널로 재설계
- **시간대 4구간**: 아침(06-11) / 점심(11-14) / 오후(14-18) / 저녁밤(18-24)
- 기획서 작성 후 **사실 검증으로 20여 곳 수정** → `submission/01_보고서/`

**중간에 방향을 두 번 바꿨습니다**

| 시점 | 변경 | 이유 |
|---|---|---|
| 수집 중 | 실시간 주차 → **구조적 과부족(회귀 잔차)** | `CUR_PARKING` 컬럼 폐지 확인 |
| 분석 중 | 주차 공급 → **공영주차 접근성** | 민영 데이터가 공개되지 않아 측정 대상을 정직하게 한정 |

### ② 수집 ✅

| 데이터 | 출처 | 방식 | 규모 |
|---|---|---|---|
| 생활인구 | 서울 열린데이터광장 | OpenAPI | **56일** (7요일 × 8일치) |
| 주차장(표준) | 공공데이터포털 | OpenAPI | 856개소 73,796면 |
| 주차장(서울시) | 서울 열린데이터광장 | OpenAPI | 보충용 43개 동 |
| 상권분석 4종 | 서울 열린데이터광장 | CSV | 점포·집객시설·상주인구·직장인구 |
| 행정동 경계 | SGIS | OpenAPI | 426개 |
| 행정동 코드정보 | 서울 열린데이터광장 | 파일 | 43개월분 |

```bash
python -m src.collect.fetch_dong_boundary
python -m src.collect.fetch_parking_standard
python -m src.collect.fetch_parking_seoul
python -m src.collect.fetch_living_population --days 56
```

> 상권분석 CSV는 웹에서 직접 받아 `data/external/commercial/`에 배치합니다. 링크는 [docs/data_links.md](./docs/data_links.md).

### ③ 전처리 ✅

이 프로젝트에서 **가장 오래 걸린 단계**입니다.

| 모듈 | 한 일 | 결과 |
|---|---|---|
| `dong_code.py` | 서로 다른 행정동코드 체계 연결 | 조인율 **7.5% → 100%** |
| `geocode_parking.py` | 주소 → 행정동 배정 | 배정률 **100%** |
| `build_panel.py` | 집계·병합·파생변수, 공휴일 제외 | **11,872행** |
| `validate.py` | 중복·논리·결측·이상치 검증 | 전 항목 통과 |

```bash
python -m src.preprocess.dong_code
python -m src.preprocess.geocode_parking --source standard
python -m src.preprocess.geocode_parking --source seoul
python -m src.preprocess.build_panel --quarter 20261
python -m src.preprocess.validate
```

**주요 처리**
- 생활인구(행안부 코드) ↔ SGIS 경계(자체 코드) → 코드정보 파일을 다리로 연결
- 주차장에 행정동 정보가 없어 SGIS 지오코딩으로 배정 (좌표는 결측 5.7~33.5%)
- **평일에 낀 공휴일 2일 제외** (지방선거 6/3, 제헌절 7/17) → 변동계수 수 2.01%→0.19%
- 이상치는 **제거하지 않음** — 서교동 117,158명은 오류가 아니라 실제 번화가

### ④ 분석 ✅

```bash
python -m src.analysis.daily_trend   # 일별 추세·공휴일 검증
python -m src.analysis.explore       # 상관 히트맵·자치구 분포
python -m src.analysis.residual      # 회귀 잔차 진단
```

**핵심 결과**

| 발견 | 수치 |
|---|---|
| 공영주차 공급이 생활인구로 설명되는 정도 | **R² = 0.074** (변수 5개로 늘려도 0.092) |
| 공급 부족 / 여유 행정동 | 56개 / 54개 |
| 가설 3 (음식점 밀도 ↔ 1인당 주차면) | r = **-0.02**, 사실상 기각 |
| 다중공선성 | 음식점 ↔ 카페 **r = 0.93** |

> **가장 중요한 발견**: 서울 공영주차장은 사람이 얼마나 오는지와 **거의 무관하게 배치**돼 있습니다.
> 논현2동은 4.4만 명에 13면, 도봉1동은 1.75만 명에 1,413면입니다.
> 가설이 기각된 것 자체가 결과이며, 설명되지 않는 편차가 크므로 잔차 진단이 오히려 유효해집니다.

산출: `reports/figures/*.png` (5종), `data/processed/dong_residual.csv`

### ⑤ 보고서 ⬜

`reports/report.md`가 목차 상태입니다. 위 결과를 배경→방법→결과→결론으로 엮어야 합니다.

### ⑥ 대시보드 ✅

```bash
.\.venv\Scripts\streamlit.exe run dashboard/app.py
```

사이드바(요일·시간대·자치구·0면동 제외)가 **4개 페이지 전부에 연동**됩니다.

| 페이지 | 내용 |
|---|---|
| `app` 탐색 | KPI 4종 + 시간대별 곡선 + 자치구 여유도 + 순위표 |
| `1_지도` | 행정동 choropleth, 지표 5종 전환, **‘이 시간대의 편차’ 모드** |
| `2_코스추천` | 놀거리×주차 사분면, 추천 랭킹, 동네별 최적 시간대 |
| `3_동네유형` | PCA + K-means(실루엣 자동), 레이더 비교 |

### ⑦ 발표 준비 ⬜

`submission/` 폴더에 정리합니다. 발표자료·스크린샷 미착수.

---

## 결론 요약

| 무엇을 답하나 | 예시 (토요일 오후) |
|---|---|
| **어디로 갈까** | 을지로동 — 음식점 630개에 1,000명당 67면 |
| **언제 갈까** | 성수2가3동 — 오후(3.5)보다 아침(5.6)이 **60% 여유** |
| **어디가 부족한가** | 논현2동 4.4만 명에 **13면** (기대 186면) |

**답할 수 없는 것**: 지금 몇 자리 비었는지(실시간 없음), 민영 포함 총 주차면(비공개)

---

## 시작하기

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # API 키 입력
```

**필요한 API 키**

| 키 | 발급처 | 용도 |
|---|---|---|
| `SEOUL_OPENAPI_KEY` | https://data.seoul.go.kr | 생활인구, 서울 공영주차장 |
| `DATA_GO_KR_KEY` | https://www.data.go.kr | 전국주차장 표준데이터 |
| `SGIS_CONSUMER_KEY/SECRET` | https://sgis.mods.go.kr | 행정동 경계·지오코딩 |
| `KAKAO_REST_API_KEY` | https://developers.kakao.com | (미사용) POI 교차검증용 |

---

## 프로젝트 구조

```
├── config/config.yaml       전역 설정 (시간대·회귀 기준·임계값)
├── data/                    README 참고 → data/README.md
├── src/
│   ├── collect/             수집 5종
│   ├── preprocess/          코드연결·지오코딩·패널생성·검증
│   ├── analysis/            일별추세·탐색·회귀잔차
│   └── utils/               API클라이언트·시간대·공휴일·설정
├── dashboard/               Streamlit 4페이지
├── reports/figures/         분석 그림 5종
├── docs/                    데이터 명세·링크·사전
└── submission/              제출물
```

## 문서

| 문서 | 내용 |
|---|---|
| [data/README.md](./data/README.md) | **데이터 전체 안내** — 출처·컬럼·처리 과정·한계 |
| [PROGRESS.md](./PROGRESS.md) | 일자별 진행 / 트러블슈팅 |
| [docs/data_links.md](./docs/data_links.md) | 다운로드 링크 모음 |

## 알려진 한계

| 한계 | 내용 |
|---|---|
| 민영주차장 없음 | 서울 25개 구 중 2개 구 45건만 공개 → 측정 대상은 **공영주차** |
| 0면 행정동 66개 | 실제 0이나 민영 미개방 영향 혼재 → `has_parking`으로 분리 |
| 실시간 불가 | `CUR_PARKING` 폐지 → 8주 평균 패턴 |
| 생활인구는 대리변수 | 통신 추계치라 **차량 이용자 구분 불가** |
| 테스트 없음 | 기존 테스트는 대상 모듈 삭제로 제거, 신규 미작성 |
