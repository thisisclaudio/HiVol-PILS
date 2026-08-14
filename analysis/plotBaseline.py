"""
Dieses Skript plottet die Baseline-Messung bei DMA 0V, um den Untergrund zu quantifizieren.
"""

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


BASELINE_DIR = Path("data\\baseline")

CSV_FILES = [
    BASELINE_DIR / "NaCl_0lpm_0nm_20260626_131223.csv",
    BASELINE_DIR / "NaCl_0lpm_0nm_20260626_131412.csv",
]

SKIP_SECONDS = 5.0


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", decimal=".")


def plot_measurement(path: Path) -> None:
    df = load_csv(path)
    df = df[df["Zeit_s"] >= SKIP_SECONDS].reset_index(drop=True)

    cpc_mean = df["CPC_inst"].mean()
    opc_mean = df["OPC_inst"].mean()

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.set_xlabel("Zeit [s]")
    ax.set_ylabel("Konzentration [#/cm³]")

    ax.plot(
        df["Zeit_s"],
        df["CPC_inst"],
        color="tab:blue",
        alpha=0.6,
        linewidth=1.5,
        label=f"CPC (Ø = {cpc_mean:.3f} #/cm³)",
    )

    ax.plot(
        df["Zeit_s"],
        df["OPC_inst"],
        color="tab:red",
        alpha=0.6,
        linewidth=1.5,
        label=f"OPC (Ø = {opc_mean:.3f} #/cm³)",
    )

    ax.set_title("Baseline-Messung: DMA 0V")
    ax.legend(loc="upper right")

    fig.tight_layout()

    print(f"Ø CPC_inst = {cpc_mean:.3f} #/cm³")
    print(f"Ø OPC_inst = {opc_mean:.3f} #/cm³")


def main() -> None:
    for path in CSV_FILES:
        if not path.exists():
            print(f"WARNUNG: Datei nicht gefunden: {path}")
            continue

        plot_measurement(path)

    plt.show()


if __name__ == "__main__":
    main()