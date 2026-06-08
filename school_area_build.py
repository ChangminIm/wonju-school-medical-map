"""원주 초·중학교 통학구역 + 비만율 결합 → school_area.js 생성
- data/school_area/원주시_초등_통학.shp (56개), 원주시_중등_통학.shp (8개) · 강원 원주교육지원청
- 공통 규칙: 구역에 속한 학교 비만율의 단순 평균
  · 초등(이름 기반): 단독=학교값, 공동=구성교 평균, 원주삼육초(통학구역 미지정)는
    공간 중첩되는 무실초 구역에 합산 → avg(무실초, 삼육초)
    학교명 매칭은 '원주섬강초'↔'섬강초등학교' 처럼 '원주' 접두어 정규화
  · 중등(공간 기반): 학구/학교군 폴리곤에 점이 포함되는 중학교 평균.
    원주시학교군·서부지역학교군은 다수 학교 포함. 방송통신중은 일반 학구교가 아니므로
    평균에서 제외(CLAUDE.md 규칙 #8: 공유 폴리곤 처리와 정합)
- Getis-Ord Gi* (Queen 인접, permutations=999): giZ, giP, giClass
- 출력 구조: SCHOOL_AREA_DATA = {"elementary": {...}, "middle": {...}}
"""
import os
import json
import warnings

import numpy as np
import geopandas as gpd
from shapely.geometry import Point

from libpysal.weights import Queen
from esda.getisord import G_Local

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SA_DIR = os.path.join(BASE_DIR, "data", "school_area")

ELEM_SHP = os.path.join(SA_DIR, "원주시_초등_통학.shp")
MID_SHP = os.path.join(SA_DIR, "원주시_중등_통학.shp")

# 초등: 통학구역 미지정이나 특정 단독구역에 공간 중첩되는 학교 보정
OVERLAP = {"무실초통학구역": "원주삼육초등학교"}
# 중등: 학교군 평균에서 제외할 비(非)학구 특수교
MID_EXCLUDE = {"원주중학교부설방송통신중학교"}

with open(os.path.join(BASE_DIR, "map_data.json"), encoding="utf-8") as f:
    ALL = json.load(f)
SCHOOLS = ALL["wonju"]["schools"]
elem_by_name = {s["name"]: s for s in SCHOOLS if s["level"] == "초등학교"}


# ── 공통 유틸 ──────────────────────────────────────────────
def quantile_breaks(values, n=5):
    arr = np.array([v for v in values if v is not None], dtype=float)
    qs = np.quantile(arr, [i / n for i in range(n + 1)])
    out = []
    for q in qs:
        r = round(float(q), 2)
        if not out or r > out[-1]:
            out.append(r)
    return out


def classify_gi(z, p):
    if z is None or p is None:
        return None
    if p < 0.01 and z > 0:
        return "Hot 99%"
    if p < 0.05 and z > 0:
        return "Hot 95%"
    if p < 0.01 and z < 0:
        return "Cold 99%"
    if p < 0.05 and z < 0:
        return "Cold 95%"
    return "Not Significant"


def compute_gi_star(geoms, color_rates, crs):
    n = len(geoms)
    gi_z, gi_p, gi_class = [None] * n, [None] * n, [None] * n
    rates = np.array([np.nan if v is None else float(v) for v in color_rates], dtype=float)
    valid = ~np.isnan(rates)
    if valid.sum() < 2:
        return gi_z, gi_p, gi_class
    gdf = gpd.GeoDataFrame({"geometry": geoms}, geometry="geometry", crs=crs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        w = Queen.from_dataframe(gdf, silence_warnings=True)
    w.transform = "R"
    vals = rates.copy()
    vals[~valid] = np.nanmean(rates)
    try:
        gi = G_Local(vals, w, transform="R", permutations=999, seed=42)
        for i in range(n):
            if not valid[i]:
                continue
            z, p = float(gi.Zs[i]), float(gi.p_sim[i])
            gi_z[i] = round(z, 3)
            gi_p[i] = round(p, 4)
            gi_class[i] = classify_gi(z, p)
    except Exception as e:
        print(f"  Gi* 계산 실패: {e}")
    return gi_z, gi_p, gi_class


def assemble(rows, crs):
    """rows: [(geometry, name, gb_label, members[list of school dict], note)]"""
    color_rates = [
        round(float(np.mean([m["obeseRate"] for m in mem])), 2) if mem else None
        for _, _, _, mem, _ in rows
    ]
    gi_z, gi_p, gi_class = compute_gi_star([r[0] for r in rows], color_rates, crs)

    features, rates = [], []
    for idx, (geom, name, gb_label, members, note) in enumerate(rows):
        rate = color_rates[idx]
        props = {
            "name": name,
            "gb": gb_label,
            "schools": " · ".join(m["name"] for m in members),
            "schoolCount": len(members),
            "students": int(sum(m.get("students") or 0 for m in members)),
            "obese": round(float(sum(m.get("obese") or 0 for m in members)), 1),
            "obeseRate": rate,
            "giZ": gi_z[idx],
            "giP": gi_p[idx],
            "giClass": gi_class[idx],
        }
        if note:
            props["note"] = note
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": geom.__geo_interface__,
        })
        if rate is not None:
            rates.append(rate)

    breaks = quantile_breaks(rates, 5)
    gi_counts = {}
    for c in gi_class:
        if c is not None:
            gi_counts[c] = gi_counts.get(c, 0) + 1
    shared = sum(1 for _, _, gb, _, _ in rows if gb != "단독")
    return {
        "type": "FeatureCollection",
        "features": features,
        "breaks": breaks,
        "min": round(float(np.min(rates)), 1),
        "max": round(float(np.max(rates)), 1),
        "mean": round(float(np.mean(rates)), 1),
        "median": round(float(np.median(rates)), 1),
        "count": len(features),
        "shared": shared,
        "giCounts": gi_counts,
    }


