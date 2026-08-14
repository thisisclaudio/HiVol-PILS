"""
Dieses Skript berechnet die Kalibrierkurve des Alphasense OPC-N2 vom PSL-Aequivalenzdurchmesser auf den realen Wassertropfendurchmesser

Referenzen
----------
- Wellenlaenge 658 nm, RI-Annahme 1.5+i0: Alphasense OPC-N2 User Manual
- Akzeptanzwinkel 32-88 deg: Sousan et al. (2016), Aerosol Sci. Technol.
- n_PSL ~ 1.5, n_Wasser ~ 1.331 bei sichtbarem Licht (Standardwerte)
- Methodischer Vergleich (fast identischer Ansatz fuer OPC-N3):
  Nurowska et al. (2023), Atmos. Meas. Tech., 16, 2415-2430,
  https://doi.org/10.5194/amt-16-2415-2023 (Appendix A1)

Benoetigt: numpy, matplotlib, PyMieScatt
"""

import numpy as np
if not hasattr(np, "trapz"):
    np.trapz = np.trapezoid
import matplotlib.pyplot as plt
import scipy.integrate
if not hasattr(scipy.integrate, "trapz"):
    scipy.integrate.trapz = scipy.integrate.trapezoid
import PyMieScatt as ps
import csv

# ---------------------------------------------------------------------
# Parameter (hier anpassen falls noetig)
# ---------------------------------------------------------------------
WAVELENGTH_NM = 658.0            # OPC-N2 Laserwellenlaenge
THETA_MIN_DEG = 32.0             # Akzeptanzwinkel-Fenster der Optik
THETA_MAX_DEG = 88.0             # (Sousan et al. 2016)

N_PSL = 1.5 + 0j              #92 # Brechungsindex PSL-Kalibrierpartikel
N_WATER = 1.331 + 0j             # Brechungsindex Wasser

D_MIN_NM = 150.0                 # unterer Rand Durchmesserraster (Berechnung)
D_MAX_NM = 14000.0                # oberer Rand Durchmesserraster (Berechnung) -
                                                                                              # bereichs nicht durch fehlende Stuetzstellen verzerrt
                                  # wird (Randeffekt)
N_POINTS = 900                   # Anzahl Stuetzstellen (fein, wegen Glaettung danach)
SMOOTH_WINDOW = 25               # Glaettungsfenster (gleitender Mittelwert) fuer die
                                  # Signalkurven, um Mie-Oszillationen (Ripple-Struktur)
                                  # zu unterdruecken -> siehe Nurowska et al. (2023),
                                  # die dasselbe fuer den OPC-N3 machen (dort: 100 Punkte
                                  # bei 6000 Stuetzstellen, hier proportional angepasst)

D_ACTIVATION_RANGE_UM = (2.5, 10.0)   # relevanter Bereich fuer Mittelwert
D_PLOT_MAX_UM = 5.0                  # oberer Rand fuer die Plots (Interessensbereich)

# ---------------------------------------------------------------------
# Kernfunktionen
# ---------------------------------------------------------------------
def collected_signal(n: complex, d_nm: float) -> float:
    """
    Integriertes Streusignal im Akzeptanzwinkel-Fenster [theta_min, theta_max]
    fuer einen Partikel mit Brechungsindex n und Durchmesser d_nm.
    """
    theta, SL, SR, SU = ps.ScatteringFunction(
        n, WAVELENGTH_NM, d_nm,
        minAngle=THETA_MIN_DEG, maxAngle=THETA_MAX_DEG,
        angularResolution=0.5,
    )
    integrand = SU * np.sin(theta)
    return np.trapz(integrand, theta)

def build_signal_curve(n: complex, d_grid_nm: np.ndarray) -> np.ndarray:
    """Signalkurve ueber ein ganzes Durchmesserraster."""
    return np.array([collected_signal(n, d) for d in d_grid_nm])

