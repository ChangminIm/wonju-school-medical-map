# HANDOFF — 원주·용인 소아비만 GIS 분석 플랫폼

> **작성 기준:** 2026-06-08  
> **근거:** 저장소 파일 구조, 소스 코드, `git log --oneline --all` 전체 이력, GitHub Pages 원격 상태  
> **저장소:** `ChangminIm/wonju-school-medical-map`  
> **배포 URL:** https://changminim.github.io/wonju-school-medical-map/

---

## ① 프로젝트 목적 / 전체 그림

### 연구 배경
강원특별자치도 **원주시**와 경기도 **용인시**를 대상으로, 소아비만 연구용 GIS 플랫폼을 구축한다.  
학교–의료기관 **접근성**, 학교별 **소아비만율 공간 분포**, **2SFCA 공간 접근성**을 하나의 웹 앱으로 제공한다.

### 최종 아키텍처 (현재 의도)
정적 HTML + Leaflet.js + 사전 생성 JS/JSON. 백엔드 서버 없음. GitHub Pages 배포.

```
index.html          ← 메인 랜딩 (3개 지도 링크 + 결과지도 PNG)
├── access.html     ← 접근성 인터랙티브 지도 (원주+용인)
├── choropleth.html ← 원주 티센폴리곤 비만율 단계구분도
├── 2sfca/index.html← 용인 500m 격자 2SFCA/E2SFCA/KDE/Gi*
├── data.js         ← 학교·의료·늘봄·비만 데이터
├── thiessen.js     ← 원주 티센폴리곤 GeoJSON
└── maps/*.png      ← 정적 결과지도 (논문/보고용)
```

### 데이터 파이프라인
```
원본(SHP/엑셀, 로컬 D: 드라이브)
    ↓ convert_data.py  (gitignore, 로컬만)
map_data.json        (gitignore)
    ↓
data.js              (브라우저용 const ALL_DATA)

원주 티센 SHP
    ↓ thiessen_build.py
thiessen.js          (THIESSEN_DATA)

용인 500m 격자 SHP + data.js
    ↓ 2sfca/analyze.py
2sfca/result.js + boundary.js
```

---

## ② 지금까지 만들어진 것 (기능·모듈·산출물)

### A. 접근성 지도 (`access.html`)
**역할:** 초·중등학교와 의료기관·늘봄기관 위치 및 접근성 탐색.

| 기능 | 설명 |
|------|------|
| 지역 탭 | 전체 / 원주시 / 용인시 |
| 마커 | 학교(초·중), 의료(소아청소년과/내과/기타), 늘봄기관(🧸) |
| 필터 | 학교급, 진료과, 의료기관 종별, 지역별 건강검진 |
| 검색 | 학교·의료·늘봄 이름 검색 |
| 학교 클릭 | 가까운 의료기관 N개(3/5/10) + 1km·3km 반경 요약(진료과별·합계) |
| 반경 원 | 1km / 3km 선택 표시 |
| 팝업 | 학생수, 건강/영양교사, 소아비만(추정) 인원·비율 |
| 좌표 보정 | 교동초등학교 → (37.339043, 127.946940) |

**기술:** Leaflet.js, Turf.js(거리), `data.js`

---

### B. 메인 랜딩 (`index.html`)
**역할:** 소아비만 연구 플랫폼 허브. 건국대 그린 테마.

- 통계 카드: 학교 238교, 의료 1,104개, 늘봄 96개 등
- 3개 지도 카드 링크 (접근성 / 단계구분도 / 2SFCA)
- **결과 지도** 섹션: 정적 PNG 2종 (초등·중학 비만율) 다운로드

---

### C. 소아비만율 단계구분도 (`choropleth.html` + `thiessen.js`)
**역할:** 원주시 티센(Thiessen/Voronoi) 영향권별 비만율 시각화.

| 항목 | 내용 |
|------|------|
| 대상 | 원주 초등 51폴리곤, 중학 24폴리곤 |
| 색상 | 분위수 5등급, 연노랑→진빨강 |
| UI | 초등/중학 토글, 학교 위치점 오버레이 |
| 팝업 | 학교명, 비만율, 학생수, 추정 비만 인원 |
| 매칭 | SHP `Input_FID` = `data.js` 원주 schools 배열 인덱스 |
| 예외 | 원주중학교부설방송통신중학교 폴리곤 → 원주중학교 비만율 사용 |

**생성:** `python thiessen_build.py` → `thiessen.js`

---

### D. 2SFCA 접근성 분석 (`2sfca/`)
**역할:** 용인시 초등학생 500m 격자 의료 접근성.

