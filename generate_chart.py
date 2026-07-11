#!/usr/bin/env python3
"""
generate_chart.py — builds the single-page Bible chart PDF from bible_data.yaml.

Usage:
    python generate_chart.py
    python generate_chart.py --data bible_data.yaml --output bible_at_a_glance.pdf
    python generate_chart.py --page-size a4
    python generate_chart.py --page-size 13x9   (custom, inches, landscape)

All text content (title, summary, timeline, book names/summaries, colors,
section groupings) lives in the YAML data file — this script only handles
layout, auto-sizing text to fit, and drawing. Edit the .yaml, rerun this
script, and every font size / wrap / card size recalculates automatically.

Requires: matplotlib, pyyaml   (pip install matplotlib pyyaml)
"""

import argparse
import math
import sys

import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch

PAGE_PRESETS = {
    "letter": (11.0, 8.5),
    "a4": (11.69, 8.27),
    "tabloid": (17.0, 11.0),
}


# ---------------------------------------------------------------- utilities
def tint(hexc, amt):
    """Blend a hex color toward white by `amt` (0-1)."""
    r, g, b = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
    r = int(r + (255 - r) * amt)
    g = int(g + (255 - g) * amt)
    b = int(b + (255 - b) * amt)
    return f"#{r:02x}{g:02x}{b:02x}"


def shade(hexc, amt):
    """Blend a hex color toward black by `amt` (0-1)."""
    r, g, b = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
    r, g, b = int(r * (1 - amt)), int(g * (1 - amt)), int(b * (1 - amt))
    return f"#{r:02x}{g:02x}{b:02x}"


