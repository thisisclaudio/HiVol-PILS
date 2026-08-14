"""
Dieses Skript plottet die Aktivierungskurvne aus den Rohdaten
"""

import glob
import os
import re

import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Einstellungen
# ---------------------------------------------------------------------------

ORDNER = r"data"


# ---------------------------------------------------------------------------
# Material bestimmen
# ---------------------------------------------------------------------------

def material_aus_dateiname(dateiname):

    if re.match(r"^Russ_", dateiname, re.IGNORECASE):
        return "Russ"

    if re.match(r"^NaCl_", dateiname, re.IGNORECASE):
        return "NaCl"

    return None


# ---------------------------------------------------------------------------
# CSV-Dateien einlesen
# ---------------------------------------------------------------------------

alle_csv = glob.glob(os.path.join(ORDNER, "*.csv"))

zeilen = []

for pfad in alle_csv:

    dateiname = os.path.basename(pfad)

    material = material_aus_dateiname(dateiname)

    if material is None:
        continue

    df = pd.read_csv(pfad, sep=";")

    # Dateien ohne die benötigten Messdaten überspringen
    if "CPC_conc" not in df.columns or "OPC_conc" not in df.columns:
        continue

    if "Durchmesser_nm" not in df.columns:
        continue

    durchmesser = df["Durchmesser_nm"].iloc[0]

    cpc_mittel = df["CPC_conc"].mean()
    opc_mittel = df["OPC_conc"].mean()

    # Schutz gegen Division durch 0
    if cpc_mittel == 0:
        continue

    verhaeltnis = opc_mittel / cpc_mittel

    zeilen.append({
        "Material": material,
        "Datei": dateiname,
        "Durchmesser_nm": durchmesser,
        "Verhaeltnis": verhaeltnis,
    })


ergebnis_df = pd.DataFrame(zeilen)

if ergebnis_df.empty:
    raise SystemExit(
        f"Keine passenden CSV-Dateien mit CPC_conc und OPC_conc in: {ORDNER}"
    )


# ---------------------------------------------------------------------------
# Statistik pro Material und Durchmesser
# ---------------------------------------------------------------------------

statistik = (
    ergebnis_df
    .groupby(["Material", "Durchmesser_nm"])["Verhaeltnis"]
    .agg(
        mittelwert="mean",
        std="std",
        n="count",
    )
    .reset_index()
    .sort_values(["Material", "Durchmesser_nm"])
)

statistik["std"] = statistik["std"].fillna(0)


# ---------------------------------------------------------------------------
# Figure 1: Russ
# ---------------------------------------------------------------------------

daten = ergebnis_df[ergebnis_df["Material"] == "Russ"]
stats = statistik[statistik["Material"] == "Russ"]

if not daten.empty:

    fig, ax = plt.subplots(figsize=(8, 5))

    # Einzelmessungen
    ax.scatter(
        daten["Durchmesser_nm"],
        daten["Verhaeltnis"],
        color="red",
        alpha=0.3,
        label="Einzelmessungen",
    )

    # Mittelwert ± Standardabweichung
    ax.errorbar(
        stats["Durchmesser_nm"],
        stats["mittelwert"],
        yerr=stats["std"],
        color="red",
        marker="o",
        linewidth=1.5,
        capsize=4,
        label="Mittelwert ± Std.",
    )

    ax.set_xlabel("Kerndurchmesser [nm]")
    ax.set_ylabel("Aktivierungsverhältnis OPC/CPC [-]")
    ax.set_title("Aktivierungskurve – Russpartikel")

    ax.set_ylim(0, 1.5)
    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.tight_layout()


# ---------------------------------------------------------------------------
# Figure 2: NaCl
# ---------------------------------------------------------------------------

daten = ergebnis_df[ergebnis_df["Material"] == "NaCl"]
stats = statistik[statistik["Material"] == "NaCl"]

if not daten.empty:

    fig, ax = plt.subplots(figsize=(8, 5))

    # Einzelmessungen
    ax.scatter(
        daten["Durchmesser_nm"],
        daten["Verhaeltnis"],
        color="blue",
        alpha=0.3,
        label="Einzelmessungen",
    )

    # Mittelwert ± Standardabweichung
    ax.errorbar(
        stats["Durchmesser_nm"],
        stats["mittelwert"],
        yerr=stats["std"],
        color="blue",
        marker="o",
        linewidth=1.5,
        capsize=4,
        label="Mittelwert ± Std.",
    )

    ax.set_xlabel("Kerndurchmesser [nm]")
    ax.set_ylabel("Aktivierungsverhältnis OPC/CPC [-]")
    ax.set_title("Aktivierungskurve – NaCl-Partikel")

    ax.set_ylim(0, 1.5)
    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.tight_layout()


# ---------------------------------------------------------------------------
# Anzeigen
# ---------------------------------------------------------------------------

plt.show()