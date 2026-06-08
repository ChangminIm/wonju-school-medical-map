# -*- coding: utf-8 -*-
"""티센폴리곤 소아비만율 단계구분도 정적 PNG 렌더링 (초등/중학교)"""
import os, json
import numpy as np
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import contextily as cx

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "maps")
os.makedirs(OUTDIR, exist_ok=True)

COLORS = ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"]

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
        "title": "원주시 초등학교 소아비만율 분포",
        "lvname": "초등학교",
        "out": "원주_초등학교_소아비만율.png",
    },
    "middle": {
        "shp": "원주시_중학교_티센.shp",
        "title": "원주시 중학교 소아비만율 분포",
        "lvname": "중학교",
        "out": "원주_중학교_소아비만율.png",
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
    breaks = quantile_breaks([r for r in rates if r is not None], 5)
    gdf["cidx"] = gdf["rate"].apply(lambda r: class_index(r, breaks) if r is not None else -1)
    gdf["fill"] = gdf["cidx"].apply(lambda i: COLORS[min(i, len(COLORS) - 1)] if i >= 0 else "#dddddd")

    # 미터 좌표계(EPSG:5179, UTM-K)로 변환 - 거리(스케일바) 정확도 확보
    gdf = gdf.to_crs(epsg=5179)
    pts = [s for s in schools if s["level"] == c["lvname"]]
    pgdf = gpd.GeoDataFrame(
        {"name": [s["name"] for s in pts]},
        geometry=[Point(s["lng"], s["lat"]) for s in pts],
        crs="EPSG:4326",
    ).to_crs(epsg=5179)

    fig, ax = plt.subplots(figsize=(8.8, 9.6), dpi=150)
    fig.patch.set_facecolor("white")

    gdf.plot(ax=ax, color=gdf["fill"], edgecolor="white", linewidth=0.7, alpha=0.82)
    try:
        outline = gdf.dissolve()
        outline.boundary.plot(ax=ax, color="#555555", linewidth=1.1)
    except Exception:
        pass
    pgdf.plot(ax=ax, color="#222222", markersize=18, edgecolor="white", linewidth=0.6, zorder=5)

    # 행정구역 우측 끝선 정도로만 여백 확보
    minx, miny, maxx, maxy = gdf.total_bounds
    w = maxx - minx
    h = maxy - miny
    ax.set_xlim(minx - w * 0.03, maxx + w * 0.03)
    ax.set_ylim(miny - h * 0.03, maxy + h * 0.03)  # 상하 여백 대칭

    # OSM 그레이(밝은 회색) 배경 - 지명 라벨 없음
    cx.add_basemap(ax, source=cx.providers.CartoDB.PositronNoLabels, attribution=False, crs=gdf.crs)

    ax.set_axis_off()
    ax.set_title(c["title"], fontsize=18, fontweight="bold", pad=14)

    from matplotlib.patches import Rectangle, Polygon as MplPolygon

    # 범례 (높은 수 → 낮은 수)
    legend_items = []
    for i in range(len(breaks) - 2, -1, -1):
        legend_items.append(Patch(facecolor=COLORS[i], edgecolor="#999",
                                   label="%.1f ~ %.1f%%" % (breaks[i], breaks[i + 1])))
    legend_items.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#222",
                               markeredgecolor="white", markersize=8, label=c["lvname"]))
    leg = ax.legend(handles=legend_items, title="추정 소아비만율", loc="upper right",
                    fontsize=10, title_fontsize=11, frameon=True, framealpha=0.95,
                    borderpad=0.8, labelspacing=0.7, handleheight=1.7, handlelength=2.0)
    leg.get_frame().set_edgecolor("#dddddd")

    # 범례 실제 위치(데이터 좌표) 측정 → 노스애로우/스케일바 정렬 기준
    fig.canvas.draw()
    inv = ax.transData.inverted()
    lbb = leg.get_window_extent().transformed(inv)
    leg_right = lbb.x1
    leg_top = lbb.y1

    # 노스 애로우 (좌상단) - 위 끝선 = 범례 위 끝선, 왼쪽 끝선 = 행정경계 왼쪽 끝선
    tw = w * 0.020
    nax = minx + tw / 2
    ntxt = ax.text(nax, leg_top, "N", ha="center", va="top",
                   fontsize=13, color="#222", zorder=7)
    fig.canvas.draw()
    nbb = ntxt.get_window_extent().transformed(inv)
    apex_y = nbb.y0 - h * 0.002  # N과 삼각형 가깝게
    th = tw * 1.5  # 세로가 더 긴 이등변삼각형
    base_y = apex_y - th
    ax.add_patch(MplPolygon([[nax - tw / 2, base_y], [nax + tw / 2, base_y], [nax, apex_y]],
                            closed=True, facecolor="#222", edgecolor="#222", zorder=7))

    # 스케일바 (우하단, 흰 박스, 최대 10km) - 오른쪽 끝선=범례 오른쪽, 아래 끝선=행정경계 하단
    bar_len = 10000.0
    pad = w * 0.012
    gap = w * 0.004
    km_w = w * 0.042
    box_w = pad + bar_len + gap + km_w
    box_right = leg_right
    box_left = box_right - box_w
    box_bottom = miny
    inner = h * 0.014  # 바-박스 아래 여백
    inner_top = inner * 0.55  # 위 여백은 아래보다 살짝 좁게
    bar_h = h * 0.006
    bar_x0 = box_left + pad
    bar_x1 = bar_x0 + bar_len
    bar_mid = (bar_x0 + bar_x1) / 2
    bar_y = box_bottom + inner
    label_y = bar_y + bar_h + h * 0.003
    # 라벨 먼저 그려 상단 위치 측정 → 위 여백을 아래 여백과 동일하게
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
    outpath = os.path.join(OUTDIR, c["out"])
    fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    sz = os.path.getsize(outpath) / 1024
    print("저장: %s (%.1f KB) breaks=%s, 학교 %d개" % (c["out"], sz, breaks, len(pts)))
