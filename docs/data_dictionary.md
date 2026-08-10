# 데이터 사전

실제 API 응답으로 검증한 컬럼 명세. 최종 확인 2026-08-10.

---

## 1. 생활인구 (`SPOP_LOCAL_RESD_DONG`)
`data/raw/living_population/YYYYMMDD.csv` — **32컬럼 / 하루 10,176행** (424동 × 24시간)

### 키 컬럼
| 컬럼 | 설명 |
|---|---|
| `STDR_DE_ID` | 기준일 (YYYYMMDD) |
| `TMZON_PD_SE` | **시간대 (0~23)** — 4구간 집계의 기준 |
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

## 2. 서울 공영주차장 (`GetParkInfo`)
`data/raw/parking_seoul.csv` — **2,189건 / 총 61,035면**

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
⚠️ **행정동 코드 없음** → `LAT`/`LOT` 공간조인 필수.

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

## 4. 전국주차장 표준데이터 (민영 포함) — ⚠️ 서버 장애
`data/raw/parking_standard.csv` (미수집)

문서상 제공 컬럼: `주차장관리번호`, `주차장명`, `주차장구분`(공영/민영), `주차장유형`,
`소재지도로명주소`, `소재지지번주소`, **`주차구획수`**, `급지구분`, `요금정보`,
`주차기본시간`, `주차기본요금`, `추가단위시간`, `추가단위요금`, `1일주차권요금`,
`월정기권요금`, **`위도`**, **`경도`** 등

API 응답 컬럼은 영문 축약형(`rdnmadr`, `lnmadr` 등)이며 **실호출 전까지 미검증**.

---

## 5. 상권분석 CSV 4종 — ⬜ 미수집
`data/external/commercial/` — 컬럼 구조는 다운로드 후 `load_commercial.py`로 확인.

| 파일 | 데이터셋 |
|---|---|
| `점포_행정동.csv` | OA-22172 |
| `집객시설_행정동.csv` | OA-22169 |
| `상주인구_행정동.csv` | OA-22183 |
| `직장인구_행정동.csv` | OA-22184 |

⚠️ 행정동코드가 **행정안전부 체계**라 생활인구(통계청 체계)와 불일치 가능 → 조인 시 대조 필요.

---

## 6. 최종 산출 테이블

### `data/processed/panel.csv`
행정동 × 요일 × 시간대 (≈ 426 × 7 × 4)

| 컬럼 | 출처 |
|---|---|
| `adm_dong_cd`, `adm_dong_nm`, `gu_nm` | 경계 |
| `weekday`, `is_weekend`, `timeslot` | 파생 |
| `living_pop`, `young_ratio` | 생활인구 |
| `parking_supply`, `parking_per_capita`, `avg_parking_fee` | 주차장 |
| `store_food`, `store_cafe`, `facility_cnt` | 상권 |
| `resident_pop`, `worker_pop` | 상권 |

### `data/processed/dong_summary.csv`
행정동 단위 집계 + 회귀 표준화 잔차(`residual`) + PCA 주성분 + 군집 라벨
