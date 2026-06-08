"""원주 학교 티센폴리곤 + 비만율 결합 → thiessen.js 생성
- Input_FID = data.js(map_data.json) 원주 학교 리스트 인덱스
- 초등/중학교별 GeoJSON, 분위수 5등급 경계 메타 포함
- 공유 폴리곤(FID 62 원주중학교부설방송통신중학교)은 원주중학교(FID 61) 비만율로 색칠
- Getis-Ord Gi* (Queen 인접, permutations=999): giZ, giP, giClass
"""
import geopandas as gpd
import pandas as pd
import numpy as np
import json
import os
import warnings

from libpysal.weights import Queen
from esda.getisord import G_Local

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "map_data.json"), encoding="utf-8") as f:
    ALL = json.load(f)
schools = ALL["wonju"]["schools"]

SHP = {
    "elementary": "원주시_초등학교_티센.shp",
    "middle": "원주시_중학교_티센.shp",
}

# 공유 폴리곤 보정: 부설방송통신중 폴리곤 → 원주중학교 비만율 사용
name_to_idx = {s["name"]: i for i, s in enumerate(schools)}
OVERRIDE = {}  # fid(폴리곤 학교) -> 색칠에 쓸 학교 인덱스
if "원주중학교부설방송통신중학교" in name_to_idx and "원주중학교" in name_to_idx:
    OVERRIDE[name_to_idx["원주중학교부설방송통신중학교"]] = name_to_idx["원주중학교"]


def quantile_breaks(values, n=5):
    arr = np.array([v for v in values if v is not None], dtype=float)
    qs = np.quantile(arr, [i / n for i in range(n + 1)])
    # 중복 제거(동일 값 경계 방지)
    out = []
    for q in qs:
        r = round(float(q), 2)
        if not out or r > out[-1]:
            out.append(r)
    return out


def classify_gi(z, p):
    """Gi* 분류: p<0.01/0.05 × Hot/Cold, 그 외 Not Significant"""
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
    """gdf 행 순서에 맞춘 obeseRate 리스트(color_rates)로 Queen 인접 Gi* 계산.
    None 값은 평균으로 대체해 분석하되, 출력은 None 으로 표시."""
    n = len(gdf)
    gi_z = [None] * n
    gi_p = [None] * n
    gi_class = [None] * n

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
        zs = gi.Zs
        ps = gi.p_sim
        for i in range(n):
            if not valid[i]:
                continue
            z = float(zs[i])
            p = float(ps[i])
            gi_z[i] = round(z, 3)
            gi_p[i] = round(p, 4)
            gi_class[i] = classify_gi(z, p)
    except Exception as e:
        print(f"  Gi* 계산 실패: {e}")

    return gi_z, gi_p, gi_class


output = {}
for level, fn in SHP.items():
    gdf = gpd.read_file(os.path.join(BASE_DIR, "data", "thiessen", fn), encoding="cp949")
    gdf = gdf.to_crs(epsg=4326)

    # 행 순서에 맞춘 색칠 대상 학교/비만율 — 유효 폴리곤만 남김
    rows = []
    color_rates = []
    for _, row in gdf.iterrows():
        fid = int(row["Input_FID"])
        if not (0 <= fid < len(schools)):
            continue
        sch = schools[fid]
        color_idx = OVERRIDE.get(fid, fid)
        color_sch = schools[color_idx]
        rows.append((row, fid, sch, color_idx, color_sch))
        color_rates.append(color_sch.get("obeseRate"))

    # Queen 인접 Gi* (행 순서 = rows 순서)
    valid_gdf = gpd.GeoDataFrame(
        {"geometry": [r[0].geometry for r in rows]},
        geometry="geometry",
        crs=gdf.crs,
    )
    gi_z, gi_p, gi_class = compute_gi_star(valid_gdf, color_rates)

    features = []
    rates = []
    for idx, (row, fid, sch, color_idx, color_sch) in enumerate(rows):
        rate = color_sch.get("obeseRate")
        props = {
            "name": color_sch["name"],
            "level": color_sch["level"],
            "students": color_sch.get("students"),
            "obese": color_sch.get("obese"),
            "obeseRate": rate,
            "giZ": gi_z[idx],
            "giP": gi_p[idx],
            "giClass": gi_class[idx],
        }
        if color_idx != fid:
            props["also"] = sch["name"]
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": row.geometry.__geo_interface__,
        })
        if rate is not None:
            rates.append(rate)

    breaks = quantile_breaks(rates, 5)

    # Gi* 분류 카운트(요약용)
    gi_counts = {}
    for c in gi_class:
        if c is None:
            continue
        gi_counts[c] = gi_counts.get(c, 0) + 1

    output[level] = {
        "type": "FeatureCollection",
        "features": features,
        "breaks": breaks,
        "min": round(float(np.min(rates)), 1),
        "max": round(float(np.max(rates)), 1),
        "mean": round(float(np.mean(rates)), 1),
        "median": round(float(np.median(rates)), 1),
        "count": len(features),
        "giCounts": gi_counts,
    }
    print(f"[{level}] 폴리곤 {len(features)}개, 비만율 {output[level]['min']}~{output[level]['max']}% (평균 {output[level]['mean']}), breaks={breaks}")
    print(f"  Gi*: {gi_counts}")

out_path = os.path.join(BASE_DIR, "thiessen.js")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("const THIESSEN_DATA = ")
    json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";")
print(f"출력: {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")
