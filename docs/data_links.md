# 데이터 링크 모음

모든 링크는 2026-08-10 접속 확인. 상태는 실제 호출/접속 결과.

---

## 1. 수동 다운로드 (지금 받아야 할 것)

### 상권분석 CSV 4종 — ⬜ **다운로드 필요**

받은 파일은 **`data/external/commercial/`** 에 아래 이름으로 저장하세요.

| 저장할 파일명 | 데이터셋 | 링크 |
|---|---|---|
| `점포_행정동.csv` | 상권분석서비스(점포-행정동) | https://data.seoul.go.kr/dataList/OA-22172/S/1/datasetView.do |
| `집객시설_행정동.csv` | 상권분석서비스(집객시설-행정동) | https://data.seoul.go.kr/dataList/OA-22169/S/1/datasetView.do |
| `상주인구_행정동.csv` | 상권분석서비스(상주인구-행정동) | https://data.seoul.go.kr/dataList/OA-22183/S/1/datasetView.do |
| `직장인구_행정동.csv` | 상권분석서비스(직장인구-행정동) | https://data.seoul.go.kr/dataList/OA-22184/S/1/datasetView.do |

> ⚠️ **반드시 `-행정동` 버전**을 받으세요. `-자치구`·`-서울시` 버전은 집계 단위가 달라 쓸 수 없고,
> 구버전 `-상권`(OA-15xxx)은 공간 단위 자체가 달라 행정동 조인이 안 됩니다.

**참고 — 헷갈리기 쉬운 인접 ID (받지 말 것)**

| ID | 이름 |
|---|---|
| OA-22170 | 집객시설-**자치구** |
| OA-22171 | 집객시설-**서울시** |
| OA-22181 | 상주인구-**서울시** |
| OA-22182 | 상주인구-**자치구** |
| OA-22185 | 직장인구-**자치구** |
| OA-22173 | 점포-**자치구** |

---

## 2. API 자동 수집 (스크립트로 처리)

| 데이터 | 링크 | 인증키 | 상태 |
|---|---|---|---|
| 행정동 생활인구(내국인) | https://data.seoul.go.kr/dataList/OA-14991/S/1/datasetView.do | `SEOUL_OPENAPI_KEY` | ✅ 호출 성공 |
| 서울 공영주차장 | https://data.seoul.go.kr/dataList/OA-13122/S/1/datasetView.do | `SEOUL_OPENAPI_KEY` | ✅ 2,189건 / 61,035면 |
| 행정동 경계 (SGIS) | https://sgis.mods.go.kr | `SGIS_CONSUMER_KEY/SECRET` | ✅ 426개 행정동 |
| 카카오 로컬 (POI, 보조) | https://developers.kakao.com | `KAKAO_REST_API_KEY` | ✅ 키 보유 |

---

## 3. 서버 장애 중 — 복구 후 재시도

| 데이터 | 링크 | 상태 |
|---|---|---|
| 전국주차장정보 표준데이터 (**민영 포함**) | https://www.data.go.kr/data/15012896/standard.do | ❌ 파일 500 / API 504 |

복구 확인 명령:
```bash
python -m src.collect.fetch_parking_standard --probe
```

---

## 4. 인증키 발급처

| 키 | 발급처 | 비고 |
|---|---|---|
| `SEOUL_OPENAPI_KEY` | https://data.seoul.go.kr | 마이페이지 → 인증키 신청 |
| `KAKAO_REST_API_KEY` | https://developers.kakao.com | 내 애플리케이션 → 플랫폼 키 → REST API 키 |
| `DATA_GO_KR_KEY` | https://www.data.go.kr | 오픈API 탭 → 활용신청. **Encoding 키 사용 중** |
| `SGIS_CONSUMER_KEY/SECRET` | https://sgis.mods.go.kr | 서비스 ID + 보안 Key 한 쌍 |

> ⚠️ SGIS 도메인 이전: `sgis.kostat.go.kr` → **`sgis.mods.go.kr`** (통계청 → 국가데이터처)

---

## 5. 참고 자료

| 내용 | 링크 |
|---|---|
| 서울 생활인구 소개 페이지 | https://data.seoul.go.kr/dataVisual/seoul/seoulLivingPopulation.do |
| 상권분석 데이터셋 전체 검색 | https://data.seoul.go.kr/dataList/datasetList.do?srchKeyword=상권분석 |
| 카카오 로컬 API 문서 | https://developers.kakao.com/docs/ko/local/dev-guide |
