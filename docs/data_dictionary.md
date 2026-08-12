# 데이터 사전

실제 API 응답·파일로 검증한 컬럼 명세. 최종 확인 2026-08-12.

---

## 1. 생활인구 (`SPOP_LOCAL_RESD_DONG`)
`data/raw/living_population/YYYYMMDD.csv` — **32컬럼 / 하루 10,176행** (424동 × 24시간)

### 키 컬럼
| 컬럼 | 설명 |
|---|---|
| `STDR_DE_ID` | 기준일 (YYYYMMDD) |
| `TMZON_PD_SE` | **시간대 (0~23)** — 5구간(10~24시) 집계의 기준 |
| `ADSTRD_CODE_SE` | 행정동코드 (통계청 체계) |
| `TOT_LVPOP_CO` | **총 생활인구수** |

### 연령·성별 컬럼 (28개)
`MALE_F{시작}T{끝}_LVPOP_CO` / `FEMALE_F{시작}T{끝}_LVPOP_CO`

구간: `0T9`, `10T14`, `15T19`, `20T24`, `25T29`, `30T34`, `35T39`, `40T44`, `45T49`, `50T54`, `55T59`, `60T64`, `65T69`, `70T74`

**20~30대 비중 산출** (가설 3 검증용) — 아래 8개 합 ÷ `TOT_LVPOP_CO`
```
MALE_F20T24  MALE_F25T29  MALE_F30T34  MALE_F35T39
FEMALE_F20T24  FEMALE_F25T29  FEMALE_F30T34  FEMALE_F35T39
```

⚠️ 값이 실수형(추계치)이며 지수표기로 읽힐 수 있으니 `float`로 처리할 것.

---

## 2. 서울 공영주차장 (`GetParkInfo`) — **보충용**
`data/raw/parking_seoul.csv` — **2,189건 / 총 61,035면**

> 초기에는 주(主) 데이터였으나 **1면짜리 거주자우선 구획**이 다수 섞여 있어 §4로 교체했습니다.
> 지금은 표준데이터로 0면이 되는 동에만 보충 투입합니다(**43개 동**, 거주자우선·버스전용 제외).

| 컬럼 | 설명 | 용도 |
|---|---|---|
| `PKLT_CD` | 주차장코드 | 키 |
| `PKLT_NM` | 주차장명 | |
| `ADDR` | 주소 | |
| **`TPKCT`** | **총 주차면수** | **공급 변수** |
| **`LAT` / `LOT`** | 위도 / 경도 | **행정동 공간조인** |
| `PRK_CRG` / `PRK_HM` | 주차요금 / 기준시간 | 요금 변수 |
| `ADD_CRG` / `ADD_UNIT_TM_MNT` | 추가요금 / 추가단위시간 | |
| `DLY_MAX_CRG` | 일 최대요금 | |
| `MNTL_CMUT_CRG` | 월정기권 요금 | |
| `PKLT_KND_NM` | 노상(1,662) / 노외(527) | |
| `OPER_SE_NM` | 운영구분 — **전부 공영** | |
| `CHGD_FREE_NM` | 유료 / 무료 | |
| `PRK_NOW_INFO_PVSN_YN` | 실시간 정보 제공 여부 | |
| `WD_OPER_BGNG_TM` / `WD_OPER_END_TM` | 평일 운영 시작/종료 | |
| `WE_OPER_BGNG_TM` / `WE_OPER_END_TM` | 주말 운영 시작/종료 | |

⚠️ **`CUR_PARKING`(현재주차대수)은 폐지** — 실시간 여유율 산출 불가.
⚠️ **행정동 코드 없음.** 게다가 `LAT`/`LOT`이 **33.5% 결측**이라 공간조인이 불안정합니다.
→ 주소 기반 **SGIS 지오코딩**(`addr/geocodewgs84`)으로 배정했습니다. 이 API는 좌표와 함께
행정동코드를 직접 반환하므로 공간조인 자체가 불필요합니다. 배정률 100%.

---

## 3. 행정동 경계 (SGIS `hadmarea.geojson`)
`data/external/dong_boundary.geojson` — **426개 행정동**

| 컬럼 | 설명 |
|---|---|
| `adm_cd` | 행정동코드 |
| `adm_nm` | 행정동명 (예: `서울특별시 종로구 사직동`) |
| `x` / `y` | 중심점 좌표 |
| `geometry` | 경계 폴리곤 |

