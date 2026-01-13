import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


def read_smps_raw_csv(file_path):
    # finde Header-Zeile
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    data_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith('Scan Number'):
            data_start = i
            break

    if data_start is None:
        raise ValueError("Header nicht gefunden")

    df = pd.read_csv(file_path, skiprows=data_start)

    # Rohdaten-Spalten: _<Durchmesser>
    raw_cols = [c for c in df.columns if c.startswith('_') and c[1:].replace('.', '', 1).isdigit()]
    diameters_nm = np.array([float(c[1:]) for c in raw_cols])
    concentrations = df[raw_cols].astype(float)

    return diameters_nm, concentrations


if __name__ == "__main__":

    file_path = "data/2025-12-16_085457_SMPS_PARI_AMS_0_01_VK_Modul.csv"

    diam_nm, conc_df = read_smps_raw_csv(file_path)

    diam_um = diam_nm / 1000.0

    plt.figure(figsize=(10, 6))

    for i, (_, row) in enumerate(conc_df.iterrows()):
        plt.plot(diam_um, row.values, alpha=0.6, label=f"Scan {i+1}" if i < 10 else None)

    plt.xscale("log")
    plt.xlabel("Diameter (µm)")
    plt.ylabel("dN/dlogDp (#/cm³)")
    plt.title("SMPS Rohdaten – alle Scans")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)

    if len(conc_df) <= 10:
        plt.legend()

    plt.show()
