# High-Volume Particle-into-Liquid Sampler (Hi-Vol PILS)
Dieses Repository enthält Python-Skripte aus dem P5-Projekt „Entwicklung eines neuartigen High-Volume Particle-into-Liquid Sampler (Hi-Vol PILS)“.
Die Skripte dienen der Auswertung, dem Vergleich und der Visualisierung von Aerosoldaten aus SMPS-Messungen.

## Struktur
- data/ – Rohdaten (SMPS CSV-Dateien)
- smps_quickplot.py – Einlesen und Plotten von Rohdaten
- smps_salt_to_droplet.py – Berechnung der ursprünglichen Tröpfchengrösse aus getrockneten Salzresiduen
- coagulation_chamber_model.py – Modellierung der brownschen Koagulation zur Abschätzung von Koagulationskammer-Volumen für verschiedene Vernebler

## Datenformat
- Rohdaten: native SMPS CSV-Exporte, keine Vorverarbeitung nötig
