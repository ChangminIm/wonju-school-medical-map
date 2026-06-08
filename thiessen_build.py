"""원주 학교 티센폴리곤 + 비만율 결합 → thiessen.js 생성
- Input_FID = data.js(map_data.json) 원주 학교 리스트 인덱스
- 초등/중학교별 GeoJSON, 분위수 5등급 경계 메타 포함
- 공유 폴리곤(FID 62 원주중학교부설방송통신중학교)은 원주중학교(FID 61) 비만율로 색칠
"""
import geopandas as gpd
import pandas as pd
import numpy as np
import json
import os

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


output = {}
for level, fn in SHP.items():
    gdf = gpd.read_file(os.path.join(BASE_DIR, "data", "thiessen", fn), encoding="cp949")
    gdf = gdf.to_crs(epsg=4326)
    features = []
    rates = []
    for _, row in gdf.iterrows():
        fid = int(row["Input_FID"])
        sch = schools[fid] if 0 <= fid < len(schools) else None
        if sch is None:
            continue
        color_idx = OVERRIDE.get(fid, fid)
        color_sch = schools[color_idx]
        rate = color_sch.get("obeseRate")
        obese = color_sch.get("obese")
        students = color_sch.get("students")
        props = {
            "name": color_sch["name"],
            "level": color_sch["level"],
            "students": students,
            "obese": obese,
            "obeseRate": rate,
        }
        if color_idx != fid:
            props["also"] = sch["name"]
        geom = row.geometry.__geo_interface__
        features.append({"type": "Feature", "properties": props, "geometry": geom})
        if rate is not None:
            rates.append(rate)
    breaks = quantile_breaks(rates, 5)
    output[level] = {
        "type": "FeatureCollection",
        "features": features,
        "breaks": breaks,
        "min": round(float(np.min(rates)), 1),
        "max": round(float(np.max(rates)), 1),
        "mean": round(float(np.mean(rates)), 1),
        "median": round(float(np.median(rates)), 1),
        "count": len(features),
    }
    print(f"[{level}] 폴리곤 {len(features)}개, 비만율 {output[level]['min']}~{output[level]['max']}% (평균 {output[level]['mean']}), breaks={breaks}")

out_path = os.path.join(BASE_DIR, "thiessen.js")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("const THIESSEN_DATA = ")
    json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";")
print(f"출력: {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")
