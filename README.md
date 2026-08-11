# High-Volume Particle-into-Liquid Sampler (Hi-Vol PILS)

Python-Skripte und Messdaten aus der Bachelorarbeit „Entwicklung eines
neuartigen Hi-Vol PILS (High-Volume Particle-into-Liquid Sampler)“
(Projekt RIQAP, FHNW / Universität Basel).

## Struktur

- `acquisition/pils_gui_logger.py` – GUI zum gleichzeitigen Auslesen und Aufzeichnen von CPC, OPC-N2 und TC-08
- `data/` – Rohmessungen (NaCl- und Russ-Referenzaerosol)
- `data/baseline/` – Untergrundmessungen (DMA auf 0 V, kein Referenzaerosol)
- `utils/smps_quickplot.py` – Einlesen und Plotten von SMPS-Rohdaten
- `utils/smps_salt_to_droplet.py` – Berechnung der ursprünglichen Tröpfchengrösse aus getrockneten Salzresiduen (SMPS)

## Datenformat
`data/*.csv` (NaCl und Russ):
```
Zeit_s;Material;Fluss_lpm;Durchmesser_nm;Kommentar;CPC_conc;OPC_conc;OPC_SampleFlow;
OPC_Bin0..OPC_Bin15;T1_C;T2_C;T3_C;T4_C
```
