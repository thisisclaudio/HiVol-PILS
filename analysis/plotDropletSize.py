#!/usr/bin/env python3

"""
Dieses Skript plottet die Tröpfchengrössenverteilungen
"""

from pathlib import Path
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================================
# Einstellungen
# ============================================================================

DATA_DIR = Path("data")

# OPC-N2 Bin-Grenzen [nm]
BIN_EDGES = np.array([
    (380, 540),
    (540, 780),
    (750, 1050),
    (1050, 1340),
    (1340, 1590),
    (1590, 2070),
    (2070, 3000),
    (3000, 4000),
    (4000, 5000),
    (5000, 6500),
    (6500, 8000),
    (8000, 10000),
    (10000, 12000),
    (12000, 14000),
    (14000, 16000),
    (16000, 17000),
], dtype=float)

BIN_COLS = [f"OPC_Bin{i}" for i in range(16)]

# Unkorrigierte geometrische Bin-Mittel
GEO_MEAN = np.sqrt(
    BIN_EDGES[:, 0] * BIN_EDGES[:, 1]
)

# Unkorrigierte logarithmische Bin-Breiten
LOG_WIDTH = np.log10(
    BIN_EDGES[:, 1] / BIN_EDGES[:, 0]
)


# ============================================================================
# Grössenkorrektur
# ============================================================================

CORRECTION_THRESHOLD = 2500.0  # nm
CORRECTION_FACTOR = 1.17


def corrected_bin_geometry():
    """
    Berechnet die korrigierten Bin-Grenzen und daraus
    die korrigierten geometrischen Bin-Mittel sowie
    die korrigierten logarithmischen Bin-Breiten.
    """

    lo = BIN_EDGES[:, 0]
    hi = BIN_EDGES[:, 1]

    geo = np.sqrt(lo * hi)

    factors = np.where(
        geo >= CORRECTION_THRESHOLD,
        CORRECTION_FACTOR,
        1.0
    )

    lo_corrected = lo * factors
    hi_corrected = hi * factors

    geo_corrected = np.sqrt(
        lo_corrected * hi_corrected
    )

    log_width_corrected = np.log10(
        hi_corrected / lo_corrected
    )

    return geo_corrected, log_width_corrected


GEO_MEAN_CORRECTED, LOG_WIDTH_CORRECTED = corrected_bin_geometry()


# ============================================================================
# Dateinamen
# ============================================================================

FILENAME_RE = re.compile(
    r"(NaCl|Russ)_(\d+)lpm_(\d+)nm_"
    r"(\d{8})_(\d{6})\.csv$",
    re.IGNORECASE
)


def parse_filename(path):
    match = FILENAME_RE.search(path.name)

    if match is None:
        return None

    material = match.group(1)

    if material.lower() == "russ":
        material = "Russ"
    else:
        material = "NaCl"

    diameter = int(match.group(3))

    return material, diameter


# ============================================================================
# Messdatei einlesen
# ============================================================================

def read_bin_means(path):
    """
    Mittelt OPC_Bin0...OPC_Bin15 über die Zeit.

    Dateien ohne OPC-Bins werden ignoriert.
    """

    try:
        df = pd.read_csv(
            path,
            sep=";",
            decimal="."
        )
    except Exception:
        return None

    missing = [
        col for col in BIN_COLS
        if col not in df.columns
    ]

    # Beispielsweise Baseline-Dateien
    # besitzen keine OPC-Bins.
    if missing:
        return None

    return (
        df[BIN_COLS]
        .mean(axis=0, skipna=True)
        .to_numpy(dtype=float)
    )


# ============================================================================
# Dateien suchen und gruppieren
# ============================================================================

def find_measurements():

    files = list(DATA_DIR.rglob("*.csv"))

    print(f"{len(files)} CSV-Dateien gefunden.")

    groups = {}

    for path in files:

        parsed = parse_filename(path)

        if parsed is None:
            continue

        material, diameter = parsed

        values = read_bin_means(path)

        # Dateien ohne OPC-Daten ignorieren
        if values is None:
            continue

        key = (material, diameter)

        groups.setdefault(key, []).append(values)

    print(
        f"{sum(len(v) for v in groups.values())} "
        f"Messdateien mit OPC-Daten verwendet."
    )

    return groups


# ============================================================================
# Grössenverteilungen
# ============================================================================

def calculate_distributions(groups):

    results = {}

    for (material, diameter), measurements in sorted(groups.items()):

        measurements = np.asarray(measurements)

        # Erst Mittelwert jeder Messung über die Zeit,
        # danach Mittelwert über alle Wiederholmessungen.
        mean_values = np.nanmean(
            measurements,
            axis=0
        )

        # Unkorrigierte Verteilung
        dndlogd = (
            mean_values / LOG_WIDTH
        )

        # Grössenkorrigierte Verteilung
        dndlogd_corrected = (
            mean_values / LOG_WIDTH_CORRECTED
        )

        results[(material, diameter)] = {
            "uncorrected": dndlogd,
            "corrected": dndlogd_corrected,
        }

    return results


# ============================================================================
# Plot
# ============================================================================

def plot_material(results, material, corrected):

    subset = sorted(
        [
            (diameter, result)
            for (mat, diameter), result in results.items()
            if mat == material
        ],
        key=lambda x: x[0]
    )

    if not subset:
        return

    fig, ax = plt.subplots(
        figsize=(7, 5)
    )

    if corrected:
        x = GEO_MEAN_CORRECTED
        title = (
            f"Tröpfchengrössenverteilung – {material} "
            f"(grössenkorrigiert)"
        )
        ylabel = "$dN/d\\log D_p$"
    else:
        x = GEO_MEAN
        title = (
            f"Tröpfchengrössenverteilung – {material} "
            f"(unkorrigiert)"
        )
        ylabel = "$dN/d\\log D_p$"

    for diameter, result in subset:

        if corrected:
            y = result["corrected"]
        else:
            y = result["uncorrected"]

        ax.plot(
            x,
            y,
            marker="o",
            label=f"{diameter} nm"
        )

    ax.set_xscale("log")

    ax.set_xlabel(
        "Tröpfchendurchmesser $D_p$ [nm]"
    )

    ax.set_ylabel(ylabel)

    ax.set_title(title)

    ax.grid(
        True,
        which="both",
        alpha=0.3
    )

    ax.legend(
        title="Kerndurchmesser"
    )

    fig.tight_layout()


# ============================================================================
# Main
# ============================================================================

def main():

    print(f"Lese Messdaten aus: {DATA_DIR}")

    groups = find_measurements()

    if not groups:
        raise RuntimeError(
            "Keine gültigen OPC-Messdateien gefunden."
        )

    results = calculate_distributions(groups)

    # ------------------------------------------------------------
    # 1. NaCl unkorrigiert
    # ------------------------------------------------------------
    plot_material(
        results,
        "NaCl",
        corrected=False
    )

    # ------------------------------------------------------------
    # 2. NaCl korrigiert
    # ------------------------------------------------------------
    plot_material(
        results,
        "NaCl",
        corrected=True
    )

    # ------------------------------------------------------------
    # 3. Russ unkorrigiert
    # ------------------------------------------------------------
    plot_material(
        results,
        "Russ",
        corrected=False
    )

    # ------------------------------------------------------------
    # 4. Russ korrigiert
    # ------------------------------------------------------------
    plot_material(
        results,
        "Russ",
        corrected=True
    )

    # Nur anzeigen, nichts speichern
    plt.show()


if __name__ == "__main__":
    main()