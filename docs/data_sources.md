# 수집 데이터 명세

최종 분석 단위: **행정동 × 요일 × 시간대 = 1행**
실측 **14,840행 × 31열** (424개 동 × 요일 7 × 시간대 **5**)

최종 확인일: 2026-08-12

> 수집 이후 방향이 세 번 바뀌었습니다. 이 문서는 **바뀐 뒤 기준**입니다.
> ① 주차 주(主) 데이터가 서울시 API → **전국주차장 표준데이터**로 교체
> ② 실시간 주차 불가 확인 → **구조적 과부족(회귀 잔차)** 으로 전환
> ③ 시간대 **4구간 → 5구간** 개편, **인구주택총조사** 결합(실수요 보정)
> 경위는 `PROGRESS.md`와 `config/config.yaml` 주석 참고.

---

## 1. 데이터 소스 현황

| # | 데이터 | 출처 | 인증키 | 상태 |
|---|---|---|---|---|
| ① | 생활인구 (행정동×시간대) | 서울 열린데이터광장 `SPOP_LOCAL_RESD_DONG` | `SEOUL_OPENAPI_KEY` | ✅ 56일 수집 완료 |
| ② | 전국주차장 표준데이터 (**주 데이터**) | 공공데이터포털 `tn_pubr_prkplce_info_api` | `DATA_GO_KR_KEY` | ✅ 856건 (장애 복구됨) |
| ③ | 서울시 공영주차장 (**보충용**) | 서울 열린데이터광장 `GetParkInfo` | `SEOUL_OPENAPI_KEY` | ✅ 2,189건 |
| ④ | 상권분석 4종 | 서울 열린데이터광장 CSV | 불필요 | ✅ 수동 다운로드 완료 |
| ⑤ | 인구주택총조사 (거처종류별 가구) | KOSIS CSV | 불필요 | ✅ 수동 다운로드 |
| ⑥ | 행정동 경계 | SGIS `hadmarea.geojson` | `SGIS_CONSUMER_KEY/SECRET` | ✅ 426개 폴리곤 |
| ⑦ | 전국 행정동 코드정보 | 서울 열린데이터광장 CSV | 불필요 | ✅ 43개월분 |
| ⑧ | POI (보조) | 카카오 로컬 API | `KAKAO_REST_API_KEY` | ❌ 403 — 미사용 |

---

## 2. 각 소스 상세

### ① 생활인구 — 수요·혼잡도 (핵심 변수)

| 항목 | 값 |
|---|---|
| 기간 | 2026-06-02 ~ 07-27 (**56일** = 7개 요일 × 각 8일) |
| 규모 | 56개 파일 / 하루 10,176행 / **157.1MB** (파일당 2.8MB) |

- 행정동별 **1시간 단위** 체류인구. 요일×시간대 패널의 뼈대.
- 연령대별·성별 컬럼으로 **20~30대 비중** 산출.
- ⚠️ **API 제공 구간 실측**: 7일전 0건(집계 지연) / 14~70일전 정상 / 80일전 이상 0건
  → 가용 폭이 약 57일뿐이라 **56일이 사실상 최대치**입니다.
  그보다 과거가 필요하면 월별 ZIP(`LOCAL_PEOPLE_DONG_YYYYMM.zip`)을 받아야 합니다.
- 평일에 낀 **공휴일 2일 제외** (지방선거 6/3, 제헌절 7/17). 판정은 `src/utils/holidays.py`.
- 스크립트: `src/collect/fetch_living_population.py`

### ② 전국주차장 표준데이터 — 공급 (주 데이터)

수집 범위가 정의상 **"거주지우선주차지역 제외"** 라 방문객 주차 분석에 적합합니다.

| 항목 | 값 |
|---|---|
| 서울분 건수 | 856건 |
| 총 주차면 | **73,796면** |
| 행정동 배정률 | 100% (856/856) |

- 초기에는 ③을 주 데이터로 썼으나, 검증 중 ③이 **1면짜리 거주자우선 구획**을 다수 포함함을 발견해 교체했습니다.
  ```
  서교동(홍대)   서울시 API:   6면  ← 1면짜리 거주자우선 구획
                 표준데이터 : 152면  ← 실제 주차장
  ```
- ⚠️ 2026-08-10 한때 HTTP 500/504 장애였으나 **복구 후 수집 성공**했습니다.
  생존 확인: `python -m src.collect.fetch_parking_standard --probe`
- ⚠️ `.env`의 키는 **Encoding 키**(`%` 포함)이므로 재인코딩하면 403입니다.
- ⚠️ **민영은 45건(1,149면)뿐**입니다 (구로구 39 · 금천구 6, 나머지 23개 구는 0건). §5 참고.
- 스크립트: `src/collect/fetch_parking_standard.py`

### ③ 서울시 공영주차장 — 공급 (보충용)