def smooth_curve(signal: np.ndarray, window: int) -> np.ndarray:
    """
    Glaettet eine Signalkurve mit einem gleitenden Mittelwert, um die
    Mie-Oszillationen (Ripple-Struktur) zu unterdruecken. Ohne Glaettung
    ist die Kurve nicht monoton, was die Inversion (Signal -> Durchmesser)
    unstabil macht (siehe auch Nurowska et al. 2023, die dasselbe fuer den
    OPC-N3 tun).
    """
    if window <= 1:
        return signal
    kernel = np.ones(window) / window
    # 'same' Modus + Randbehandlung durch Reflektion, damit die Kurve an
    # den Raendern nicht verzerrt wird
    padded = np.pad(signal, (window // 2, window // 2), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")
    return smoothed[: len(signal)]

def invert_calibration(signal_calib: np.ndarray, d_grid_nm: np.ndarray,
                        signal_query: np.ndarray) -> np.ndarray:
    """
    Kehrt eine Kalibrierkurve (Signal -> Durchmesser) um und wertet sie
    an den gegebenen Signalwerten aus (lineare Interpolation).
    Signal muss dazu monoton sein -> wird vorher sortiert.
    """
    order = np.argsort(signal_calib)
    return np.interp(signal_query, signal_calib[order], d_grid_nm[order])

def eval_curve(d_grid_nm: np.ndarray, signal_grid: np.ndarray,
               d_query_nm: np.ndarray) -> np.ndarray:
    """Wertet eine Signalkurve (Durchmesser -> Signal) an d_query aus."""
    return np.interp(d_query_nm, d_grid_nm, signal_grid)

# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
def correct_measured_diameter(d_measured_psl_nm, d_grid_nm,
                               signal_psl, signal_water):
    """
    Rechnet einen vom OPC-N2 AUSGEGEBENEN PSL-Aequivalenzdurchmesser
    zurueck auf den echten Wassertropfendurchmesser.

    Weg: d_gemessen (auf PSL-Kurve) -> Signal -> d_real (auf Wasser-Kurve)

    Parameter
    ---------
    d_measured_psl_nm : float oder array
        Vom Geraet ausgegebener (PSL-Aequivalenz-)Durchmesser [nm].
    d_grid_nm, signal_psl, signal_water : wie von build_signal_curve()

    Returns
    -------
    d_real_nm : float oder array
        Rekonstruierter, echter Wassertropfendurchmesser [nm].
    """
    # Schritt 1: welches Signal erzeugt dieser PSL-Aequivalenzdurchmesser?
    signal_at_measured = eval_curve(d_grid_nm, signal_psl, d_measured_psl_nm)
    # Schritt 2: bei welchem Wasser-Durchmesser wuerde genau dieses Signal
    # entstehen? -> das ist der echte Tropfendurchmesser.
    d_real_nm = invert_calibration(signal_water, d_grid_nm, signal_at_measured)
    return d_real_nm

# ---------------------------------------------------------------------
# Hauptrechnung
# ---------------------------------------------------------------------
def main():
    d_grid_nm = np.linspace(D_MIN_NM, D_MAX_NM, N_POINTS)

    print("Berechne PSL-Kalibrierkurve ...")
    signal_psl_raw = build_signal_curve(N_PSL, d_grid_nm)
    signal_psl = smooth_curve(signal_psl_raw, SMOOTH_WINDOW)

    print("Berechne Wasser-Signalkurve ...")
    signal_water_raw = build_signal_curve(N_WATER, d_grid_nm)
    signal_water = smooth_curve(signal_water_raw, SMOOTH_WINDOW)

    print("Invertiere Kalibrierkurve fuer Wassertropfen (Bias-Richtung) ...")
    d_measured_nm = invert_calibration(signal_psl, d_grid_nm, signal_water)
    bias_percent = (d_measured_nm - d_grid_nm) / d_grid_nm * 100.0

    mask = ((d_grid_nm / 1000 >= D_ACTIVATION_RANGE_UM[0]) &
            (d_grid_nm / 1000 <= D_ACTIVATION_RANGE_UM[1]))
    mean_bias_relevant = np.nanmean(bias_percent[mask])
    mean_bias_total = np.nanmean(bias_percent)

    print(f"\n{'d_real [um]':>12} {'d_gemessen [um]':>18} {'Bias [%]':>10}")
    for target_um in [0.3, 0.5, 1, 2, 3, 4, 5]:
        idx = int(np.abs(d_grid_nm / 1000 - target_um).argmin())
        print(f"{d_grid_nm[idx]/1000:12.2f} "
              f"{d_measured_nm[idx]/1000:18.2f} "
              f"{bias_percent[idx]:10.1f}")

    print(f"\nMittlerer Bias {D_ACTIVATION_RANGE_UM[0]}-"
          f"{D_ACTIVATION_RANGE_UM[1]} um (Aktivierungsbereich): "
          f"{mean_bias_relevant:.1f} %")
    print(f"Mittlerer Bias gesamter Bereich "
          f"{D_MIN_NM/1000:.2f}-{D_MAX_NM/1000:.1f} um: "
          f"{mean_bias_total:.1f} %")

    # ---- Teil B: Korrekturfunktion (gemessen -> real)----
    print("\nWende Korrekturfunktion an (gemessen -> real) ...")
    d_gemessen_grid_nm = d_grid_nm  # wir werten auf demselben Raster aus
    d_real_korrigiert_nm = correct_measured_diameter(
        d_gemessen_grid_nm, d_grid_nm, signal_psl, signal_water)
    korrektur_faktor = d_real_korrigiert_nm / d_gemessen_grid_nm

    print(f"\n{'d_gemessen [um]':>16} {'d_real (korr.) [um]':>20} {'Faktor':>8}")
    for target_um in [0.3, 0.5, 1, 2, 3, 4, 5]:
        idx = int(np.abs(d_gemessen_grid_nm / 1000 - target_um).argmin())
        print(f"{d_gemessen_grid_nm[idx]/1000:16.2f} "
              f"{d_real_korrigiert_nm[idx]/1000:20.2f} "
              f"{korrektur_faktor[idx]:8.3f}")

    mask_g = ((d_gemessen_grid_nm / 1000 >= D_ACTIVATION_RANGE_UM[0]) &
              (d_gemessen_grid_nm / 1000 <= D_ACTIVATION_RANGE_UM[1]))
    mean_factor_relevant = np.nanmean(korrektur_faktor[mask_g])
    print(f"\nMittlerer Korrekturfaktor {D_ACTIVATION_RANGE_UM[0]}-"
          f"{D_ACTIVATION_RANGE_UM[1]} um: {mean_factor_relevant:.3f}")

    # ---- Plot 1: Kalibrierkurven (Signal vs. Durchmesser), roh + geglaettet ----
    fig1, ax1 = plt.subplots(figsize=(7, 5))
    ax1.plot(d_grid_nm / 1000, signal_psl_raw, color="tab:blue")
    ax1.plot(d_grid_nm / 1000, signal_water_raw, color="tab:orange")
    #ax1.plot(d_grid_nm / 1000, signal_psl, label="PSL (n=1.5), geglaettet", color="tab:blue")
    #ax1.plot(d_grid_nm / 1000, signal_water, label="Wasser (n=1.331), geglaettet", color="tab:orange")
    ax1.set_xlabel("Physikalischer Durchmesser [µm]")
    ax1.set_ylabel("Integriertes Streusignal [-]")
    ax1.set_title("OPC-N2: Streusignal im Akzeptanzwinkel (32°-88°)")
    ax1.legend()
    ax1.grid(alpha=0.3)
    ax1.set_ylim(0,200)
    ax1.set_xlim(0, D_PLOT_MAX_UM)
    fig1.tight_layout()

    # ---- Plot 2: Bias-Kurve (real -> gemessen) ----
    fig2, ax2 = plt.subplots(figsize=(7, 5))
    ax2.plot(d_grid_nm / 1000, bias_percent, color="tab:red")
    ax2.axhline(mean_bias_relevant, color="grey", linestyle="--",
                label=f"Mittel {D_ACTIVATION_RANGE_UM[0]}-{D_ACTIVATION_RANGE_UM[1]} µm: "
                      f"{mean_bias_relevant:.1f} %")
    ax2.axvspan(*D_ACTIVATION_RANGE_UM, color="grey", alpha=0.15)
    ax2.set_xlabel("Realer Tropfendurchmesser [µm]")
    ax2.set_ylabel("Bias [%]  (negativ = Unterschaetzung)")
    ax2.set_title("Groessen-Bias: OPC-N2 (PSL-kalibriert) misst Wassertropfen")
    ax2.legend()
    ax2.grid(alpha=0.3)
    ax2.set_xlim(0, D_PLOT_MAX_UM)
    fig2.tight_layout()

    # ---- Plot 3: Korrekturfunktion (gemessen -> real) ----
    fig3, ax3 = plt.subplots(figsize=(7, 5))
    ax3.plot(d_gemessen_grid_nm / 1000, d_real_korrigiert_nm / 1000,
              color="tab:green", label="Korrigierter Durchmesser")
    ax3.plot(d_gemessen_grid_nm / 1000, d_gemessen_grid_nm / 1000,
              color="grey", linestyle=":", label="1:1 (keine Korrektur)")
    #ax3.axvspan(*D_ACTIVATION_RANGE_UM, color="grey", alpha=0.15)
    ax3.set_xlabel("Vom OPC-N2 klassifizierter (PSL-Aequiv.) Durchmesser [µm]")
    ax3.set_ylabel("Wassertropfendurchmesser [µm]")
    ax3.set_title("Korrekturfunktion")
    ax3.legend()
    ax3.grid(alpha=0.3)
    ax3.set_xlim(0, 10)
    ax3.set_ylim(0, 10)
    fig3.tight_layout()

    # ---- Plot 4: Korrekturfaktor vs. gemessener Durchmesser ----
    fig4, ax4 = plt.subplots(figsize=(7, 5))
    ax4.plot(d_gemessen_grid_nm / 1000, korrektur_faktor, color="tab:purple")
    ax4.axhline(mean_factor_relevant, color="grey", linestyle="--",
                label=f"Mittel {D_ACTIVATION_RANGE_UM[0]}-{D_ACTIVATION_RANGE_UM[1]} µm: "
                      f"{mean_factor_relevant:.2f}")
    ax4.set_xlabel("Vom OPC-N2 ausgegebener (PSL-Aequiv.) Durchmesser [µm]")
    ax4.set_ylabel("Korrekturfaktor  (d_real / d_gemessen)")
    ax4.set_title("Korrekturfaktor als Funktion des gemessenen Durchmessers")
    ax4.legend()
    ax4.grid(alpha=0.3)
    ax4.set_xlim(0, 10)
    fig4.tight_layout()

    plt.show()

    print("\nPlots gespeichert: opcn2_kalibrierkurven.png, opcn2_bias_kurve.png, "
          "opcn2_korrekturfunktion.png, opcn2_korrekturfaktor.png")

if __name__ == "__main__":
    main()