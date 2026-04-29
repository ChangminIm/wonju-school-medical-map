"""
2SFCA / E2SFCA + KDE + Getis-Ord Gi* Analysis
for Yongin Elementary School Medical Accessibility.
Outputs result.js + hotspot.js for web visualization.
"""
import geopandas as gpd
import numpy as np
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRID_SHP = os.path.join(BASE_DIR, "data", "YI_500m_elementary.shp")

CATCHMENTS = [1000, 3000, 5000]
SUPPLY_METRICS = {
    "ped": "소아청소년과 전문의",
    "inter": "내과 전문의",
    "ped_inter": "소아+내과 합계",
    "count": "기관 수",
}


def gaussian_weight(d, d0):
    if d > d0:
        return 0.0
    return np.exp(-0.5 * (d / (d0 / 2.5)) ** 2)


def load_grid():
    gdf = gpd.read_file(GRID_SHP)
    gdf_proj = gdf.copy()
    gdf = gdf.to_crs(epsg=4326)
    gdf["val"] = gdf["val"].fillna(0).astype(float)
    gdf["centroid_lat"] = gdf.geometry.centroid.y
    gdf["centroid_lng"] = gdf.geometry.centroid.x
    gdf_proj["val"] = gdf_proj["val"].fillna(0).astype(float)
    cx = gdf_proj.geometry.centroid.x.values
    cy = gdf_proj.geometry.centroid.y.values
    gdf["cx_proj"] = cx
    gdf["cy_proj"] = cy
    return gdf


def load_medical():
    json_path = os.path.join(BASE_DIR, "..", "map_data.json")
    with open(json_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)
    meds = all_data["yongin"]["medical"]
    result = []
    for m in meds:
        result.append({
            "name": m["name"],
            "type": m["type"],
            "category": m["category"],
            "lat": m["lat"],
            "lng": m["lng"],
            "ped": m["ped"],
            "inter": m["inter"],
            "supply_ped": m["ped"],
            "supply_inter": m["inter"],
            "supply_ped_inter": m["ped"] + m["inter"],
            "supply_count": 1,
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


def run_kde(gdf, results_dict, pop_mask):
    """KDE on accessibility scores for populated grid cells."""
    from scipy.stats import gaussian_kde

    sub = gdf[pop_mask].copy()
    coords = np.vstack([sub["cx_proj"].values, sub["cy_proj"].values])

    kde_results = {}
    for key, vals_all in results_dict.items():
        vals = np.array(vals_all)[pop_mask]
        if vals.max() <= 0:
            kde_results[f"kde_{key}"] = np.zeros(len(sub)).tolist()
            continue
        weights = vals.copy()
        weights[weights < 0] = 0
        if weights.sum() == 0:
            kde_results[f"kde_{key}"] = np.zeros(len(sub)).tolist()
            continue
        try:
            kde = gaussian_kde(coords, weights=weights, bw_method=0.15)
            density = kde(coords)
            dmin, dmax = density.min(), density.max()
            if dmax > dmin:
                density = (density - dmin) / (dmax - dmin)
            else:
                density = np.zeros_like(density)
            kde_results[f"kde_{key}"] = density.tolist()
        except Exception:
            kde_results[f"kde_{key}"] = np.zeros(len(sub)).tolist()
    return kde_results


def run_gi_star(gdf, results_dict, pop_mask):
    """Getis-Ord Gi* using KNN weights on populated cells only."""
    from libpysal.weights import KNN
    from esda.getisord import G_Local

    sub = gdf[pop_mask].copy().reset_index(drop=True)
    w = KNN.from_dataframe(sub, k=8)
    w.transform = "R"

    gi_results = {}
    for key, vals_all in results_dict.items():
        vals = np.array(vals_all)[pop_mask]
        if vals.max() <= 0 or np.std(vals) == 0:
            gi_results[f"gi_{key}"] = np.zeros(len(sub)).tolist()
            gi_results[f"gip_{key}"] = np.ones(len(sub)).tolist()
            continue
        try:
            gi = G_Local(vals, w, transform="R", permutations=999, seed=42)
            gi_results[f"gi_{key}"] = gi.Zs.tolist()
            gi_results[f"gip_{key}"] = gi.p_sim.tolist()
        except Exception as e:
            print(f"    Gi* failed for {key}: {e}")
            gi_results[f"gi_{key}"] = np.zeros(len(sub)).tolist()
            gi_results[f"gip_{key}"] = np.ones(len(sub)).tolist()
    return gi_results


def main():
    print("Loading grid data...")
    gdf = load_grid()
    pop_mask = gdf["val"].values > 0
    print(f"  {len(gdf)} grid cells, {pop_mask.sum()} with population")

    print("Loading medical data...")
    meds = load_medical()
    print(f"  {len(meds)} medical facilities")

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
            print(f"  Skipping {metric_label}: no active facilities")
            continue
        for d0 in CATCHMENTS:
            print(f"  Computing: {metric_label} / {d0}m ...")
            k2 = f"2sfca_{metric_key}_{d0}"
            ke = f"e2sfca_{metric_key}_{d0}"
            sfca_results[k2] = run_2sfca(
                grid_lats, grid_lngs, grid_pops,
                med_lats[active], med_lngs[active], med_supply[active], d0
            ).tolist()
            sfca_results[ke] = run_e2sfca(
                grid_lats, grid_lngs, grid_pops,
                med_lats[active], med_lngs[active], med_supply[active], d0
            ).tolist()

    # KDE
    print("Running KDE...")
    kde_results = run_kde(gdf, sfca_results, pop_mask)

    # Gi*
    print("Running Getis-Ord Gi*...")
    gi_results = run_gi_star(gdf, sfca_results, pop_mask)

    # Build GeoJSON (only populated cells)
    print("Building output...")
    gdf_pop = gdf[pop_mask].copy().reset_index(drop=True)
    features = []
    pop_indices = np.where(pop_mask)[0]

    for local_i, (_, row) in enumerate(gdf_pop.iterrows()):
        global_i = pop_indices[local_i]
        geom = row.geometry.__geo_interface__
        props = {"id": local_i, "pop": row["val"]}
        for key, vals in sfca_results.items():
            v = vals[global_i]
            props[key] = round(v, 8) if v > 0 else 0
        for key, vals in kde_results.items():
            props[key] = round(vals[local_i], 6)
        for key, vals in gi_results.items():
            props[key] = round(vals[local_i], 4)
        features.append({"type": "Feature", "geometry": geom, "properties": props})

    geojson = {"type": "FeatureCollection", "features": features}

    meta = {
        "catchments": CATCHMENTS,
        "methods": ["2sfca", "e2sfca"],
        "metrics": SUPPLY_METRICS,
        "grid_count": int(pop_mask.sum()),
        "grid_total": len(gdf),
        "med_count": len(meds),
        "analyses": ["sfca", "kde", "gi_star"],
    }

    out_path = os.path.join(BASE_DIR, "result.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("const SFCA_META = " + json.dumps(meta, ensure_ascii=False) + ";\n")
        f.write("const SFCA_GEOJSON = " + json.dumps(geojson, ensure_ascii=False) + ";\n")

    print(f"Output: {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")
    print("Done!")


if __name__ == "__main__":
    main()
