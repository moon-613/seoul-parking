# 수집 데이터 명세

최종 분석 단위: **행정동 × 요일 × 시간대 = 1행**
(행정동 약 425개 × 요일 7 × 시간대 4 ≈ 11,900행)

최종 확인일: 2026-08-10

---

## 1. 데이터 소스 현황

| # | 데이터 | 출처 | 인증키 | 상태 |
|---|---|---|---|---|
| ① | 생활인구 (행정동×시간대) | 서울 열린데이터광장 `SPOP_LOCAL_RESD_DONG` | `SEOUL_OPENAPI_KEY` | ✅ 작동 확인 |
| ② | 공영주차장 | 서울 열린데이터광장 `GetParkInfo` | `SEOUL_OPENAPI_KEY` | ✅ 작동 확인 (2,189건) |
| ③ | 전국주차장 표준데이터 (**민영 포함**) | 공공데이터포털 `tn_pubr_prkplce_info_api` | `DATA_GO_KR_KEY` | ⚠️ **서버 장애** |
| ④ | 상권분석 4종 | 서울 열린데이터광장 CSV | 불필요 | ⬜ 수동 다운로드 |
| ⑤ | 행정동 경계 | SGIS `hadmarea.geojson` | `SGIS_CONSUMER_KEY/SECRET` | ⬜ 키 발급 대기 |
| ⑥ | POI (보조) | 카카오 로컬 API | `KAKAO_REST_API_KEY` | ✅ 키 보유 |

---

## 2. 각 소스 상세

### ① 생활인구 — 수요·혼잡도 (핵심 변수)
- 행정동별 **1시간 단위** 체류인구. 요일×시간대 패널의 뼈대.
- 연령대별·성별 컬럼으로 **20~30대 비중** 산출.
- ⚠️ **OpenAPI는 최근 2개월분만 제공** + 집계 지연 존재.
  → 그보다 과거가 필요하면 월별 ZIP(`LOCAL_PEOPLE_DONG_YYYYMM.zip`) 다운로드.
- 스크립트: `src/collect/fetch_living_population.py`

### ② 서울 공영주차장 — 공급 (기본)
2026-08-10 전량 수집 실측:

| 항목 | 값 |
|---|---|
| 건수 | 2,189건 |
| 총 주차면 | **61,035면** |
| 노상 / 노외 | 1,662 / 527 |
| 운영구분 | 시간제 1,995 · 시간제+거주자 115 · 버스전용 70 · 거주자우선 7 · 기타 2 |

- ⚠️ **전부 공영. 민영 0건.** → 공급 과소추정 요인.
- ⚠️ `CUR_PARKING`(현재주차대수)은 **폐지**되어 실시간 여유율 산출 불가.
- 주요 컬럼: `TPKCT`(총주차면) · `LAT`/`LOT`(위경도) · `PRK_CRG`·`ADD_CRG`·`DLY_MAX_CRG`(요금)
- 스크립트: `src/collect/fetch_parking_seoul.py`

### ③ 전국주차장 표준데이터 — 민영 포함 (⚠️ 장애)
민영주차장을 포함하는 **유일한 경로**이나, 2026-08-10 기준 양쪽 모두 서버 장애:

| 경로 | 결과 |
|---|---|
| 파일 다운로드 `/download/columList.json` | **HTTP 500** |
| 오픈 API `tn_pubr_prkplce_info_api` | **HTTP 504** (60초 후) |

- 세션 쿠키·`publicDataPk`·`Referer` 정상 구성 후에도 동일 → **서버측 문제 확정**
- 복구 확인: `python -m src.collect.fetch_parking_standard --probe`
- ⚠️ `.env`의 키는 **Encoding 키**(`%` 포함)이므로 재인코딩하면 403
- 스크립트: `src/collect/fetch_parking_standard.py`

### ④ 상권분석 CSV — 매력도 변수
**"-행정동" 버전(OA-22xxx)** 을 받아 `data/external/commercial/` 에 배치:

| 파일명 | 내용 | 참고 |
|---|---|---|
| `점포_행정동.csv` | 음식점·카페 점포 수 | OA-22172 |
| `집객시설_행정동.csv` | 영화관·문화시설 수 | 검색 필요 |
| `상주인구_행정동.csv` | 동네 성격 구분 | 검색 필요 |
| `직장인구_행정동.csv` | 동네 성격 구분 | OA-22184 |

- ⚠️ **"-상권"(OA-15xxx)은 공간 단위가 달라 행정동 조인 불가**
- 2024년 표준단위구역 전환 / 2026-07-03부터 2021년 이후 자료만 제공
- 검색: https://data.seoul.go.kr/dataList/datasetList.do?srchKeyword=상권분석
- 로더: `src/preprocess/load_commercial.py`

### ⑤ 행정동 경계 — 공간조인 기준 (필수 선행)
- 주차장 데이터에 **행정동 코드가 없어** 위경도 공간조인이 필수. 시각화용이 아님.
- SGIS 사용 이유: 서울 열린데이터광장 경계 파일은 **2016년 기준**이라 행정동 통폐합 불일치 발생.
- ⚠️ 도메인 이전: `sgis.kostat.go.kr` → **`sgis.mods.go.kr`**
- 스크립트: `src/collect/fetch_dong_boundary.py`

### ⑥ 카카오 POI — 보조 (교차검증)
- 상권분석은 **분기 고정**, 카카오는 **현재 시점** → 두 값을 비교해 데이터 신뢰도 검증 섹션 구성.
- 행정동 중심점 반경 500m 내 카테고리별 개수(`meta.total_count`).
- ⚠️ 면적이 큰 동은 과소집계 → 주 변수가 아닌 보조로만 사용.
- 스크립트: `src/collect/fetch_poi_kakao.py`

---

## 3. 분석 변수 (기획서 기준 10개)

| 구분 | 변수 | 출처 |
|---|---|---|
| 인구 | 총생활인구, 20~30대 비중 | ① |
| 인구 | 상주인구, 직장인구 | ④ |
| 상권 | 음식점 수, 카페 수, 집객시설 수 | ④ |
| 주차 | 주차면수, 1인당 주차면수, 평균 주차요금 | ②(+③) |

---

## 4. 실행 순서

```bash
# 1) 경계 (다른 수집의 선행 조건)
python -m src.collect.fetch_dong_boundary

# 2) 주차 공급
python -m src.collect.fetch_parking_seoul              # 공영 (즉시 가능)
python -m src.collect.fetch_parking_standard --probe   # 민영 API 생존 확인
python -m src.collect.fetch_parking_standard           # 복구 시에만

# 3) 생활인구 (4주)
python -m src.collect.fetch_living_population --days 28

# 4) 상권 CSV 확인 (수동 배치 후)
python -m src.preprocess.load_commercial

# 5) POI (보조)
python -m src.collect.fetch_poi_kakao
```

---

## 5. 알려진 한계

1. **민영주차장 누락** — 포털 장애로 공영(61,035면)만 확보 시 공급 과소추정.
2. **실시간 주차 불가** — `CUR_PARKING` 폐지. 구조적 과부족(회귀 잔차)으로 대체.
3. **생활인구 가용기간** — OpenAPI 최근 2개월 + 집계 지연.
4. **행정동코드 불일치** — 생활인구(통계청) vs 상권분석(행안부) 체계 상이. 통폐합 결측 점검 필요.
5. **POI 반경 방식** — 면적 큰 동 과소집계 (보조 변수로만 사용).
