# -*- coding: utf-8 -*-
"""티센폴리곤 소아비만율 / Gi* 핫스팟 정적 PNG 렌더링 (초등/중학교)"""
import os, json, shutil, warnings
import numpy as np
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle, Polygon as MplPolygon
from matplotlib.lines import Line2D
import contextily as cx

from libpysal.weights import Queen
from esda.getisord import G_Local

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "maps")
os.makedirs(OUTDIR, exist_ok=True)

COLORS = ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"]
GI_COLORS = {
    "Hot 99%": "#dc2626",
    "Hot 95%": "#f87171",
    "Not Significant": "#e2e8f0",
    "Cold 95%": "#93c5fd",
    "Cold 99%": "#2563eb",
}
GI_ORDER = ["Hot 99%", "Hot 95%", "Not Significant", "Cold 95%", "Cold 99%"]

with open(os.path.join(BASE, "map_data.json"), encoding="utf-8") as f:
    ALL = json.load(f)
schools = ALL["wonju"]["schools"]
name_to_idx = {s["name"]: i for i, s in enumerate(schools)}
OVERRIDE = {}
if "원주중학교부설방송통신중학교" in name_to_idx and "원주중학교" in name_to_idx:
    OVERRIDE[name_to_idx["원주중학교부설방송통신중학교"]] = name_to_idx["원주중학교"]

CONF = {
    "elementary": {
        "shp": "원주시_초등학교_티센.shp",
        "lvname": "초등학교",
        "title_rate": "원주시 초등학교 소아비만율 분포",
        "title_gi": "원주시 초등학교 소아비만율 Gi* 핫스팟",
        "out_rate": "원주_초등학교_소아비만율.png",
        "out_gi": "원주_초등학교_소아비만_Gi.png",
        "alt_rate": "wonju_elem_obesity.png",
        "alt_gi": "wonju_elem_gi.png",
    },
    "middle": {
        "shp": "원주시_중학교_티센.shp",
        "lvname": "중학교",
        "title_rate": "원주시 중학교 소아비만율 분포",
        "title_gi": "원주시 중학교 소아비만율 Gi* 핫스팟",
        "out_rate": "원주_중학교_소아비만율.png",
        "out_gi": "원주_중학교_소아비만_Gi.png",
        "alt_rate": "wonju_mid_obesity.png",
        "alt_gi": "wonju_mid_gi.png",
    },
}


def quantile_breaks(values, n=5):
    arr = np.array(values, dtype=float)
    qs = np.quantile(arr, [i / n for i in range(n + 1)])
    out = []
    for q in qs:
        r = round(float(q), 1)
        if not out or r > out[-1]:
            out.append(r)
    return out


def class_index(rate, breaks):
    for i in range(len(breaks) - 1):
        if rate <= breaks[i + 1]:
            return i
    return len(breaks) - 2


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


def compute_gi(gdf, color_rates):
    """gdf 행 순서에 맞춘 obeseRate(color_rates)로 Queen Gi* → giClass 리스트"""
    n = len(gdf)
    out = [None] * n
    rates = np.array([np.nan if v is None else float(v) for v in color_rates], dtype=float)
    valid = ~np.isnan(rates)
    if valid.sum() < 2:
        return out
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
            out[i] = classify_gi(float(gi.Zs[i]), float(gi.p_sim[i]))
    except Exception as e:
        print(f"  Gi* 실패: {e}")
    return out