⚠️ **`low_search=2` 필수.** 미지정 시 자치구 25개만 반환됨.
⚠️ `adm_nm`이 `시도 시군구 행정동` 형태이므로 자치구 추출 시 분리 필요.

---

## 4. 전국주차장 표준데이터 — **주(主) 주차 데이터**
`data/raw/parking_standard.csv` — **34컬럼 / 서울분 856건 / 총 73,796면**

API 응답 컬럼은 영문 축약형입니다. 실호출로 검증했습니다.

| 컬럼 | 설명 | 용도 |
|---|---|---|
| `prkplceNo` | 주차장관리번호 | 키 |
| `prkplceNm` | 주차장명 | |
| `prkplceSe` | 주차장구분 — 공영 / 민영 | 민영 45건뿐 |
| `prkplceType` | 주차장유형 — 노상 / 노외 / 부설 | |
| `rdnmadr` / `lnmadr` | 도로명 / 지번 주소 | **지오코딩 입력** |
| **`prkcmprt`** | **주차구획수** | **공급 변수** |
| **`latitude` / `longitude`** | 위도 / 경도 | 보조 (5.7% 결측) |
| `basicTime` / `basicCharge` | 주차기본시간 / 기본요금 | 요금 변수 |
| `addUnitTime` / `addUnitCharge` | 추가단위시간 / 추가단위요금 | |
| `dayCmmtkt` / `monthCmmtkt` | 1일주차권 / 월정기권 요금 | |
| `feedingSe` | 유료 / 무료 | |
| `institutionNm` / `insttCode` | 관리기관 | |
| `referenceDate` | 데이터 기준일 | |

⚠️ 수집 범위가 정의상 **"거주지우선주차지역 제외"** 라 방문객 주차 분석에 적합합니다.
⚠️ **행정동 코드 없음** → 주소 기반 SGIS 지오코딩으로 배정(배정률 100%).

---

## 5. 상권분석 CSV 4종
`data/external/commercial/` — 사용 분기 **20261**. 로더 `load_commercial.py`(인코딩 자동판별).

| 파일 | 데이터셋 | 행수 | 쓰는 컬럼 |
|---|---|---|---|
| `점포_행정동.csv` | OA-22172 | 176,531 | `서비스_업종_코드_명`, `전체_점포_수` |
| `집객시설_행정동.csv` | OA-22169 | 8,925 | `집객시설_수` |
| `상주인구_행정동.csv` | OA-22183 | 8,925 | `총_상주인구_수` |
| `직장인구_행정동.csv` | OA-22184 | 8,694 | `총_직장_인구_수` |

공통 키: `기준_년분기_코드`, `행정동_코드`, `행정동_코드_명`

⚠️ 점포 파일은 **업종 100종 × 행정동** 구조입니다. 음식점 8업종·카페 2업종만 걸러 합산합니다.
⚠️ 직장인구는 **414개 동만 제공**됩니다.
⚠️ 행정동코드가 **행정안전부 체계**라 SGIS 경계와 불일치 → `dong_code.py` 크로스워크 경유.

---

## 6. 인구주택총조사 (거처의 종류별 가구)
`data/external/census/거처종류별가구_행정동.csv` — KOSIS 수동 다운로드 (**저장소에 없음**)

헤더 2줄(연도/항목)을 건너뛰고 읽습니다. 비공개는 `X`로 표기되며 결측 처리합니다.

| 컬럼(내부명) | 설명 |
|---|---|
| `census_nm` | 행정동명 (**자치구 컬럼이 없음**) |
| **`households`** | **일반가구 수** |
| `house_total` | 주택 계 |
| `detached` / **`apartment`** / `rowhouse` / `multiplex` | 단독 / **아파트** / 연립 / 다세대 |
| `nonresidential` / `non_house` | 비거주용 건물 내 주택 / 주택 이외의 거처 |

파생: `non_apt_households = households − apartment`, `apt_ratio = apartment / households`

⚠️ **합산이 아니라 차감**으로 구합니다. 연립 12.1%·다세대 7.0%·단독 6.1%가 `X`라
합산하면 결측이 전파되지만, `households`·`apartment`는 각각 0건·2건만 `X`입니다 (결측 11개 → 2개).
⚠️ 동명만으로 매칭하므로 중복동(신사동)·통합동(용신동·상일1동)·미제공동(항동)을 별도 처리합니다.
로더: `src/preprocess/load_census.py`

