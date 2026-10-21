import sys, glob, os
from kiutils.schematic import Schematic
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
D, name, out = sys.argv[1:4]
sch = Schematic.from_file(f"{D}/{name}.kicad_sch")
fig, ax = plt.subplots(figsize=(21, 14.8))
libs = {s.entryName: s for s in sch.libSymbols}
for s in sch.schematicSymbols:
    ls = libs[s.libId.split(":")[-1]]
    for u in ls.units:
        for g in u.graphicItems:
            if type(g).__name__ == "SyRect":
                x0, y0, x1, y1 = s.position.X + g.start.X, s.position.Y - g.start.Y, s.position.X + g.end.X, s.position.Y - g.end.Y
                ax.add_patch(Rectangle((min(x0, x1), min(y0, y1)), abs(x1 - x0), abs(y1 - y0), fill=False, ec="navy", lw=0.8))
        for p in u.pins:
            x, y = s.position.X + p.position.X, s.position.Y - p.position.Y
            ax.plot(x, y, "r.", ms=2)
            if ls.entryName and len(ls.units) and p.name not in ("1", "2"):
                dx = 1 if p.position.X < 0 else -1
                ax.text(x + dx * 3, y, p.name, fontsize=3.2, ha="left" if dx > 0 else "right", va="center", color="green")
    ref = [q.value for q in s.properties if q.key == "Reference"][0]
    val = [q.value for q in s.properties if q.key == "Value"][0]
    ax.text(s.position.X, s.position.Y - 1, ref, fontsize=4, ha="center", color="black")
    ax.text(s.position.X, s.position.Y + 8, val, fontsize=3.6, ha="center", va="top", color="purple")
for w in sch.graphicalItems:
    if w.type == "wire":
        ax.plot([w.points[0].X, w.points[1].X], [w.points[0].Y, w.points[1].Y], "b-", lw=0.5)
for l in sch.globalLabels:
    ax.text(l.position.X, l.position.Y, l.text, fontsize=3.4, ha="right" if l.position.angle == 180 else "left", va="center", color="darkorange")
for t in sch.texts:
    ax.text(t.position.X, t.position.Y, t.text, fontsize=3.8, va="top", ha="left", color="gray")
ax.set_xlim(0, 420); ax.set_ylim(297, 0); ax.set_aspect("equal"); ax.axis("off")
plt.savefig(out, dpi=110, bbox_inches="tight")
