# 수집 데이터 명세

최종 분석 단위: **행정동 × 요일 × 시간대 = 1행**
(행정동 약 425개 × 요일 7 × 시간대 4 = 약 11,900행)

---

## 1. 수집 대상 데이터 6종

| # | 데이터 | 출처 | 인증키 | 시간 해상도 | 산출물 |
|---|---|---|---|---|---|
| 1 | 우리마을 생활인구 | 서울 열린데이터광장 `SPOP_LOCAL_RESD_DONG` | `SEOUL_OPENAPI_KEY` | 일 × 1시간 | `data/raw/living_population/YYYYMMDD.csv` |
| 2 | 공영주차장 안내정보 | 서울 열린데이터광장 `GetParkInfo` | `SEOUL_OPENAPI_KEY` | 정적 | `data/raw/parking_lots.csv` |
| 3 | 시영주차장 실시간 주차대수 | 서울 열린데이터광장 OA-21709 | `SEOUL_OPENAPI_KEY` | 5분 (폴링 누적) | `data/raw/parking_snapshots/YYYYMMDD_HHMM.csv` |
| 4 | POI (음식점/카페/문화시설/관광명소) | 카카오 로컬 API | `KAKAO_REST_API_KEY` | 정적 | `data/raw/poi_counts.csv` |
| 5 | 행정동 경계 | SGIS `hadmarea.geojson` | `SGIS_CONSUMER_KEY/SECRET` | 정적 | `data/external/dong_boundary.geojson` |
| 6 | 자치구별 등록차량 | 서울 열린데이터광장 `TbCarRegistNum` | `SEOUL_OPENAPI_KEY` | 월 | `data/raw/registered_vehicles.csv` |

---

## 2. 각 데이터의 역할

### ① 생활인구 — **수요 / 혼잡도 (핵심 변수)**
- 행정동별 1시간 단위 체류인구. 요일×시간대 패널의 뼈대.
- 4주(28일) 수집 → 요일별 4개 표본 평균으로 대표값 산출.
- **주의**: 집계 지연이 있어 최근 날짜는 데이터 없음. 기본 60일 전 기준으로 수집.

### ② 공영주차장 안내정보 — **공급 (총주차면수)**
- 서울시 약 14,000개 노상·노외 주차장. 위경도 → 행정동 공간조인으로 배분.
- 행정동별 `parking_supply` (총 주차면수) 산출.

### ③ 시영주차장 실시간 주차대수 — **실측 여유율**
- `여유율 = (총면수 - 현재주차대수) / 총면수`
- ⚠️ **커버리지 제한**: 시영주차장만 대상 (전체 14,000개 대비 극히 일부).
  → 커버되는 행정동만 실측, 나머지는 생활인구 기반 추정치로 대체.
- ⚠️ 서비스명 미검증 (`config.yaml`의 `parking_realtime`, 포털 확인 필요).

### ④ POI — **놀거리 매력도**
- 행정동 중심점 반경 500m 내 카테고리별 장소 수 (`meta.total_count` 활용).
- 카테고리: `FD6` 음식점 / `CE7` 카페 / `CT1` 문화시설 / `AT4` 관광명소
- "주차 여유 있으면서 놀거리도 많은 동" 추천의 근거.

### ⑤ 행정동 경계 — **지도 시각화 + 공간조인 기준**
- 주차장·POI 좌표를 행정동에 배분할 때, 그리고 대시보드 지도 렌더링에 사용.

### ⑥ 등록차량 — **보조 지표**
- 자치구 단위만 제공 → 행정동 배분 시 인구 비례 보정 필요. 상관분석 변수로 활용.

---

## 3. 최종 분석 테이블 스키마

### `data/processed/panel.csv` (메인)

| 컬럼 | 타입 | 설명 | 출처 |
|---|---|---|---|
| `adm_dong_cd` | str | 행정동코드 | ⑤ |
| `adm_dong_nm` | str | 행정동명 | ⑤ |
| `gu_nm` | str | 자치구명 | ⑤ |
| `weekday` | str | 요일 (월~일) | 파생 |
| `is_weekend` | bool | 주말 여부 | 파생 |
| `timeslot` | str | 시간대 (아침/점심/오후/저녁밤) | 파생 |
| `living_pop` | float | 평균 생활인구 | ① |
| `parking_supply` | int | 총 주차면수 | ② |
| `parking_occupied` | float | 평균 주차 점유대수 (실측) | ③ |
| `parking_vacancy_rate` | float | **주차 여유율** | ②③ |
| `is_vacancy_observed` | bool | 실측 여부 (False면 추정치) | ③ |
| `poi_음식점` / `poi_카페` / `poi_문화시설` / `poi_관광명소` | int | 카테고리별 POI 수 | ④ |
| `poi_total` | int | POI 합계 | ④ |
| `registered_vehicles` | float | 등록차량 (자치구 배분) | ⑥ |

### `data/processed/dong_summary.csv` (심화 분석용)
행정동 단위 집계 (요일·시간대 평균) + PCA 주성분 + 군집 라벨.

---

## 4. 대시보드 매핑

| 대시보드 요소 | 사용 컬럼 |
|---|---|
| **사이드바 필터** | `weekday`, `timeslot`, `gu_nm` |
| **KPI ①** 평균 생활인구 | `living_pop` (필터 조건 평균) |
| **KPI ②** 주차 여유율 | `parking_vacancy_rate` |
| **KPI ③** 전체 평균 대비 delta | 위 두 값 vs 전체 평균 차이 |
| **그래프 ①** 시간대별 생활인구 곡선 | `timeslot` × `living_pop` |
| **그래프 ②** 자치구별 막대 | `gu_nm` × `living_pop` / `parking_vacancy_rate` |
| **심화 ①** 상관 히트맵 | 수치형 컬럼 전체 |
| **심화 ②** PCA 군집 | `dong_summary.csv` |
| **심화 ③** 지도 | `dong_boundary.geojson` + `parking_vacancy_rate` |

---

## 5. 수집 실행 순서

```bash
# 정적 데이터 (1회)
python -m src.collect.fetch_dong_boundary        # 다른 수집의 선행 조건
python -m src.collect.fetch_parking_lots
python -m src.collect.fetch_registered_vehicles
python -m src.collect.fetch_poi_kakao            # 경계 파일 필요

# 시계열 데이터
python -m src.collect.fetch_living_population --days 28
python -m src.collect.fetch_parking_realtime     # 하루 4회 스케줄 폴링
```

---

## 6. 알려진 한계

1. **실시간 주차 커버리지** — 시영주차장만 실측 가능. 대부분 행정동은 추정치.
2. **생활인구 집계 지연** — 약 1~2개월. "실시간 혼잡도"가 아닌 **요일×시간대 평균 패턴**.
3. **등록차량 해상도** — 자치구 단위만 제공, 행정동 배분은 인구 비례 가정.
4. **POI 반경 방식** — 행정동 중심점 반경 500m 기준이라 면적이 큰 동은 과소 집계 가능.
