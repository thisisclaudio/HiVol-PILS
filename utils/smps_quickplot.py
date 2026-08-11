import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


def read_smps_raw_csv(file_path):
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    header = None
    for i, line in enumerate(lines):
        if line.strip().startswith('Scan Number'):
            header = i
            break

    if header is None:
        raise ValueError("Header nicht gefunden")

    df = pd.read_csv(file_path, skiprows=header)

    raw_cols = [c for c in df.columns if c.startswith('_') and c[1:].replace('.', '', 1).isdigit()]
    diam_nm = np.array([float(c[1:]) for c in raw_cols])
    concentrations = df[raw_cols].astype(float)

    return diam_nm, concentrations


def calc_stats(d_um, n):
    mask = n > 0
    d = d_um[mask]
    n = n[mask]

    # Mode
    mode = d[np.argmax(n)]

    # GeoMean
    geomean = np.exp(np.sum(n * np.log(d)) / np.sum(n))

    # MMOD (volumen-gewichtet)
    weights = n * d**3
    mmod = np.sum(d * weights) / np.sum(weights)

    return mode, geomean, mmod


if __name__ == "__main__":

    file_path = "data/2025-12-16_085457_SMPS_PARI_AMS_0_01_VK_Modul.csv"

    diam_nm, conc_df = read_smps_raw_csv(file_path)
    diam_um = diam_nm / 1000.0

    plt.figure(figsize=(10, 6))

    first_stats = None

    for i, (_, row) in enumerate(conc_df.iterrows()):
        n = row.values
        plt.plot(diam_um, n, alpha=0.6, label=f"Scan {i+1}" if i < 10 else None)

        if i == 0:
            first_stats = calc_stats(diam_um, n)

    mode, geomean, mmod = first_stats

    text = (
        f"Mode: {mode:.3f} µm\n"
        f"GeoMean: {geomean:.3f} µm\n"
        f"MMOD: {mmod:.3f} µm"
    )

    plt.text(
        0.02, 0.98, text,
        transform=plt.gca().transAxes,
        verticalalignment="top",
        bbox=dict(facecolor="white", alpha=0.8)
    )

    plt.xscale("log")
    plt.xlabel("Diameter (µm)")
    plt.ylabel("dN/dlogDp (#/cm³)")
    plt.title("SMPS Rohdaten – alle Scans")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)

    if len(conc_df) <= 10:
        plt.legend()

    plt.show()
