# HiVol-PILS

# Aerosol / SMPS Analysis Tools

Dieses Repository enthält eine Sammlung kleiner, zielgerichteter Python-Skripte zur Auswertung von SMPS-Messdaten sowie zur physikalischen Abschätzung von Aerosol- und Tröpfchenprozessen.  
Der Fokus liegt auf **Nachvollziehbarkeit**, **minimalem Overhead** und **physikalisch sauberen Modellen**, nicht auf Frameworks oder automatisierter Pipelines.

---

## Inhalte

### 1. `plot_smps_raw.py`
Plottet **unveränderte SMPS-Rohdaten**.

- Liest CSV-Dateien im TSI-SMPS-Format
- Nutzt ausschließlich die Rohdaten-Bins (`_xx`)
- Überlagert alle Scans in einem Plot
- Berechnet und zeigt:
  - **Mode**
  - **GeoMean**
  - **MMOD (volumen-/massenbasiert)**

**Einsatz:**  
Schnelle visuelle Kontrolle der Messung ohne Modellannahmen.

---

### 2. `smps_salt_to_droplet.py`
Rückrechnung von **Salzresiduen auf ursprüngliche Tröpfchengrößen**  
(fest parametriert für **0.01 % (m/m) Ammoniumsulfat**).

- Rechnet nur die **x-Achse** um (Durchmesser)
- Konzentrationen bleiben unverändert
- Optionales Overlay:
  - Salzresiduum
  - Rückgerechnete Tröpfchen
- Kennwerte im Plot:
  - Mode
  - GeoMean
  - MMOD

**Annahmen:**
- vollständiges Salzresiduum
- kugelförmige Partikel
- homogene Lösung
- konstante Dichten

**Einsatz:**  
Vergleich SMPS-Messung ↔ reale Tröpfchengrößen.

---

### 3. `coagulation_chamber_sizing.py`
Physikalisches Abschätzungsmodell für **brownsche Koagulation** in einer Aerosol-/Tröpfchenkammer.

- Brownscher Koagulationskernel nach Seinfeld & Pandis
- Slip-korrigierte Diffusion (Cunningham)
- Berechnet für gegebene:
  - Tröpfchengröße
  - Flüssigkeitsdurchsatz
  - Aerosolfluss
- Liefert:
  - Koagulationskoeffizient **K₁₂**
  - Zeitkonstante **τ**
  - notwendiges **Kammervolumen**
  - Tröpfchenkonzentration

**Einsatz:**  
Auslegung und Größenordnungsschätzung von Koagulations- oder Kontaktkammern.

---

## Abhängigkeiten

- Python ≥ 3.9
- `numpy`
- `matplotlib`
- `pandas` (nur für SMPS-CSV-Import)

Keine weiteren Frameworks oder externen Tools.

---