# CLAUDE.md — wonju-school-medical-map

> AI/신규 담당자용 빠른 참조. 상세는 **HANDOFF.md** 참조.

## 프로젝트 한 줄 요약

원주·용인 **소아비만 연구** GIS 웹 플랫폼. GitHub Pages 정적 배포.  
Leaflet 지도 3종 + matplotlib 정적 PNG + Python 전처리/공간분석.

**URL:** https://changminim.github.io/wonju-school-medical-map/

---

## 페이지 구조

| URL | 파일 | 역할 |
|-----|------|------|
| `/` | `index.html` | 메인 랜딩 + 결과 PNG |
| `/access.html` | `access.html` | 학교·의료·늘봄 접근성 지도 |
| `/choropleth.html` | `choropleth.html` | 원주 티센 비만율 |
| `/2sfca/` | `2sfca/index.html` | 용인·원주 500m 2SFCA/Gi*(Queen) · 지역 토글 |

---

## 핵심 데이터 파일

| 파일 | 생성 | 용도 |
|------|------|------|
| `data.js` | `convert_data.py` | ALL_DATA (학교·의료·늘봄·obeseRate) |
| `thiessen.js` | `thiessen_build.py` | THIESSEN_DATA (원주 폴리곤) |
| `2sfca/result.js` | `2sfca/analyze.py` | 용인·원주 격자별 2SFCA/E2SFCA/Gi*(Queen). 컬럼형 {지역:{surfaces,gi,boundary}} |

`convert_data.py`, `data/`, `map_data.json` → **.gitignore** (로컬 원본 필요)

---

## 자주 쓰는 명령

```bat
# 로컬 서버
python -m http.server 8011

# 데이터 갱신 (순서)
python convert_data.py
python thiessen_build.py
cd 2sfca && python analyze.py
python render_maps.py

# GitHub 직접 배포 (git push 실패 시)
python deploy_pages.py
```

---

## 코딩 규칙

1. **한국어 UI** — 라벨·팝업·README 사용자-facing 텍스트
2. **최소 diff** — 요청 범위만 수정, 무관 코드 건드리지 않음
3. **기존 패턴 따르기** — Leaflet divIcon, Turf 거리, 2SFCA Gi* 색상(`#dc2626`/`#2563eb`/`#e2e8f0`)
4. **커밋** — 사용자 요청 시에만. Made-with-Cursor trailer 금지
5. **배포 후** — 브라우저 캐시(`data.js`) 이슈 안내
6. **원주 의료** — SHP 491 전체 + 엑셀 252 보강 (convert_data.py)
7. **티센 매칭** — `Input_FID` = `ALL_DATA.wonju.schools` 인덱스
8. **공유 폴리곤** — 원주중학교부설방송통신중학교 → 원주중학교 비만율
9. **건강검진 필터** — 원주=학생건강검진, 용인·전체=국가건강검진
10. **정적 PNG** — EPSG:5179, OSM NoLabels, 노스애로우+10km 스케일바 (render_maps.py)

---

## Git 주의

- **로컬 master** (`26fc7c1`) ≠ **origin/master** (`d66776c`) — diverged
- **GitHub Pages**는 gh api로 더 앞서 있음 (`access.html`, `choropleth.html`, `maps/` 등)
- HEAD 추적: 8파일만. 나머지는 미커밋 상태일 수 있음

---

## 다음 작업 (P0, 미완)

티센폴리곤 **Getis-Ord Gi\* (Queen)**:
1. `thiessen_build.py` — giZ, giP, giClass 추가
2. `choropleth.html` — 비만율/Gi* 레이어 토글
3. `render_maps.py` — Gi* PNG 2종
4. `index.html` — 결과지도 +2

상세 플랜·현황: **HANDOFF.md** §⑥

---

## 의존성

```
pip install geopandas pandas numpy shapely openpyxl
pip install libpysal esda          # 2SFCA
pip install matplotlib contextily  # PNG
```

원본 데이터 경로: `convert_data.py` 내 `d:\02_2026년\12_소아비만\...` (이식 시 수정 필요)

---

## 참고 링크

- Repo: https://github.com/ChangminIm/wonju-school-medical-map
- 상세 인수인계: [HANDOFF.md](./HANDOFF.md)
