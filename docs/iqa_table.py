import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

metrics = [
    ("MUSIQ",    "68.56",   "70 – 100",    False),
    ("TOPIQ",    "0.4947",  "0.65 – 1.0",  False),
    ("HyperIQA", "0.5012",  "0.65 – 1.0",  False),
    ("DBCNN",    "0.4951",  "0.65 – 1.0",  False),
    ("PAQ2PIQ",  "74.70",   "60 – 100",    True),
    ("BRISQUE",  "29.50",   "0 – 30 ↓",    True),
    ("NIQE",     "5.4392",  "0 – 5 ↓",     False),
]

fig, ax = plt.subplots(figsize=(9, 5.6))
fig.patch.set_facecolor("#0f1923")
ax.set_facecolor("#0f1923")
ax.axis("off")

ax.text(0.5, 0.965, "IQA Metrik Analiz Sonuçları",
        transform=ax.transAxes, fontsize=15, fontweight="bold",
        color="white", ha="center", va="top")

cols = ["Metrik", "Skor", "İyi Aralık", "Durum"]
col_x = [0.12, 0.38, 0.63, 0.85]
header_y = 0.875

header_rect = FancyBboxPatch((0.02, header_y - 0.032), 0.96, 0.068,
                              transform=ax.transAxes,
                              boxstyle="round,pad=0.008",
                              facecolor="#1e3a5f", edgecolor="none")
ax.add_patch(header_rect)

for col, x in zip(cols, col_x):
    ax.text(x, header_y + 0.002, col,
            transform=ax.transAxes, fontsize=10.5, fontweight="bold",
            color="#7ec8e3", ha="center", va="center")

row_colors = ["#141e2b", "#1a2535"]
row_h = 0.092

for r, (name, score_str, rng, passed) in enumerate(metrics):
    y = header_y - row_h * (r + 1) - 0.01

    rect = FancyBboxPatch((0.02, y - 0.032), 0.96, 0.066,
                           transform=ax.transAxes,
                           boxstyle="round,pad=0.005",
                           facecolor=row_colors[r % 2], edgecolor="none")
    ax.add_patch(rect)

    ax.text(col_x[0], y, name,
            transform=ax.transAxes, fontsize=10, fontweight="bold",
            color="white", ha="center", va="center")
    ax.text(col_x[1], y, score_str,
            transform=ax.transAxes, fontsize=10,
            color="#f0f0f0", ha="center", va="center", fontfamily="monospace")
    ax.text(col_x[2], y, rng,
            transform=ax.transAxes, fontsize=9.5,
            color="#aaaaaa", ha="center", va="center")

    sc = "#2ecc71" if passed else "#e74c3c"
    st = "✓  Geçti" if passed else "✗  Düşük"
    badge = FancyBboxPatch((col_x[3] - 0.09, y - 0.024), 0.18, 0.048,
                            transform=ax.transAxes,
                            boxstyle="round,pad=0.008",
                            facecolor=sc + "33", edgecolor=sc, linewidth=1)
    ax.add_patch(badge)
    ax.text(col_x[3], y, st,
            transform=ax.transAxes, fontsize=9.5, fontweight="bold",
            color=sc, ha="center", va="center")

ax.text(0.5, 0.022,
        "↓ = düşük değer daha iyidir   |   Test görseli: Wikipedia / Camponotus karıncası (Canon EOS 400D)",
        transform=ax.transAxes, fontsize=7.5,
        color="#555555", ha="center", va="bottom")

plt.tight_layout(pad=0.3)
plt.savefig("/Users/reyn/iqa_table.png", dpi=200, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Kaydedildi: /Users/reyn/iqa_table.png")