| 항목 | 내용 |
|------|------|
| 수요 | `2sfca/data/YI_500m_elementary.shp` (val=인구) |
| 공급 | `map_data.json` 용인 의료기관 |
| 방법 | 2SFCA, E2SFCA(가우시안 감쇠) |
| 거리 | 1km / 3km / 5km |
| 지표 | 소아전문의, 내과전문의, 합계, 기관 수 |
| 부가 | KDE 밀도, **Gi\* 핫스팟(KNN k=8, p<0.05)** |
| 시각 | 인구 0 격자 숨김, 0~1 정규화, 파란 그radient, 용인 경계 오버레이 |

**생성:** `cd 2sfca && python analyze.py` → `result.js`, `boundary.js`

---

### E. 정적 결과지도 (`render_maps.py` → `maps/`)
**역할:** 보고서·발표용 PNG (matplotlib + contextily).

| 파일 | 내용 |
|------|------|
| `wonju_elem_obesity.png` | 초등 비만율, 2.9~7.6% |
| `wonju_mid_obesity.png` | 중학 비만율, 0~22.3% |
| `원주_초등학교_소아비만율.png` | 한글 파일명 원본 |
| `원주_중학교_소아비만율.png` | 한글 파일명 원본 |

**지도 요소 (현재 확정 스타일):**
- OSM CartoDB Positron **NoLabels** (회색 배경, 지명 없음)
- 좌표계 EPSG:5179 (거리 정확도)
- 노스애로우: N(일반) + 세로 긴 이등변삼각형, 위 끝=범례 위 끝, 왼쪽=행정경계 왼쪽
- 스케일바: 흰박스, 0·5·10 Km, 박스 우측=범례 우측, 박스 하단=행정경계 하단
- 상하 지도 여백 3% 대칭

**생성:** `python render_maps.py` (contextily 필요)

---

### F. 데이터 전처리 (`convert_data.py`, gitignore)
**역할:** SHP/엑셀 → `map_data.json` + `data.js`

| 지역 | 소스 | 산출 |
|------|------|------|
| 원주 학교 | `원주시초중등.xlsx` | schools[] |
| 원주 의료 | SHP 491 + 엑셀 252 매칭 | medical[] |
| 원주·용인 늘봄 | `원주시늘봄기관_WGS.shp`, `용인시_늘봄센터_WGS.shp` | care[] |
| 용인 학교·의료 | 용인 엑셀 | schools[], medical[] |
| 비만 추정 | `용인_원주_소아비만_수_추정.xlsx` | obese, obeseRate (학교명+지역 매칭) |

**의료 분류 규칙 (커밋 e0470ac):**
- 소아청소년과 ○ → `소아청소년과`
- 소아 ×, 내과 ○ → `내과`
- 둘 다 × → `기타`

**건강검진 필터 (커밋 35d460d):**
- 원주: `healthCheck` = 학생건강검진 ○
- 용인: 국가건강검진(일반) ○
- 전체 탭: 용인 규칙(국가건강검진) 적용

---

### G. 배포 스크립트 (`deploy_pages.py`)
GitHub CLI `gh api PUT`으로 원격 파일 직접 업데이트.  
로컬 `git push`가 불안정했을 때 사용. `FILES` dict에 경로·커밋 메시지 지정.

---

## ③ Git 전체 이력 (시간순, 중복 커밋 병합)

> `git filter-branch`로 Made-with-Cursor 제거 과정에서 동일 변경의 한·영 커밋 쌍이 존재. 아래는 **논리적 변경** 기준.

| 날짜 | 커밋 | 변경 |
|------|------|------|
| 2026-04-14 | `83bad02` | **초기:** 원주 접근성 지도 `index.html`(520줄), `.gitignore` |
| 2026-04-29 | `e0470ac` | 진료과 3분류 + 종별 필터 |
| 2026-04-29 | `6c0a963` | 팝업: 학생수·교사수·전문의수 |
| 2026-04-29 | `35d460d` | **용인 데이터** + 지역 탭 + 건강검진 필터, `data.js` 추가 |
| 2026-04-29 | `672afdf` | **전체 탭** (원주+용인 동시 표시) |
| 2026-04-29 | `337aeef` | 전체보기 건강검진 라벨 명확화 |
| 2026-04-29 | `d1e3d6c` | 교동초 좌표 수정 |
| 2026-04-29 | `3dd0241` | **2SFCA 페이지** (`2sfca/analyze.py`, `index.html`, `result.js`) |
| 2026-04-29 | `e649bfe` | 2SFCA: 빈 격자 숨김, 0~1 정규화 |
| 2026-04-29 | `efcd65e` | **KDE + Gi\* + 용인 경계**, blue palette 복원 |
| 2026-04-29 | `8d4cf1c` | **1km/3km 반경 의료기관 요약** (팝업+사이드바) |
| 2026-04-29 | `3c2b0d2` | 사이드바: 거리순 목록 → 반경 요약 순서 |
| 2026-04-29 | `17a41d6` | 반경 요약 테이블 가독성 |
| 2026-04-29 | `cdb06ce` | 사이드바 섹션 헤더 |
| 2026-04-29 | `564fbcc` | 한글 README |
| 2026-04-29 | `d66776c` | README 수정 (**origin/master HEAD**) |
| 2026-06-05 | `26fc7c1` | **늘봄기관** (로컬 master HEAD) |