---

## 7. 최종 산출 테이블

### `data/processed/panel.csv` — **14,840행 × 31열**
행정동 424 × 요일 7 × 시간대 **5**

| 컬럼 | 설명 | 출처 |
|---|---|---|
| `adm_cd` | 행정동코드 (**SGIS 체계**) | 경계 |
| `admi_cd` | 행정동코드 (**행안부 체계**) | 코드표 |
| `adm_nm` / `sgg_nm` / `admi_nm` | 풀네임 / 자치구 / 행정동명 | 경계 |
| `weekday` / `is_weekend` | 요일 / 주말 여부 | 파생 |
| `timeslot` | 오전·점심·오후·저녁·밤 | 파생 |
| `living_pop` | 총 생활인구 (56일 평균, 공휴일 제외) | 생활인구 |
| `young_pop` / `young_ratio` | 20~30대 인구 / 비중 | 생활인구 |
| `parking_slots` / `parking_lots` | **공영주차면수** / 주차장 개소 | 주차장 |
| `avg_fee_per_hour` | 시간당 평균 요금 | 주차장 |
| `source` | `standard`(315동) / `seoul_api`(43동) / `none`(66동) | 파생 |
| `has_parking` | 공영주차면 > 0 여부 | 파생 |
| `store_food` / `store_cafe` / `facility_cnt` | 음식점 / 카페 / 집객시설 | 상권 |
| `resident_pop` / `worker_pop` | 상주인구 / 직장인구 | 상권 |
| `households` / `apartment` / `non_apt_households` / `apt_ratio` | 가구·아파트·비아파트·아파트비율 | 총조사 |
| `detached` / `rowhouse` / `multiplex` / `non_house` | 단독 / 연립 / 다세대 / 주택이외 | 총조사 |
| **`slots_per_1k`** | **1,000명당 주차면** = `parking_slots / living_pop × 1000` | 파생 |
| **`slots_per_100_nonapt`** | **비아파트 100가구당 주차면** | 파생 |

### 분석 산출물

| 파일 | 스크립트 | 행수 | 핵심 컬럼 |
|---|---|---|---|
| `dong_residual.csv` | `residual.py` | 358 | `expected_slots` `supply_ratio` **`z_residual`** `grade` |
| `dong_timeslot.csv` | `timeslot_effect.py` | 358 | 동별 최적 시점·개선율 |
| `dong_suitability.csv` | `suitability.py` | 357 | `매력도지수`(PC1) `주차여유지수`(PC2) **`나들이적합도`** |
| `dong_recommend.csv` | `recommend.py` | 423 | `등급` `종합점수` |
| `dong_real_demand.csv` | `real_demand.py` | 422 | 비아파트 가구 기준 실수요 진단 |
| `dong_cluster.csv` | `cluster.py` | — | `유형` (**저장소에 미포함**) |
| `sgg_summary.csv` | `district.py` | 25 | 자치구 단위 요약 |

**행수가 제각각인 이유** (424개 동 기준)

| 산출물 | 계산 | 이유 |
|---|---|---|
| 358 | 424 − 0면 66 | 회귀선을 그을 수 없고, 포함하면 "취약 1위"가 전부 0면 동으로 채워짐 |
| 357 | 358 − 상권 결측 1 | 지수에 음식점·카페가 들어감 |
| 423 | 424 − 상권 결측 1 | **0면 66개 동을 남김** — `등급`에 "공영주차 없음"으로 따로 표시 |
| 422 | 424 − 총조사 결측 2 | 아파트 가구가 비공개(`X`)인 2개 동 |

> 진단 계열(423·422)이 0면 동을 남기는 것은 의도된 것입니다.
> 0면은 숨겨야 할 결측이 아니라 **이용자가 가장 먼저 알아야 할 사실**이기 때문입니다.
> (문정2동은 음식점 821개에 공영주차 0면이라 혼잡주의 1위보다 사정이 나쁩니다)

> `grade` 기준은 표준화 잔차 −1 이하 **공급부족** / +1 이상 **공급여유** (`config.yaml`).
> `나들이적합도`는 두 지수 백분위의 **기하평균** — 한쪽만 높으면 크게 떨어집니다(병목 반영).
