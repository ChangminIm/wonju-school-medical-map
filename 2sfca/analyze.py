"""
2SFCA / E2SFCA + Getis-Ord Gi* (Queen) — 용인·원주 초등학생 의료 접근성.
- 전체 격자(빈격자 포함) 출력. 인구=0 셀도 feature 로 내보냄(웹에서 회색/값 비교).
- Gi* 공간가중 = Queen 인접(전체 격자 기준), row-standardized.
- KDE 제거.
- 출력: result.js → const SFCA_DATA = {yongin:{meta,geojson,boundary}, wonju:{...}};
"""
import geopandas as gpd
import numpy as np
import json
import os
import warnings

from libpysal.weights import Queen

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

REGIONS = {
    "yongin": {"shp": "YI_500m_elementary.shp", "med": "yongin", "label": "용인시"},
    "wonju": {"shp": "WJ_500m_elementary.shp", "med": "wonju", "label": "원주시"},
}

CATCHMENTS = [1000, 3000, 5000]
SUPPLY_METRICS = {
    "ped": "소아청소년과 전문의",
    "inter": "내과 전문의",
    "ped_inter": "소아+내과 합계",
}


def gaussian_weight(d, d0):
    if d > d0:
        return 0.0
    return np.exp(-0.5 * (d / (d0 / 2.5)) ** 2)


def load_grid(shp_name):
    gdf = gpd.read_file(os.path.join(BASE_DIR, "data", shp_name))
    gdf = gdf.to_crs(epsg=4326)
    gdf["val"] = gdf["val"].fillna(0).astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gdf["centroid_lat"] = gdf.geometry.centroid.y
        gdf["centroid_lng"] = gdf.geometry.centroid.x
    return gdf


def load_medical(region):
    json_path = os.path.join(BASE_DIR, "..", "map_data.json")
    with open(json_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)
    meds = all_data[region]["medical"]
    result = []
    for m in meds:
        result.append({
            "lat": m["lat"], "lng": m["lng"],
            "supply_ped": m["ped"],
            "supply_inter": m["inter"],
            "supply_ped_inter": m["ped"] + m["inter"],
        })
    return result