### Git에 없지만 로컬·원격에 존재하는 작업 (gh api 배포)
커밋 없이 GitHub Pages에 반영된 변경:

- `index.html` → 메인 랜딩 페이지로 교체
- `access.html` 신규 (구 `index.html` 접근성 지도)
- `choropleth.html`, `thiessen.js` 신규
- `maps/wonju_elem_obesity.png`, `wonju_mid_obesity.png`
- `data.js` 소아비만(obese/obeseRate) 필드
- `2sfca/index.html` 메인 링크
- `render_maps.py`, `thiessen_build.py`, `deploy_pages.py` (로컬만, 원격 미포함)

---

## ④ 현재 동작 상태

### 정상 동작 (로컬 + GitHub Pages 확인됨)
| 구성요소 | 상태 |
|----------|------|
| 메인 랜딩 | ✅ 배포됨 |
| access.html | ✅ 배포됨 |
| choropleth.html | ✅ 배포됨 |
| 2sfca/ | ✅ 배포됨 (result.js 사전 생성 필요) |
| 결과 PNG 2종 | ✅ 배포됨 |
| data.js (늘봄·비만) | ✅ (캐시 주의: hard refresh) |

### Git 상태 (2026-06-08 기준)
```
로컬 master:  26fc7c1 (늘봄기관)
origin/master: d66776c (README)  ← diverged
```

**로컬 HEAD 추적 파일 (8개):**
`.gitignore`, `README.md`, `data.js`, `index.html`, `2sfca/analyze.py`, `2sfca/boundary.js`, `2sfca/index.html`, `2sfca/result.js`

**로컬 미추적/미커밋 (주요):**
`access.html`, `choropleth.html`, `thiessen.js`, `thiessen_build.py`, `render_maps.py`, `deploy_pages.py`, `maps/`

**gitignore (의도적 제외):**
`data/`, `map_data.json`, `convert_data.py`, `start_server.bat`

### 깨진 / 미완성 / 불일치

| 항목 | 상태 |
|------|------|
| **Gi\* (티센폴리곤, Queen)** | ❌ 미구현 (다음 단계로 합의) |
| **README.md** | ⚠️ 구조 반영 안 됨 (단일 지도 URL만 기재) |
| **git ↔ GitHub Pages** | ⚠️ 원격이 로컬보다 앞섬 (gh api 직접 배포) |
| **git ↔ origin** | ⚠️ diverged (pull/merge 필요) |
| **convert_data.py 경로** | ⚠️ `d:\02_2026년\...` 하드코딩, 다른 PC에서 실행 불가 |
| **2sfca 재분석** | ⚠️ `analyze.py` 실행 시 `map_data.json` 필요 (gitignore) |
| **Gi\* 정적 PNG** | ❌ 미생성 |
| **choropleth Gi\* 레이어** | ❌ 미구현 |

---

## ⑤ 설계·방법론 결정 (코드·커밋·문서 근거)

| 결정 | 근거 |
|------|------|
| 정적 사이트 + Leaflet | 초기 커밋 `83bad02`, 서버 없이 GitHub Pages |
| 원주 의료 SHP 전체 + 엑셀 보강 | `convert_data.py` — 491 SHP, 252 엑셀 매칭 |
| 진료과 3분류 | 커밋 `e0470ac`, 연구 요청 반영 |
| 용인 건강검진 = 국가건강검진 | 커밋 `35d460d`, 지역별 필터 분기 |
| 전체 탭 = 용인 건강검진 규칙 | 커밋 `337aeef` |
| 2SFCA 수요 = 500m 격자 | `2sfca/analyze.py`, `YI_500m_elementary.shp` |
| 2SFCA Gi\* = KNN k=8 | `2sfca/analyze.py` `run_gi_star()` |
| 2SFCA 색상 = blue gradient | 커밋 `efcd65e` "revert to blue palette" |
| 티센 FID = schools 인덱스 | `thiessen_build.py` 주석·코드 |
| 비만율 = 추정합계/학생수×100 | `convert_data.py` col 35, 1소수 |
| 비만 단계구분 = 분위수 5등급 | `thiessen_build.py`, `choropleth.html` |
| 정적 지도 EPSG:5179 | `render_maps.py` — 스케일바 km 정확도 |
| 배포 우회 = gh api | `deploy_pages.py` |
| 페이지 분리 | `index.html` 랜딩 + `access.html` (원격 파일 목록) |