def render_map(gdf, pgdf, title, legend_items, legend_title, lvname_label, outpath):
    """공통 렌더링: OSM NoLabels + 노스애로우 + 10km 스케일바.
    gdf 는 EPSG:5179, 'fill' 컬럼에 색상 hex 가 들어 있어야 함."""
    fig, ax = plt.subplots(figsize=(8.8, 9.6), dpi=150)
    fig.patch.set_facecolor("white")

    gdf.plot(ax=ax, color=gdf["fill"], edgecolor="white", linewidth=0.7, alpha=0.82)
    try:
        outline = gdf.dissolve()
        outline.boundary.plot(ax=ax, color="#555555", linewidth=1.1)
    except Exception:
        pass
    pgdf.plot(ax=ax, color="#222222", markersize=18, edgecolor="white", linewidth=0.6, zorder=5)

    minx, miny, maxx, maxy = gdf.total_bounds
    w = maxx - minx
    h = maxy - miny
    ax.set_xlim(minx - w * 0.03, maxx + w * 0.03)
    ax.set_ylim(miny - h * 0.03, maxy + h * 0.03)

    cx.add_basemap(ax, source=cx.providers.CartoDB.PositronNoLabels, attribution=False, crs=gdf.crs)

    ax.set_axis_off()
    ax.set_title(title, fontsize=18, fontweight="bold", pad=14)

    leg = ax.legend(handles=legend_items, title=legend_title, loc="upper right",
                    fontsize=10, title_fontsize=11, frameon=True, framealpha=0.95,
                    borderpad=0.8, labelspacing=0.7, handleheight=1.7, handlelength=2.0)
    leg.get_frame().set_edgecolor("#dddddd")

    fig.canvas.draw()
    inv = ax.transData.inverted()
    lbb = leg.get_window_extent().transformed(inv)
    leg_right = lbb.x1
    leg_top = lbb.y1

    # 노스애로우 (좌상단)
    tw = w * 0.020
    nax = minx + tw / 2
    ntxt = ax.text(nax, leg_top, "N", ha="center", va="top",
                   fontsize=13, color="#222", zorder=7)
    fig.canvas.draw()
    nbb = ntxt.get_window_extent().transformed(inv)
    apex_y = nbb.y0 - h * 0.002
    th = tw * 1.5
    base_y = apex_y - th
    ax.add_patch(MplPolygon([[nax - tw / 2, base_y], [nax + tw / 2, base_y], [nax, apex_y]],
                            closed=True, facecolor="#222", edgecolor="#222", zorder=7))

    # 스케일바 (우하단, 10km)
    bar_len = 10000.0
    pad = w * 0.012
    gap = w * 0.004
    km_w = w * 0.042
    box_w = pad + bar_len + gap + km_w
    box_right = leg_right
    box_left = box_right - box_w
    box_bottom = miny
    inner = h * 0.014
    inner_top = inner * 0.55
    bar_h = h * 0.006
    bar_x0 = box_left + pad
    bar_x1 = bar_x0 + bar_len
    bar_mid = (bar_x0 + bar_x1) / 2
    bar_y = box_bottom + inner
    label_y = bar_y + bar_h + h * 0.003
    label_texts = []
    for xv, lab in [(bar_x0, "0"), (bar_mid, "5"), (bar_x1, "10")]:
        label_texts.append(ax.text(xv, label_y, lab, ha="center", va="bottom",
                                    fontsize=8, color="#222", zorder=7))
    fig.canvas.draw()
    label_top = max(t.get_window_extent().transformed(inv).y1 for t in label_texts)
    box_top = label_top + inner_top
    box_h = box_top - box_bottom
    ax.add_patch(Rectangle((box_left, box_bottom), box_w, box_h,
                           facecolor="white", edgecolor="#bbbbbb", lw=0.8, zorder=6))
    ax.add_patch(Rectangle((bar_x0, bar_y), bar_len, bar_h,
                           facecolor="white", edgecolor="#222", lw=0.9, zorder=7))
    ax.plot([bar_mid, bar_mid], [bar_y, bar_y + bar_h], color="#222", lw=0.9, zorder=7)
    ax.text(bar_x1 + gap, bar_y + bar_h / 2, "Km", ha="left", va="center",
            fontsize=8, color="#222", zorder=7)

    plt.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.02)
    fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


for level, c in CONF.items():
    gdf = gpd.read_file(os.path.join(BASE, "data", "thiessen", c["shp"]), encoding="cp949")
    rates, obeses, names = [], [], []
    for _, row in gdf.iterrows():
        fid = int(row["Input_FID"])
        ci = OVERRIDE.get(fid, fid)
        sch = schools[ci]
        rates.append(sch.get("obeseRate"))
        obeses.append(sch.get("obese"))
        names.append(sch["name"])
    gdf["rate"] = rates

    # Gi* (4326 좌표계에서 인접 판정)
    gi_class = compute_gi(gdf, rates)
    gdf["giClass"] = gi_class

    # 미터 좌표계(EPSG:5179)로 변환 - 거리(스케일바) 정확도
    gdf = gdf.to_crs(epsg=5179)
    pts = [s for s in schools if s["level"] == c["lvname"]]
    pgdf = gpd.GeoDataFrame(
        {"name": [s["name"] for s in pts]},
        geometry=[Point(s["lng"], s["lat"]) for s in pts],
        crs="EPSG:4326",
    ).to_crs(epsg=5179)

    # ─── 비만율 지도 ─────────────────────────────────
    breaks = quantile_breaks([r for r in rates if r is not None], 5)
    gdf["cidx"] = gdf["rate"].apply(lambda r: class_index(r, breaks) if r is not None else -1)
    gdf["fill"] = gdf["cidx"].apply(lambda i: COLORS[min(i, len(COLORS) - 1)] if i >= 0 else "#dddddd")

    legend_items_rate = []
    for i in range(len(breaks) - 2, -1, -1):
        legend_items_rate.append(Patch(facecolor=COLORS[i], edgecolor="#999",
                                       label="%.1f ~ %.1f%%" % (breaks[i], breaks[i + 1])))
    legend_items_rate.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#222",
                                    markeredgecolor="white", markersize=8, label=c["lvname"]))
    out_rate = os.path.join(OUTDIR, c["out_rate"])
    render_map(gdf, pgdf, c["title_rate"], legend_items_rate, "추정 소아비만율",
               c["lvname"], out_rate)
    shutil.copyfile(out_rate, os.path.join(OUTDIR, c["alt_rate"]))
    sz = os.path.getsize(out_rate) / 1024
    print("저장: %s (%.1f KB) breaks=%s, 학교 %d개" % (c["out_rate"], sz, breaks, len(pts)))

    # ─── Gi* 핫스팟 지도 ───────────────────────────
    gdf["fill"] = gdf["giClass"].apply(lambda g: GI_COLORS.get(g, "#dddddd"))
    counts = {}
    for g in gi_class:
        if g is None:
            continue
        counts[g] = counts.get(g, 0) + 1
    legend_items_gi = []
    for cls in GI_ORDER:
        n = counts.get(cls, 0)
        legend_items_gi.append(Patch(facecolor=GI_COLORS[cls], edgecolor="#999",
                                     label="%s (%d)" % (cls, n)))
    legend_items_gi.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#222",
                                  markeredgecolor="white", markersize=8, label=c["lvname"]))
    out_gi = os.path.join(OUTDIR, c["out_gi"])
    render_map(gdf, pgdf, c["title_gi"], legend_items_gi, "Gi* (Queen, p<0.05/0.01)",
               c["lvname"], out_gi)
    shutil.copyfile(out_gi, os.path.join(OUTDIR, c["alt_gi"]))
    sz = os.path.getsize(out_gi) / 1024
    print("저장: %s (%.1f KB) Gi* counts=%s" % (c["out_gi"], sz, counts))


