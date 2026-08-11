import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# =========================
# Plot-Schalter
# =========================
PLOT_SALT_DATA = True      # Salz + Tröpfchen anzeigen

# =========================
# Konstanten – 0.01 % AMS
# =========================
RHO_AS = 1.77      # g/cm³
RHO_H2O = 0.9982  # g/cm³
C = 1e-4          # 0.01 % m/m

RHO_SOLUTION = 1.0 / (C / RHO_AS + (1.0 - C) / RHO_H2O)
SCALING_FACTOR = (RHO_AS / (C * RHO_SOLUTION)) ** (1.0 / 3.0)


def read_smps_raw_csv(file_path):
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    header = None
    for i, line in enumerate(lines):
        if line.strip().startswith('Scan Number'):
            header = i
            break

    if header is None:
        raise ValueError("SMPS-Header nicht gefunden")

    df = pd.read_csv(file_path, skiprows=header)

    raw_cols = [c for c in df.columns if c.startswith('_') and c[1:].replace('.', '', 1).isdigit()]
    diam_nm = np.array([float(c[1:]) for c in raw_cols])
    concentrations = df[raw_cols].astype(float)

    return diam_nm, concentrations


def calc_stats(d_um, n):
    mask = n > 0
    d = d_um[mask]
    n = n[mask]

    # log-bin width
    dlogD = np.log10(d[1] / d[0])

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

    diam_salt_nm, conc_df = read_smps_raw_csv(file_path)

    diam_salt_um = diam_salt_nm / 1000.0
    diam_drop_um = diam_salt_um * SCALING_FACTOR

    plt.figure(figsize=(10, 6))

    # nur erster Scan für Text (sonst Chaos)
    first_stats = None

    for i, (_, row) in enumerate(conc_df.iterrows()):
        n = row.values

        if PLOT_SALT_DATA:
            plt.plot(
                diam_salt_um,
                n,
                color="gray",
                alpha=0.3,
                linewidth=1,
                label="Salzresiduum" if i == 0 else None
            )

        plt.plot(
            diam_drop_um,
            n,
            alpha=0.7,
            linewidth=2,
            label="Tröpfchen" if i == 0 else None
        )

        if i == 0:
            first_stats = calc_stats(diam_drop_um, n)

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
    plt.xlabel("Durchmesser (µm)")
    plt.ylabel("dN/dlogDp (#/cm³)")
    plt.title("SMPS: Salz → Tröpfchen (0.01% AMS)")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend()

    plt.show()