---

## ⑥ 남은 일 / 다음 단계 (우선순위)

### P0 — 즉시 (합의된 다음 작업)
1. **티센폴리곤 Gi\* (Queen)** — `thiessen_build.py`에 `G_Local` 추가
2. **choropleth.html** — 레이어 토글: 비만율 / Gi\*
3. **render_maps.py** — Gi\* PNG 2종 (초등·중학)
4. **index.html** — 결과지도 카드 +2 (총 4개)

### P1 — 저장소 정리
5. **git 정리** — 미추적 파일 커밋, origin과 merge/rebase
6. **README 갱신** — 3지도 구조, 실행법, 데이터 재생성 절차
7. **convert_data.py** — 경로를 환경변수/상대경로로 변경 검토

### P2 — 개선
8. 용인 티센/비만 단계구분도 (데이터 확보 시)
9. 원주 500m 격자 2SFCA (`2sfca/data/WJ_500m_elementary.shp` 존재, 미사용)
10. Gi\* 유의성 표시 강화 (99% 등)

---

## ⑦ 파일 트리 (전체)

```
wonju_obesity/
├── index.html              # 메인 랜딩 (건국대 그린)
├── access.html             # 접근성 지도
├── choropleth.html         # 원주 비만율 단계구분도
├── data.js                 # ALL_DATA (git 추적)
├── thiessen.js             # THIESSEN_DATA (원격만)
├── map_data.json           # gitignore
├── convert_data.py         # gitignore, 데이터 생성
├── thiessen_build.py       # thiessen.js 생성
├── render_maps.py          # PNG 결과지도
├── deploy_pages.py         # gh api 배포
├── start_server.bat        # gitignore, 로컬 http.server
├── README.md
├── .gitignore
├── maps/
│   ├── wonju_elem_obesity.png
│   ├── wonju_mid_obesity.png
│   ├── 원주_초등학교_소아비만율.png
│   └── 원주_중학교_소아비만율.png
├── data/                   # gitignore, 원본 SHP
│   ├── medical/            # 원주 의료 SHP
│   ├── schools/            # 원주 학교 SHP
│   ├── care_center/        # 원주·용인 늘봄 SHP
│   └── thiessen/           # 원주 초·중 티센 SHP
└── 2sfca/
    ├── index.html
    ├── analyze.py
    ├── result.js           # analyze.py 출력
    ├── boundary.js         # 용인 경계 GeoJSON
    └── data/
        ├── YI_500m_elementary.shp   # 용인 500m 격자 (사용 중)
        └── WJ_500m_elementary.shp   # 원주 500m 격자 (미사용)
```

---

## ⑧ 실행 방법 (신규 담당자용)

### 로컬 미리보기
```bat
cd wonju_obesity
python -m http.server 8011
```
브라우저: http://localhost:8011/

### 데이터 재생성 (원본 파일 필요)
```bat
python convert_data.py      # → map_data.json, data.js
python thiessen_build.py    # → thiessen.js
cd 2sfca && python analyze.py   # → result.js (libpysal, esda, geopandas)
python render_maps.py       # → maps/*.png (matplotlib, contextily)
```

### Python 의존성
```
geopandas, pandas, numpy, shapely
libpysal, esda          # 2SFCA Gi*
matplotlib, contextily  # PNG 렌더
openpyxl                # 엑셀
```

### GitHub Pages 배포
- 정상: `git push origin master`
- 우회: `python deploy_pages.py` (gh CLI + 인증 필요)

### 캐시 이슈
배포 후 `data.js` 변경이 안 보이면 **Ctrl+Shift+R** 또는 `?v=timestamp` URL 사용.

---

## ⑨ 데이터 규모 (data.js 기준)

| 항목 | 원주 | 용인 |
|------|------|------|
| 학교 | 76 | 162 |
| 의료 | 491 | 613 |
| 늘봄 | ~40 | ~56 |
| obeseRate | 76교 매칭 | 162교 매칭 |

(정확 수치는 `python convert_data.py` 실행 시 출력)

---

## ⑩ 연락·참고

- GitHub: https://github.com/ChangminIm/wonju-school-medical-map
- Pages: https://changminim.github.io/wonju-school-medical-map/
- 원본 데이터: `d:\02_2026년\12_소아비만\` (로컬, git 미포함)