# ── 초등 (구역명 기반 매칭) ────────────────────────────────
def strip_suffix(nm):
    for s in ("공동통학구역", "공통통학구역", "통학구역"):
        if nm.endswith(s):
            return nm[:-len(s)]
    return nm


def build_elementary():
    gdf = gpd.read_file(ELEM_SHP).to_crs(epsg=4326)

    def lookup(short):
        cands = [short + "등학교",
                 (short[2:] if short.startswith("원주") else "원주" + short) + "등학교"]
        for nm in cands:
            if nm in elem_by_name:
                return elem_by_name[nm]
        return None

    singles = [strip_suffix(r["HAKGUDO_NM"]) for _, r in gdf.iterrows() if r["HAKGUDO_GB"] == "0"]
    vocab = set(singles)

    def segment(body):
        n = len(body)
        res = [None] * (n + 1)
        res[0] = []
        for i in range(1, n + 1):
            for j in range(i):
                if res[j] is not None and body[j:i] in vocab:
                    cand = res[j] + [body[j:i]]
                    if res[i] is None or len(cand) < len(res[i]):
                        res[i] = cand
        return res[n]

    rows = []
    for _, row in gdf.iterrows():
        hname, gb = row["HAKGUDO_NM"], row["HAKGUDO_GB"]
        body = strip_suffix(hname)
        toks = [body] if gb == "0" else (segment(body) or [body])
        members = [m for m in (lookup(t) for t in toks) if m is not None]
        note = None
        if hname in OVERLAP and OVERLAP[hname] in elem_by_name:
            members.append(elem_by_name[OVERLAP[hname]])
            note = f"{OVERLAP[hname]} 포함 (통학구역 미지정·공간 중첩)"
        gb_label = "공동" if gb == "1" else "단독"
        rows.append((row.geometry, hname, gb_label, members, note))
    return assemble(rows, gdf.crs)


# ── 중등 (공간 point-in-polygon 매칭) ─────────────────────
def build_middle():
    gdf = gpd.read_file(MID_SHP).to_crs(epsg=4326)
    mids = [s for s in SCHOOLS if s["level"] == "중학교" and s["name"] not in MID_EXCLUDE]
    pts = [(s, Point(s["lng"], s["lat"])) for s in mids]

    rows = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        members = [s for s, p in pts if geom.contains(p)]
        gb_label = "학교군" if len(members) > 1 else "단독"
        note = f"{len(members)}개교 평균" if len(members) > 1 else None
        rows.append((geom, row["HAKGUDO_NM"], gb_label, members, note))
    return assemble(rows, gdf.crs)


output = {"elementary": build_elementary(), "middle": build_middle()}

out_path = os.path.join(BASE_DIR, "school_area.js")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("const SCHOOL_AREA_DATA = ")
    json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";")

for lv, d in output.items():
    print(f"[{lv}] 폴리곤 {d['count']}개 (다수교구역 {d['shared']}) · "
          f"비만율 {d['min']}~{d['max']}% (평균 {d['mean']}, 중앙 {d['median']}) · breaks={d['breaks']}")
    print(f"   Gi*: {d['giCounts']}")
print(f"출력: {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")
