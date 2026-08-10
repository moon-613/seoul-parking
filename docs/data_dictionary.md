# 데이터 사전 (Data Dictionary)

수집/전처리가 진행되며 실제 API 응답 컬럼명으로 계속 업데이트할 것.

## 1. 생활인구 (서울 열린데이터광장 - SPOP_LOCAL_RESD_DONG)
| 컬럼(예상) | 설명 |
|---|---|
| STDR_DE_ID | 기준일ID (YYYYMMDD) |
| TMZON_PD_SE | 시간대 구분 |
| ADSTRD_CODE_SE | 행정동코드 |
| TOT_LVPOP_CO | 총 생활인구 수 |

- 출처: https://data.seoul.go.kr (서비스명 SPOP_LOCAL_RESD_DONG)

## 2. 주차장 안내 정보 (GetParkInfo)
| 컬럼(예상) | 설명 |
|---|---|
| PARKING_CODE | 주차장관리번호 |
| PARKING_NAME | 주차장명 |
| ADDR | 주소 |
| LAT / LOT | 위도/경도 |
| TPKCT | 총 주차대수(면수) |

## 3. 자치구별 자동차 등록현황 (TbCarRegistNum)
| 컬럼(예상) | 설명 |
|---|---|
| GU_NM | 자치구명 |
| CAR_CNT | 등록차량대수 |

## 4. 행정동 경계 (SGIS hadmarea)
| 컬럼(예상) | 설명 |
|---|---|
| adm_dong_cd | 행정동코드 |
| adm_dong_nm | 행정동명 |
| geometry | 폴리곤 (경계) |

## 5. 분석 산출 테이블

### data/processed/dong_master.csv
행정동코드 기준 병합 결과 (생활인구 + 주차공급 + 등록차량)

### data/processed/imbalance_index.csv
| 컬럼 | 설명 |
|---|---|
| adm_dong_cd | 행정동코드 |
| adm_dong_nm | 행정동명 |
| parking_demand | 추정 주차수요 |
| parking_supply | 주차면수(공급) |
| imbalance_ratio | 수요/공급 비율 (불균형 지수) |
| is_vulnerable | 취약지역 여부 (상위 20%) |