# ──────────────────────────────────────────────────────────────
# 원주 초등 통학구역 비만율 / Gi* PNG (school_area.js 기반 — 값/Gi*는 재계산 없이 그대로 사용)
# ──────────────────────────────────────────────────────────────
sa_txt = open(os.path.join(BASE, "school_area.js"), encoding="utf-8").read()
SA = json.loads(sa_txt[sa_txt.index("{"):sa_txt.rindex("}") + 1])
sa_gdf = gpd.GeoDataFrame.from_features(SA["features"], crs="EPSG:4326").to_crs(epsg=5179)
sa_breaks = SA["breaks"]

epts = [s for s in schools if s["level"] == "초등학교"]
sa_pgdf = gpd.GeoDataFrame(
    {"name": [s["name"] for s in epts]},
    geometry=[Point(s["lng"], s["lat"]) for s in epts],
    crs="EPSG:4326",
).to_crs(epsg=5179)

# ─── 비만율 지도 ─────────────────────────────────
sa_gdf["cidx"] = sa_gdf["obeseRate"].apply(lambda r: class_index(r, sa_breaks) if r is not None else -1)
sa_gdf["fill"] = sa_gdf["cidx"].apply(lambda i: COLORS[min(i, len(COLORS) - 1)] if i >= 0 else "#dddddd")
legend_items_rate = []
for i in range(len(sa_breaks) - 2, -1, -1):
    legend_items_rate.append(Patch(facecolor=COLORS[i], edgecolor="#999",
                                   label="%.1f ~ %.1f%%" % (sa_breaks[i], sa_breaks[i + 1])))
legend_items_rate.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#222",
                                markeredgecolor="white", markersize=8, label="초등학교"))
sa_out_rate = os.path.join(OUTDIR, "원주_초등학교_통학구역_소아비만율.png")
render_map(sa_gdf, sa_pgdf, "원주시 초등학교 통학구역 소아비만율 분포",
           legend_items_rate, "추정 소아비만율", "초등학교", sa_out_rate)
shutil.copyfile(sa_out_rate, os.path.join(OUTDIR, "wonju_elem_area_obesity.png"))
print("저장: 원주_초등학교_통학구역_소아비만율.png (%.1f KB) breaks=%s, 구역 %d개"
      % (os.path.getsize(sa_out_rate) / 1024, sa_breaks, len(sa_gdf)))

# ─── Gi* 핫스팟 지도 ───────────────────────────
sa_gdf["fill"] = sa_gdf["giClass"].apply(lambda g: GI_COLORS.get(g, "#dddddd"))
sa_counts = SA["giCounts"]
legend_items_gi = []
for cls in GI_ORDER:
    legend_items_gi.append(Patch(facecolor=GI_COLORS[cls], edgecolor="#999",
                                 label="%s (%d)" % (cls, sa_counts.get(cls, 0))))
legend_items_gi.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#222",
                              markeredgecolor="white", markersize=8, label="초등학교"))
sa_out_gi = os.path.join(OUTDIR, "원주_초등학교_통학구역_소아비만_Gi.png")
render_map(sa_gdf, sa_pgdf, "원주시 초등학교 통학구역 소아비만율 Gi* 핫스팟",
           legend_items_gi, "Gi* (Queen, p<0.05/0.01)", "초등학교", sa_out_gi)
shutil.copyfile(sa_out_gi, os.path.join(OUTDIR, "wonju_elem_area_gi.png"))
print("저장: 원주_초등학교_통학구역_소아비만_Gi.png (%.1f KB) Gi* counts=%s"
      % (os.path.getsize(sa_out_gi) / 1024, sa_counts))
