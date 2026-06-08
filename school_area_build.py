"""원주 초등학교 통학구역 + 비만율 결합 → school_area.js 생성
- data/school_area/원주시_초등_통학.shp (강원 원주교육지원청 56개 구역)
- HAKGUDO_GB: '0'=단독, '1'=공동
  · 단독: 해당 학교 비만율 그대로
  · 공동: 구성 학교 비만율 단순 평균
  · 원주삼육초(통학구역 미지정)는 무실초 통학구역에 공간 포함 → 무실초 구역 값 = avg(무실초, 삼육초)
- 학교명 매칭: '원주섬강초'↔'섬강초등학교' 처럼 '원주' 접두어 정규화
- Getis-Ord Gi* (Queen 인접, permutations=999): giZ, giP, giClass
"""
import os
import json
import warnings

import numpy as np
import geopandas as gpd

from libpysal.weights import Queen
from esda.getisord import G_Local

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHP = os.path.join(BASE_DIR, "data", "school_area", "원주시_초등_통학.shp")

# 통학구역 미지정이지만 특정 단독구역에 공간 중첩되는 학교 보정
#   원주삼육초등학교 → 무실초통학구역에 합산
OVERLAP = {"무실초통학구역": "원주삼육초등학교"}

with open(os.path.join(BASE_DIR, "map_data.json"), encoding="utf-8") as f:
    ALL = json.load(f)
elem = {s["name"]: s for s in ALL["wonju"]["schools"] if s["level"] == "초등학교"}


def lookup(short):
    """구역명 토막('강천초','원주섬강초')으로 학교 레코드 찾기. '원주' 접두어 정규화."""
    cands = [short + "등학교"]
    cands.append((short[2:] if short.startswith("원주") else "원주" + short) + "등학교")
    for nm in cands:
        if nm in elem:
            return elem[nm]
    return None


def strip_suffix(nm):
    for s in ("공동통학구역", "공통통학구역", "통학구역"):
        if nm.endswith(s):
            return nm[:-len(s)]
    return nm


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


def compute_gi_star(gdf, color_rates):
    n = len(gdf)
    gi_z, gi_p, gi_class = [None] * n, [None] * n, [None] * n
    rates = np.array([np.nan if v is None else float(v) for v in color_rates], dtype=float)
    valid = ~np.isnan(rates)
    if valid.sum() < 2:
        return gi_z, gi_p, gi_class
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


gdf = gpd.read_file(SHP).to_crs(epsg=4326)

# 단독구역 토막 집합 = 공동구역 분절용 어휘
singles = [strip_suffix(r["HAKGUDO_NM"]) for _, r in gdf.iterrows() if r["HAKGUDO_GB"] == "0"]
vocab = set(singles)


def segment(body):
    """공동구역 본문('치악초서원주초')을 단독구역 어휘로 최장일치 분절."""
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


rows = []        # (geometry, name, gb, members[list of school dict], note)
color_rates = []
for _, row in gdf.iterrows():
    hname = row["HAKGUDO_NM"]
    gb = row["HAKGUDO_GB"]
    body = strip_suffix(hname)
    if gb == "0":
        toks = [body]
    else:
        toks = segment(body) or [body]

    members = []
    for t in toks:
        sch = lookup(t)
        if sch is not None:
            members.append(sch)

    note = None
    if hname in OVERLAP and OVERLAP[hname] in elem:
        members.append(elem[OVERLAP[hname]])
        note = f"{OVERLAP[hname]} 포함 (통학구역 미지정·공간 중첩)"

    rate = round(float(np.mean([m["obeseRate"] for m in members])), 2) if members else None
    rows.append((row.geometry, hname, gb, members, note))
    color_rates.append(rate)

# Queen 인접 Gi*
valid_gdf = gpd.GeoDataFrame({"geometry": [r[0] for r in rows]}, geometry="geometry", crs=gdf.crs)
gi_z, gi_p, gi_class = compute_gi_star(valid_gdf, color_rates)

features = []
rates = []
for idx, (geom, hname, gb, members, note) in enumerate(rows):
    rate = color_rates[idx]
    gb_label = "공동" if gb == "1" else "단독"
    sch_names = " · ".join(m["name"] for m in members)
    props = {
        "name": hname,
        "gb": gb_label,
        "schools": sch_names,
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

output = {
    "type": "FeatureCollection",
    "features": features,
    "breaks": breaks,
    "min": round(float(np.min(rates)), 1),
    "max": round(float(np.max(rates)), 1),
    "mean": round(float(np.mean(rates)), 1),
    "median": round(float(np.median(rates)), 1),
    "count": len(features),
    "shared": sum(1 for _, _, gb, _, _ in rows if gb == "1"),
    "giCounts": gi_counts,
}

out_path = os.path.join(BASE_DIR, "school_area.js")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("const SCHOOL_AREA_DATA = ")
    json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";")

print(f"폴리곤 {len(features)}개 (단독 {len(features)-output['shared']} / 공동 {output['shared']})")
print(f"비만율 {output['min']}~{output['max']}% (평균 {output['mean']}, 중앙 {output['median']}), breaks={breaks}")
print(f"Gi*: {gi_counts}")
print(f"출력: {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")
