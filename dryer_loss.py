# -*- coding: utf-8 -*-
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

data_dir = "data/TrocknerVerluste"

files = [
    ("2025-12-04_130743_SMPS.csv", "Ref", 0.3),
    ("2025-12-04_132534_SMPS.csv", "Ref", 0.8),
    ("2025-12-04_133105_SMPS.csv", "Ref", 1.3),
    ("2025-12-04_133645_SMPS.csv", "Ref", 2.3),
    ("2025-12-04_134508_SMPS.csv", "2T",  2.3),
    ("2025-12-04_135319_SMPS.csv", "2T",  1.3),
    ("2025-12-04_135851_SMPS.csv", "2T",  0.8),
    ("2025-12-04_140426_SMPS.csv", "2T",  0.3),
]

def load_csv(fname):
    with open(os.path.join(data_dir, fname), encoding='utf-8-sig') as f:
        for i, line in enumerate(f):
            if line.startswith("Scan Number"):
                skip = i
                break
    df = pd.read_csv(os.path.join(data_dir, fname), skiprows=skip)
    cols = sorted([c for c in df.columns if c.replace('.', '', 1).isdigit()], key=float)
    diam = np.array([float(c) for c in cols]) / 1000
    mean_vals = df[cols].astype(float).mean(axis=0).values
    return diam, mean_vals

data = {f"{typ}_{flow:.1f}": {} for _, typ, flow in files}
for f, typ, flow in files:
    data[f"{typ}_{flow:.1f}"]["diam"], data[f"{typ}_{flow:.1f}"]["conc"] = load_csv(f)

# === Geparte Verteilungen ===
plt.figure(figsize=(10, 6))
colors = ["red", "orange", "green", "blue"]
flows = [0.3, 0.8, 1.3, 2.3]

for i, flow in enumerate(flows):
    d = data[f"Ref_{flow:.1f}"]["diam"]
    plt.plot(d, data[f"Ref_{flow:.1f}"]["conc"], color=colors[i], lw=2.8, label=f"1 Trockner – {flow:.1f} l/min")
    plt.plot(d, data[f"2T_{flow:.1f}"]["conc"], '--', color=colors[i], lw=2.8, label=f"2 Trockner – {flow:.1f} l/min")

plt.xscale('log')
plt.xlabel('Partikeldurchmesser (µm)')
plt.ylabel('dN/dlogDp (#/cm³)')
plt.title('SMPS-Grössenverteilungen – perfekt gepaart je Durchfluss')
plt.grid(True, which="both", ls="--", alpha=0.6)
plt.legend(fontsize=10, ncol=2)
plt.tight_layout()

# === Verlust-Plot ===
plt.figure(figsize=(9, 6))
markers = ['o','s','^','D']

for i, flow in enumerate(flows):
    d = data[f"Ref_{flow:.1f}"]["diam"]
    ref = data[f"Ref_{flow:.1f}"]["conc"]
    kas = data[f"2T_{flow:.1f}"]["conc"]
    loss = 100 * (1 - np.where(ref > 10, kas / ref, np.nan))
    plt.plot(d, loss, color=colors[i], marker=markers[i], markevery=10, lw=3, ms=7, label=f'{flow:.1f} l/min')

plt.xscale('log')
plt.xlim(0.015, 0.8)
plt.ylim(0, 100)
plt.xlabel('Partikeldurchmesser (µm)', fontsize=13)
plt.ylabel('Verlust im 2. Trockner (%)', fontsize=13)
plt.title('Trocknerverluste des zweiten Trockners\n(kleiner + langsamer = viel mehr Verlust)', fontsize=14)
plt.grid(True, which="both", ls="--", alpha=0.7)
plt.legend(title="Durchfluss", fontsize=12, title_fontsize=13)
plt.tight_layout()
plt.show()
