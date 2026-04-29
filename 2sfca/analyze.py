"""
2SFCA & E2SFCA Analysis for Yongin Elementary School Accessibility
Outputs result.js for web visualization.
"""
import geopandas as gpd
import numpy as np
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRID_SHP = os.path.join(BASE_DIR, "data", "YI_500m_elementary.shp")

# Medical data from parent project
import sys
sys.path.insert(0, os.path.join(BASE_DIR, ".."))

CATCHMENTS = [1000, 3000, 5000]  # meters
SUPPLY_METRICS = {
    "ped": "소아청소년과 전문의",
    "inter": "내과 전문의",
    "ped_inter": "소아+내과 합계",
    "count": "기관 수",
}

def gaussian_weight(d, d0):
    """Gaussian distance decay. d and d0 in same units (meters)."""
    if d > d0:
        return 0.0
    return np.exp(-0.5 * (d / (d0 / 2.5)) ** 2)


def load_grid():
    gdf = gpd.read_file(GRID_SHP)
    gdf = gdf.to_crs(epsg=4326)
    gdf["val"] = gdf["val"].fillna(0).astype(float)
    gdf["centroid_lat"] = gdf.geometry.centroid.y
    gdf["centroid_lng"] = gdf.geometry.centroid.x
    return gdf


def load_medical():
    """Load Yongin medical data from the parent map_data.json."""
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
    """Vectorized haversine distance in meters."""
    R = 6371000
    lat1, lng1, lat2, lng2 = map(np.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def run_2sfca(grid_lats, grid_lngs, grid_pops, med_lats, med_lngs, med_supply, d0):
    """Standard 2SFCA (binary catchment)."""
    n_grid = len(grid_lats)
    n_med = len(med_lats)

    # Step 1: For each medical facility, compute R_j = S_j / sum(D_k) for demand points within d0
    R = np.zeros(n_med)
    for j in range(n_med):
        dists = haversine_meters(med_lats[j], med_lngs[j], grid_lats, grid_lngs)
        mask = dists <= d0
        pop_sum = grid_pops[mask].sum()
        if pop_sum > 0 and med_supply[j] > 0:
            R[j] = med_supply[j] / pop_sum

    # Step 2: For each demand point, sum R_j for facilities within d0
    A = np.zeros(n_grid)
    for i in range(n_grid):
        dists = haversine_meters(grid_lats[i], grid_lngs[i], np.array(med_lats), np.array(med_lngs))
        mask = dists <= d0
        A[i] = R[mask].sum()

    return A


def run_e2sfca(grid_lats, grid_lngs, grid_pops, med_lats, med_lngs, med_supply, d0):
    """Enhanced 2SFCA with Gaussian distance decay."""
    n_grid = len(grid_lats)
    n_med = len(med_lats)

    # Step 1
    R = np.zeros(n_med)
    for j in range(n_med):
        dists = haversine_meters(med_lats[j], med_lngs[j], grid_lats, grid_lngs)
        weights = np.array([gaussian_weight(d, d0) for d in dists])
        weighted_pop = (grid_pops * weights).sum()
        if weighted_pop > 0 and med_supply[j] > 0:
            R[j] = med_supply[j] / weighted_pop

    # Step 2
    A = np.zeros(n_grid)
    for i in range(n_grid):
        dists = haversine_meters(grid_lats[i], grid_lngs[i], np.array(med_lats), np.array(med_lngs))
        weights = np.array([gaussian_weight(d, d0) for d in dists])
        A[i] = (R * weights).sum()

    return A


def main():
    print("Loading grid data...")
    gdf = load_grid()
    print(f"  {len(gdf)} grid cells, {(gdf['val']>0).sum()} with population")

    print("Loading medical data...")
    meds = load_medical()
    print(f"  {len(meds)} medical facilities")

    grid_lats = gdf["centroid_lat"].values
    grid_lngs = gdf["centroid_lng"].values
    grid_pops = gdf["val"].values

    med_lats = np.array([m["lat"] for m in meds])
    med_lngs = np.array([m["lng"] for m in meds])

    results = {}

    for metric_key, metric_label in SUPPLY_METRICS.items():
        med_supply = np.array([m[f"supply_{metric_key}"] for m in meds])
        # Skip facilities with 0 supply for specialist metrics
        active = med_supply > 0
        if active.sum() == 0:
            print(f"  Skipping {metric_label}: no active facilities")
            continue

        for d0 in CATCHMENTS:
            print(f"  Computing: {metric_label} / {d0}m ...")
            key_2sfca = f"2sfca_{metric_key}_{d0}"
            key_e2sfca = f"e2sfca_{metric_key}_{d0}"

            a_2sfca = run_2sfca(grid_lats, grid_lngs, grid_pops,
                                med_lats[active], med_lngs[active], med_supply[active], d0)
            a_e2sfca = run_e2sfca(grid_lats, grid_lngs, grid_pops,
                                  med_lats[active], med_lngs[active], med_supply[active], d0)

            results[key_2sfca] = a_2sfca.tolist()
            results[key_e2sfca] = a_e2sfca.tolist()

    # Build GeoJSON
    print("Building GeoJSON output...")
    gdf_out = gdf.to_crs(epsg=4326)
    features = []
    for i, row in gdf_out.iterrows():
        geom = row.geometry.__geo_interface__
        props = {"id": i, "pop": row["val"]}
        for key, vals in results.items():
            props[key] = round(vals[i], 8) if vals[i] > 0 else 0
        features.append({"type": "Feature", "geometry": geom, "properties": props})

    geojson = {"type": "FeatureCollection", "features": features}

    # Metadata
    meta = {
        "catchments": CATCHMENTS,
        "methods": ["2sfca", "e2sfca"],
        "metrics": SUPPLY_METRICS,
        "grid_count": len(gdf),
        "med_count": len(meds),
    }

    out_path = os.path.join(BASE_DIR, "result.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("const SFCA_META = " + json.dumps(meta, ensure_ascii=False) + ";\n")
        f.write("const SFCA_GEOJSON = " + json.dumps(geojson, ensure_ascii=False) + ";\n")

    print(f"Output: {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")
    print("Done!")


if __name__ == "__main__":
    main()