②만으로는 424개 동 중 **109개(26%)가 주차면 0**이 되어, 0면 동에 한해 보충했습니다.

| 항목 | 값 |
|---|---|
| 건수 | 2,189건 / 총 61,035면 |
| 노상 / 노외 | 1,662 / 527 |
| 운영구분 | 시간제 1,995 · 시간제+거주자 115 · 버스전용 70 · 거주자우선 7 · 기타 2 |
| 실제 보충된 동 | **43개** |

- 보충 시 **거주자우선·버스전용은 제외**했고, ②와 겹치는 동이 없어 이중 계산은 없습니다.
- 결과: 0면 동 109개 → **66개**, 공급 73,796 → **78,267면**
- ⚠️ `CUR_PARKING`(현재주차대수)은 **폐지**("추후 제공예정 없음")되어 실시간 여유율 산출 불가.
- 주요 컬럼: `TPKCT`(총주차면) · `LAT`/`LOT`(위경도) · `PRK_CRG`·`ADD_CRG`·`DLY_MAX_CRG`(요금)
- 스크립트: `src/collect/fetch_parking_seoul.py`

### ④ 상권분석 CSV — 매력도·동네 성격 변수
**"-행정동" 버전(OA-22xxx)** 을 받아 `data/external/commercial/` 에 배치. 사용 분기 **20261**.

| 파일명 | 데이터셋 | 행수 | 쓰는 컬럼 |
|---|---|---|---|
| `점포_행정동.csv` | OA-22172 | 176,531 | `서비스_업종_코드_명`, `전체_점포_수` |
| `집객시설_행정동.csv` | OA-22169 | 8,925 | `집객시설_수` |
| `상주인구_행정동.csv` | OA-22183 | 8,925 | `총_상주인구_수` |
| `직장인구_행정동.csv` | OA-22184 | 8,694 | `총_직장_인구_수` |

- ⚠️ **"-상권"(OA-15xxx)은 공간 단위가 달라 행정동 조인 불가**
- ⚠️ 점포 파일은 **업종 100종 × 행정동** 구조라 행이 많습니다. 음식점 8업종·카페 2업종만 걸러 합산합니다.
- ⚠️ 직장인구는 **414개 동만 제공**됩니다.
- 2024년 표준단위구역 전환 / 2026-07-03부터 2021년 이후 자료만 제공
- 실제 경로는 `config.yaml`의 `commercial.files`가 관리합니다.
- 로더: `src/preprocess/load_commercial.py` (인코딩 자동판별)

### ⑤ 인구주택총조사 (거처의 종류별 가구) — 실수요 보정

생활인구만으로 재면 **부설주차장이 있는 아파트 거주자까지 수요로 계산**됩니다.
공영주차 실수요는 부설주차장이 없는 가구에서 주로 나오므로 아파트를 뺀 가구 수를 따로 잡습니다.

- 출처: KOSIS 「인구주택총조사 — 거처의 종류별 가구」, 서울 **행정동(최하위 레벨)** 선택
- 배치: `data/external/census/거처종류별가구_행정동.csv` (**수동 다운로드, 저장소에 없음**)
- 매칭: 427행 → 424개 행정동 **100%**
- ⚠️ 소분류가 비공개(`X`)라 **합산이 아니라 차감**으로 구합니다 — `비아파트 = 일반가구 − 아파트`
  (연립 12.1%·다세대 7.0%·단독 6.1%가 `X`. 차감하면 결측 11개 → 2개)
- ⚠️ 원본에 자치구 컬럼이 없어 **동명만으로 매칭**합니다. 동명 중복(신사동)·통합동(용신동)·
  패널에 없는 동(항동)을 별도 처리합니다.
- 로더: `src/preprocess/load_census.py`

### ⑥ 행정동 경계 — 지오코딩 검증·지도 표시
- SGIS 사용 이유: 서울 열린데이터광장 경계 파일은 **2016년 기준**이라 행정동 통폐합 불일치 발생.
- 규모: 426개 폴리곤 / 1.0MB
- ⚠️ 도메인 이전: `sgis.kostat.go.kr` → **`sgisapi.mods.go.kr`**
- ⚠️ `low_search=2` 미지정 시 **자치구 25개만** 반환됩니다.
- ⚠️ 헤더는 CRS84(경위도)로 선언되어 있으나 실제로는 **UTM-K 미터 좌표**입니다.
  좌표값으로 판별해 EPSG:5179 → 4326 재투영이 필요합니다.
- 스크립트: `src/collect/fetch_dong_boundary.py`

