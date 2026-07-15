Objective: Colour only the achieved portion of the gauge across band colours; leave the remainder as grey track, matching the reference image.

Action 1:

    FILE: export.py

    SEARCH: # Band strokes (thin overlays) — 0–40–60–80–100
bands = [
    (0, 40, GAUGE_PALETTE["High Risk"]),
    (40, 60, GAUGE_PALETTE["Needs Attention"]),
    (60, 80, GAUGE_PALETTE["Moderate"]),
    (80, 100, GAUGE_PALETTE["Strong"]),
]
for lo, hi, col in bands:
    a1, a2 = to_angle(lo) + 0.6, to_angle(hi) - 0.6  # slight gap at joins
    arc = Arc((0, 0), 2*R, 2*R, angle=0, theta1=a2, theta2=a1, linewidth=int(LW * 0.55), color=col, alpha=0.95)
    ax.add_patch(arc)

    REPLACE: # Band strokes up to achieved percent — 0–40–60–80–100
bands = [
    (0, 40, GAUGE_PALETTE["High Risk"]),
    (40, 60, GAUGE_PALETTE["Needs Attention"]),
    (60, 80, GAUGE_PALETTE["Moderate"]),
    (80, 100, GAUGE_PALETTE["Strong"]),
]
for lo, hi, col in bands:
    seg_lo = lo
    seg_hi = min(hi, pct)
    if seg_hi <= seg_lo:
        continue
    a1, a2 = to_angle(seg_lo) + 0.6, to_angle(seg_hi) - 0.6  # slight gap at joins
    arc = Arc((0, 0), 2*R, 2*R, angle=0, theta1=a2, theta2=a1, linewidth=int(LW * 0.75), color=col)
    arc.set_path_effects([pe.Stroke(linewidth=int(LW * 0.90), foreground='white', alpha=0.12), pe.Normal()])
    ax.add_patch(arc)

    VERIFICATION: /usr/bin/python3 -c "from export import render_maturity_gauge_png; import os; p=render_maturity_gauge_png(72,'Moderate'); print(os.path.exists(p))"

Action 2:

    FILE: export.py

    SEARCH: # Progress arc (category colour)
if pct > 0:
    a1, a2 = to_angle(0), to_angle(pct)
    prog = Arc((0, 0), 2*R, 2*R, angle=0, theta1=a2, theta2=a1, linewidth=int(LW * 0.75), color=cat_colour)
    # Soft outer stroke for a cleaner, less blocky edge
    prog.set_path_effects([pe.Stroke(linewidth=int(LW * 0.90), foreground='white', alpha=0.15), pe.Normal()])
    ax.add_patch(prog)

    REPLACE: # Progress arc removed — band colouring above fills only up to achieved percent
    
    VERIFICATION: /usr/bin/python3 -c "from export import render_maturity_gauge_png; import os; p=render_maturity_gauge_png(35,'High Risk'); print(os.path.exists(p))"