def parse_page_size(spec):
    if spec in PAGE_PRESETS:
        return PAGE_PRESETS[spec]
    if "x" in spec:
        w, h = spec.lower().split("x")
        return float(w), float(h)
    raise ValueError(f"Unrecognized --page-size {spec!r}. Use letter, a4, tabloid, or WxH (inches).")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="bible_data.yaml", help="Path to YAML data file")
    ap.add_argument("--output", default="bible_at_a_glance.pdf", help="Output PDF path")
    ap.add_argument("--page-size", default="letter", help="letter | a4 | tabloid | WxH in inches (e.g. 13x9)")
    ap.add_argument("--portrait", action="store_true", help="Use portrait instead of landscape orientation")
    ap.add_argument("--dpi", type=int, default=190, help="Render DPI (affects on-screen preview quality only; PDF stays vector)")
    args = ap.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    fig_w, fig_h = parse_page_size(args.page_size)
    if args.portrait and fig_w > fig_h:
        fig_w, fig_h = fig_h, fig_w
    if not args.portrait and fig_h > fig_w:
        fig_w, fig_h = fig_h, fig_w

    BG = "#F7F3E9"
    INK = "#26221a"
    M = 2.2  # outer margin in 0-100 coordinate units

    fig = plt.figure(figsize=(fig_w, fig_h), dpi=args.dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 100, 100, facecolor=BG, edgecolor="none", zorder=0))

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()

    def measure(s, fontsize, weight="normal"):
        t = ax.text(0, 0, s, fontsize=fontsize, fontweight=weight)
        bb = t.get_window_extent(renderer=renderer)
        t.remove()
        (x0, y0), (x1, y1) = inv.transform([(0, 0), (bb.width, bb.height)])
        return x1 - x0, y1 - y0

    def wrap_to_width(text, fontsize, max_w, weight="normal"):
        words = text.split()
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            tw, _ = measure(trial, fontsize, weight)
            if tw <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    # -------------------------------------------------- title
    ax.text(50, 95.9, data["title"], ha="center", va="center",
            fontsize=18, fontweight="bold", family="serif", color="#7c2d12")

    # -------------------------------------------------- testament sections (measured first)
    # Cards are sized to the minimum height their content needs at TARGET_CARD_FS
    # (falling back to a smaller size only if that would blow the page budget).
    # Whatever height this saves versus the old fixed-band layout is handed to
    # the summary box above, so its font can grow to fill the space.
    SEC_HDR_H = 2.2
    GAP_X = 0.30
    GAP_Y = 0.34
    TEST_GAP = 1.1
    BOTTOM_ANCHOR = 2.6  # y-coordinate the last testament band's bottom edge sits on
    TL_H = 3.9
    TL_GAP_ABOVE = 1.0   # gap between top of testament grids and the timeline
    SM_TL_GAP = 0.6      # gap between summary box and timeline
    SM_TOP = 93.6         # top of summary box, just under the title
    MIN_SUMMARY_H = 4.0

    def flatten(sections):
        out = []
        for sec in sections:
            for book in sec["books"]:
                out.append((sec["name"], sec["color"], book["name"], book["summary"]))
        return out

    STRIP_H = 0.18
    STRIP_TOP_GAP = 0.08
    NAME_TOP_GAP = 0.14
    NAME_SUM_GAP = 0.10
    BOTTOM_PAD = 0.12
    CARD_PAD = 0.32

    def layout_section(sections, rows, target_sfs):
        items = flatten(sections)
        ncols = max(1, math.ceil(len(items) / rows))
        nrows = math.ceil(len(items) / ncols)
        cell_w = (100 - 2 * M - (ncols - 1) * GAP_X) / ncols
        inner_w = cell_w - 2 * CARD_PAD

        nfs = 7.2 if ncols >= 9 else 8.6
        while nfs > 5.0:
            if all(len(wrap_to_width(b, nfs, inner_w, "bold")) <= 2 for _, _, b, _ in items):
                break
            nfs -= 0.2
        _, name_lh = measure("Ag", nfs, "bold")

        def name_lines_for(book):
            return wrap_to_width(book, nfs, inner_w, "bold")

        _, sum_lh = measure("Ag", target_sfs)
        cell_h = 0.0
        for _, _, book, summ in items:
            nlines = len(name_lines_for(book))
            name_block_h = nlines * name_lh * 1.08
            fixed_h = STRIP_TOP_GAP + STRIP_H + NAME_TOP_GAP + name_block_h + NAME_SUM_GAP + BOTTOM_PAD
            lines_ = wrap_to_width(summ, target_sfs, inner_w)
            cell_h = max(cell_h, fixed_h + len(lines_) * sum_lh * 1.24)

        band_h = cell_h * nrows + (nrows - 1) * GAP_Y + SEC_HDR_H + 0.5
        return {
            "items": items, "ncols": ncols, "nrows": nrows, "cell_w": cell_w, "cell_h": cell_h,
            "inner_w": inner_w, "nfs": nfs, "name_lh": name_lh, "sfs": target_sfs, "band_h": band_h,
            "name_lines_for": name_lines_for,
        }

    testament_keys = list(data["testaments"].keys())
    n_test = len(testament_keys)

    # Fixed at 5.5pt per design; auto-shrinks only if that would leave the
    # summary box smaller than MIN_SUMMARY_H (safety net for future edits).
    target_sfs = 5.5
    while True:
        layouts = {key: layout_section(data["testaments"][key]["sections"],
                                        data["testaments"][key].get("rows", 3), target_sfs)
                   for key in testament_keys}
        total_bands = sum(l["band_h"] for l in layouts.values()) + TEST_GAP * (n_test - 1)
        top_of_sections = BOTTOM_ANCHOR + total_bands
        tl_top = top_of_sections + TL_H + TL_GAP_ABOVE
        sm_bot = tl_top + SM_TL_GAP
        if SM_TOP - sm_bot >= MIN_SUMMARY_H or target_sfs <= 3.6:
            break
        target_sfs -= 0.1

    # -------------------------------------------------- summary band
    sm_top = SM_TOP
    ax.add_patch(FancyBboxPatch((M, sm_bot), 100 - 2 * M, sm_top - sm_bot,
                                 boxstyle="round,pad=0,rounding_size=0.6", facecolor="#FFFFFF",
                                 edgecolor="#d8cdb5", linewidth=1.2, zorder=1))
    pad_x, pad_y = 0.7, 0.3
    avail_w = (100 - 2 * M) - 2 * pad_x
    avail_h = (sm_top - sm_bot) - 2 * pad_y
    LS = 1.38
    summary_text = " ".join(data["summary"].split())  # normalize whitespace/newlines
    fs = 16.0
    while fs > 4.0:
        lines = wrap_to_width(summary_text, fs, avail_w)
        _, lh = measure("Ag", fs)
        if len(lines) * lh * LS <= avail_h:
            break
        fs -= 0.1
    ax.text(M + pad_x, (sm_top + sm_bot) / 2, "\n".join(lines), ha="left", va="center",
            fontsize=fs, color=INK, linespacing=LS)

    # -------------------------------------------------- timeline
    TL_C = "#8a7a5f"
    TL_DATE = "#a08e6d"
    era_colors = {key: t["bar_color"] for key, t in data["testaments"].items()}
    tl_h = TL_H
    tl_mid = tl_top - tl_h / 2
    tl_x0, tl_x1 = M + 4.0, 100 - M - 4.0

    events = data.get("timeline", [])
    n = len(events)
    if n >= 2:
        step = (tl_x1 - tl_x0) / (n - 1)
        xs = [tl_x0 + i * step for i in range(n)]
        break_idxs = [i for i, e in enumerate(events) if "break" in e]
        seg_start = tl_x0
        for bi in break_idxs:
            ax.plot([seg_start, xs[bi] - 0.9], [tl_mid, tl_mid], color=TL_C, lw=0.9,
                    solid_capstyle="round", zorder=1)
            seg_start = xs[bi] + 0.9
        ax.plot([seg_start, tl_x1], [tl_mid, tl_mid], color=TL_C, lw=0.9,
                solid_capstyle="round", zorder=1)
        arrow_tip = tl_x1 + 3.2
        ax.add_patch(FancyArrowPatch((tl_x1, tl_mid), (arrow_tip, tl_mid),
                                      arrowstyle="-|>", mutation_scale=6.5, linewidth=0.9,
                                      color=TL_C, zorder=1))
        arrow_tip_left = tl_x0 - 3.2
        ax.add_patch(FancyArrowPatch((tl_x0, tl_mid), (arrow_tip_left, tl_mid),
                                      arrowstyle="-|>", mutation_scale=6.5, linewidth=0.9,
                                      color=TL_C, zorder=1))
        for bi in break_idxs:
            bx = xs[bi]
            for dx in (-0.25, 0.25):
                ax.plot([bx + dx - 0.18, bx + dx + 0.18], [tl_mid - 0.35, tl_mid + 0.35],
                        color=TL_C, lw=0.8, zorder=2)
            ax.text(bx, tl_mid + 0.85, events[bi]["break"], ha="center", va="bottom",
                    fontsize=4.2, style="italic", color=TL_DATE, zorder=2)

        side = 1
        for i, e in enumerate(events):
            if "break" in e:
                continue
            x = xs[i]
            color = era_colors.get(e.get("era"), TL_C)
            ax.plot([x], [tl_mid], marker="o", markersize=2.6, color=color,
                    markeredgecolor="white", markeredgewidth=0.4, zorder=3)
            if side > 0:
                ax.text(x, tl_mid + 1.55, e["name"], ha="center", va="bottom",
                        fontsize=5.0, fontweight="bold", color=TL_C, zorder=2)
                ax.text(x, tl_mid + 0.50, e["date"], ha="center", va="bottom",
                        fontsize=4.6, color=TL_DATE, zorder=2)
            else:
                ax.text(x, tl_mid - 0.55, e["name"], ha="center", va="top",
                        fontsize=5.0, fontweight="bold", color=TL_C, zorder=2)
                ax.text(x, tl_mid - 1.75, e["date"], ha="center", va="top",
                        fontsize=4.6, color=TL_DATE, zorder=2)
            side *= -1
        if data.get("note"):
            ax.text(arrow_tip - 0.3, tl_mid - 1.15, data["note"].replace(" · ", "\n"),
                    ha="right", va="top", fontsize=3.7, style="italic",
                    color=TL_DATE, linespacing=1.25, zorder=2)

    # -------------------------------------------------- testament sections (render)
    def render_section(title, bar_color, sections, y_top, layout):
        ncols, nrows = layout["ncols"], layout["nrows"]
        cell_w, cell_h = layout["cell_w"], layout["cell_h"]
        inner_w, nfs, name_lh, sfs = layout["inner_w"], layout["nfs"], layout["name_lh"], layout["sfs"]
        name_lines_for = layout["name_lines_for"]

        ax.add_patch(FancyBboxPatch((M, y_top - SEC_HDR_H), 100 - 2 * M, SEC_HDR_H,
                                     boxstyle="round,pad=0,rounding_size=0.5", facecolor=bar_color,
                                     edgecolor="none", zorder=1))
        ax.text(M + 1.2, y_top - SEC_HDR_H / 2, title, ha="left", va="center",
                fontsize=10.5, fontweight="bold", color="white", family="serif", zorder=2)
        # legend chips, right-aligned
        lx = 100 - M - 1.2
        for sec in reversed(sections):
            name, color = sec["name"], sec["color"]
            tw, _ = measure(name, 6.0, "bold")
            sw = 1.1
            lx -= tw
            ax.text(lx, y_top - SEC_HDR_H / 2, name, ha="left", va="center",
                    fontsize=6.0, fontweight="bold", color="white", zorder=2)
            lx -= (sw + 0.45)
            ax.add_patch(FancyBboxPatch((lx, y_top - SEC_HDR_H / 2 - 0.55), sw, 1.1,
                                         boxstyle="round,pad=0,rounding_size=0.25",
                                         facecolor=tint(color, 0.55), edgecolor="white",
                                         linewidth=0.8, zorder=2))
            lx -= 1.6

        grid_top = y_top - SEC_HDR_H - 0.5

        overflow = []
        _, sum_lh = measure("Ag", sfs)
        for i, (gname, color, book, summ) in enumerate(layout["items"]):
            r, c = divmod(i, ncols)
            x = M + c * (cell_w + GAP_X)
            y = grid_top - r * (cell_h + GAP_Y)
            ax.add_patch(FancyBboxPatch((x, y - cell_h), cell_w, cell_h,
                                         boxstyle="round,pad=0,rounding_size=0.4",
                                         facecolor=tint(color, 0.87), edgecolor=color,
                                         linewidth=1.1, zorder=1))
            strip_y = y - STRIP_TOP_GAP
            ax.add_patch(Rectangle((x + 0.12, strip_y - STRIP_H), cell_w - 0.24, STRIP_H * 0.75,
                                    facecolor=color, edgecolor="none", zorder=2))
            name_y = strip_y - STRIP_H - NAME_TOP_GAP
            name_lines = name_lines_for(book)
            name_block_h = len(name_lines) * name_lh * 1.08
            ax.text(x + CARD_PAD, name_y, "\n".join(name_lines), ha="left", va="top",
                    fontsize=nfs, fontweight="bold", color=shade(color, 0.25),
                    linespacing=1.08, zorder=3)
            slines = wrap_to_width(summ, sfs, inner_w)
            ax.text(x + CARD_PAD, name_y - name_block_h - NAME_SUM_GAP, "\n".join(slines),
                    ha="left", va="top", fontsize=sfs, color=INK, linespacing=1.24, zorder=3)
            fixed_h = STRIP_TOP_GAP + STRIP_H + NAME_TOP_GAP + name_block_h + NAME_SUM_GAP + BOTTOM_PAD
            if len(slines) * sum_lh * 1.24 > cell_h - fixed_h:
                overflow.append(book)

        status = "OK" if not overflow else f"OVERFLOW in: {overflow}"
        print(f"[{title}] {len(layout['items'])} books, {ncols}x{nrows} grid, "
              f"name_fs={nfs:.2f}, summary_fs={sfs:.2f}  -> {status}", file=sys.stderr)
        if overflow:
            print(f"  Tip: shorten the summary text for the book(s) above, or reduce the "
                  f"number of books/rows for this testament.", file=sys.stderr)

    y_top = top_of_sections
    for key in testament_keys:
        t = data["testaments"][key]
        layout = layouts[key]
        render_section(t["title"], t["bar_color"], t["sections"], y_top, layout)
        y_top = (y_top - layout["band_h"]) - TEST_GAP

    fig.savefig(args.output, facecolor=BG)
    print(f"\nSaved: {args.output}  ({fig_w}x{fig_h} in)", file=sys.stderr)


if __name__ == "__main__":
    main()