### ⑦ 전국 행정동 코드정보 — 코드 크로스워크의 다리
- 생활인구(행안부 `11110530`)와 SGIS 경계(자체 `11010530`)는 체계가 달라 직접 조인 시 424개 중 32개만 맞습니다.
- `ADMI_YYYYMM.csv` 43개월분을 **전부 합쳐** 씁니다 — 통폐합으로 특정 월에만 있는 코드가 있어서(용신동·일원2동).
- 결과: 조인율 **7.5% → 100%** (인구 손실 0명)
- 스크립트: `src/preprocess/dong_code.py`

### ⑧ 카카오 POI — 미사용
- 상권분석(분기 고정)과 카카오(현재 시점)를 비교해 교차검증할 계획이었습니다.
- ⚠️ **앱 서비스 미활성으로 403**입니다. 문서에는 "활성화 불필요"로 적혀 있으나 실제와 다릅니다.
- 코드는 남겨두었고 **분석에는 쓰지 않습니다**.
- 스크립트: `src/collect/fetch_poi_kakao.py`

---

## 3. 분석 변수 (panel.csv 31열)

| 구분 | 변수 | 출처 |
|---|---|---|
| 식별 | `adm_cd` `admi_cd` `adm_nm` `sgg_nm` `admi_nm` | ⑦ |
| 시점 | `weekday` `is_weekend` `timeslot` | 파생 |
| 인구 | `living_pop` `young_pop` `young_ratio` | ① |
| 인구 | `resident_pop` `worker_pop` | ④ |
| 상권 | `store_food` `store_cafe` `facility_cnt` | ④ |
| 거주형태 | `households` `apartment` `non_apt_households` `apt_ratio` `detached` `rowhouse` `multiplex` `non_house` | ⑤ |
| 주차 | `parking_slots` `parking_lots` `avg_fee_per_hour` `source` `has_parking` | ②+③ |
| 파생 | `slots_per_1k` `slots_per_100_nonapt` | 파생 |

컬럼별 정의는 `docs/data_dictionary.md` 참고.

---

## 4. 실행 순서

```powershell
# 1) 경계·코드표 (전처리의 선행 조건)
python -m src.collect.fetch_dong_boundary
python -m src.preprocess.dong_code

# 2) 주차 공급 — 표준데이터가 주(主), 서울시 API가 보충
python -m src.collect.fetch_parking_standard --probe   # 생존 확인
python -m src.collect.fetch_parking_standard
python -m src.collect.fetch_parking_seoul
python -m src.preprocess.geocode_parking --source standard
python -m src.preprocess.geocode_parking --source seoul

# 3) 생활인구 (56일 = 사실상 최대치)
python -m src.collect.fetch_living_population --days 56

# 4) 수동 배치 CSV 확인
python -m src.preprocess.load_commercial
python -m src.preprocess.load_census

# 5) 패널 생성 및 검증
python -m src.preprocess.build_panel --quarter 20261
python -m src.preprocess.validate

# 6) 분석 — residual 을 먼저 돌려야 나머지가 잔차를 읽는다
python -m src.analysis.residual
python -m src.analysis.explore
python -m src.analysis.daily_trend
python -m src.analysis.real_demand
python -m src.analysis.suitability
python -m src.analysis.recommend
python -m src.analysis.timeslot_effect
python -m src.analysis.cluster
python -m src.analysis.district
python -m src.analysis.maps
```

> ⚠️ `geocode_parking.py`는 `parking_geocoded_{source}.csv` 로 저장합니다.
> 두 소스를 **모두** 돌려야 `build_panel.py`가 보충분(43개 동)을 반영합니다.
> 건너뛰면 경고만 남기고 78,267면 → 73,796면으로 줄어듭니다.

---

## 5. 알려진 한계

1. **민영·부설 주차장 누락** — 표준데이터 수집범위가 "지자체 관리 대상"으로 한정되어
   서울 민영은 45건(1,149면)뿐입니다. 주차장법상 통보 의무가 있어 **데이터는 존재하나 미개방**입니다.
   → 측정 대상을 "전체 주차 공급"이 아닌 **"공영주차 접근성"** 으로 한정해 서술합니다.
2. **0면 행정동 66개(15.6%)** — 결측이 아닌 실제 0이나 민영 미개방 영향이 섞여 있습니다.
   `has_parking`으로 분리하고 회귀에서는 제외합니다.
3. **실시간 주차 불가** — `CUR_PARKING` 폐지. 구조적 과부족(회귀 잔차)으로 대체했습니다.
4. **생활인구 가용기간** — API가 약 57일 구간만 제공합니다(§2 ①).
5. **직장인구 414개 동만 제공** — 동네 성격 지표가 일부 동에서 결측입니다.
6. **주차요금(`avg_fee_per_hour`)은 수집만 하고 분석에 쓰지 않았습니다** — 무료·결측 처리 기준을 세우지 못했습니다.
7. **POI 교차검증 미실시** — 카카오 API 403(§2 ⑧).
8. **총조사는 수동 다운로드** — `data/external/census/`가 비어 있으면 패널을 재생성할 수 없습니다.