def haversine_meters(lat1, lng1, lat2, lng2):
    R = 6371000
    lat1, lng1, lat2, lng2 = map(np.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def run_2sfca(grid_lats, grid_lngs, grid_pops, med_lats, med_lngs, med_supply, d0):
    n_grid = len(grid_lats)
    n_med = len(med_lats)
    R = np.zeros(n_med)
    for j in range(n_med):
        dists = haversine_meters(med_lats[j], med_lngs[j], grid_lats, grid_lngs)
        mask = dists <= d0
        pop_sum = grid_pops[mask].sum()
        if pop_sum > 0 and med_supply[j] > 0:
            R[j] = med_supply[j] / pop_sum
    A = np.zeros(n_grid)
    for i in range(n_grid):
        dists = haversine_meters(grid_lats[i], grid_lngs[i], np.array(med_lats), np.array(med_lngs))
        mask = dists <= d0
        A[i] = R[mask].sum()
    return A


def run_e2sfca(grid_lats, grid_lngs, grid_pops, med_lats, med_lngs, med_supply, d0):
    n_grid = len(grid_lats)
    n_med = len(med_lats)
    R = np.zeros(n_med)
    for j in range(n_med):
        dists = haversine_meters(med_lats[j], med_lngs[j], grid_lats, grid_lngs)
        weights = np.array([gaussian_weight(d, d0) for d in dists])
        weighted_pop = (grid_pops * weights).sum()
        if weighted_pop > 0 and med_supply[j] > 0:
            R[j] = med_supply[j] / weighted_pop
    A = np.zeros(n_grid)
    for i in range(n_grid):
        dists = haversine_meters(grid_lats[i], grid_lngs[i], np.array(med_lats), np.array(med_lngs))
        weights = np.array([gaussian_weight(d, d0) for d in dists])
        A[i] = (R * weights).sum()
    return A


def queen_weights(gdf):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Queen.from_dataframe(gdf, silence_warnings=True)


def largest_component_mask(gdf):
    """Queen 연결요소 중 최대 본체 마스크 (외딴 이상치 셀 제거용)."""
    w = queen_weights(gdf)
    labels = np.asarray(w.component_labels)
    vals, counts = np.unique(labels, return_counts=True)
    main = vals[counts.argmax()]
    return labels == main


def run_gi_star_queen(gdf, results_dict):
    """Getis-Ord Gi* — Queen 인접(전체 격자), row-standardized. 접근성 면 위 핫/콜드스팟."""
    from esda.getisord import G_Local

    w = queen_weights(gdf)
    w.transform = "R"

    n = len(gdf)
    gi_results = {}
    for key, vals_all in results_dict.items():
        vals = np.asarray(vals_all, dtype=float)
        if vals.max() <= 0 or np.std(vals) == 0:
            gi_results[f"gi_{key}"] = np.zeros(n).tolist()
            gi_results[f"gip_{key}"] = np.ones(n).tolist()
            continue
        try:
            gi = G_Local(vals, w, transform="R", permutations=999, seed=42)
            z = np.nan_to_num(np.asarray(gi.Zs, dtype=float), nan=0.0)
            p = np.nan_to_num(np.asarray(gi.p_sim, dtype=float), nan=1.0)
            gi_results[f"gi_{key}"] = z.tolist()
            gi_results[f"gip_{key}"] = p.tolist()
        except Exception as e:
            print(f"    Gi* 실패 {key}: {e}")
            gi_results[f"gi_{key}"] = np.zeros(n).tolist()
            gi_results[f"gip_{key}"] = np.ones(n).tolist()
    return gi_results


def round_geom(gj, nd=5):
    def r(c):
        return [round(c[0], nd), round(c[1], nd)]
    g = dict(gj)
    if gj["type"] == "Polygon":
        g["coordinates"] = [[r(c) for c in ring] for ring in gj["coordinates"]]
    elif gj["type"] == "MultiPolygon":
        g["coordinates"] = [[[r(c) for c in ring] for ring in poly] for poly in gj["coordinates"]]
    return g


def run_region(region, conf):
    print(f"\n=== {conf['label']} ({region}) ===")
    gdf = load_grid(conf["shp"])
    # 격자 본체만 유지 — Queen 비연결 외딴 이상치 셀 제거 (시 경계 밖 떠도는 셀)
    keep = largest_component_mask(gdf)
    if (~keep).sum():
        print(f"  외딴 셀 {int((~keep).sum())}개 제거 (Queen 연결요소 분리)")
        gdf = gdf[keep].reset_index(drop=True)
    pop_mask = gdf["val"].values > 0
    print(f"  격자 {len(gdf)}셀, 인구>0 {pop_mask.sum()}셀, val합 {gdf['val'].sum():.0f}")

    meds = load_medical(conf["med"])
    print(f"  의료기관 {len(meds)}개")

    grid_lats = gdf["centroid_lat"].values
    grid_lngs = gdf["centroid_lng"].values
    grid_pops = gdf["val"].values
    med_lats = np.array([m["lat"] for m in meds])
    med_lngs = np.array([m["lng"] for m in meds])

    sfca_results = {}
    for metric_key, metric_label in SUPPLY_METRICS.items():
        med_supply = np.array([m[f"supply_{metric_key}"] for m in meds])
        active = med_supply > 0
        if active.sum() == 0:
            continue
        for d0 in CATCHMENTS:
            sfca_results[f"2sfca_{metric_key}_{d0}"] = run_2sfca(
                grid_lats, grid_lngs, grid_pops,
                med_lats[active], med_lngs[active], med_supply[active], d0).tolist()
            sfca_results[f"e2sfca_{metric_key}_{d0}"] = run_e2sfca(
                grid_lats, grid_lngs, grid_pops,
                med_lats[active], med_lngs[active], med_supply[active], d0).tolist()
    print(f"  접근성 표면 {len(sfca_results)}개 계산")

    print("  Gi* (Queen) ...")
    gi_results = run_gi_star_queen(gdf, sfca_results)

    # 컬럼형 출력: geometry 는 {id,pop} 만, 값은 surface별 배열(키 반복 제거 → 용량↓)
    geoms = list(gdf.geometry)
    pops = gdf["val"].values
    features = [{
        "type": "Feature",
        "geometry": round_geom(geoms[i].__geo_interface__, 5),
        "properties": {"id": i, "pop": int(round(pops[i]))},
    } for i in range(len(gdf))]

    surfaces = {k: [round(v, 6) for v in vals] for k, vals in sfca_results.items()}
    gi = {}
    for k, vals in gi_results.items():
        nd = 3
        gi[k] = [round(v, nd) for v in vals]

    # 경계 = 격자 dissolve (시 외곽선)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        boundary = gdf.dissolve().geometry.iloc[0].simplify(0.0008)
    boundary_gj = round_geom(boundary.__geo_interface__, 5)

    meta = {
        "label": conf["label"],
        "catchments": CATCHMENTS,
        "methods": ["2sfca", "e2sfca"],
        "metrics": SUPPLY_METRICS,
        "grid_count": int(pop_mask.sum()),
        "grid_total": len(gdf),
        "med_count": len(meds),
        "center": [float(np.mean(grid_lats)), float(np.mean(grid_lngs))],
        "analyses": ["sfca", "gi_star"],
    }
    return {"meta": meta, "geojson": {"type": "FeatureCollection", "features": features},
            "surfaces": surfaces, "gi": gi, "boundary": boundary_gj}


def main():
    data = {region: run_region(region, conf) for region, conf in REGIONS.items()}
    out_path = os.path.join(BASE_DIR, "result.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("const SFCA_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"\n출력: {out_path} ({os.path.getsize(out_path) / 1024 / 1024:.2f} MB)")
    print("완료!")


if __name__ == "__main__":
    main()
