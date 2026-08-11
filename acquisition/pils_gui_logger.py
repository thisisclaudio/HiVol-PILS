''' PILS GUI Logger
Einfaches GUI-Tool zum gleichzeitigen Auslesen von CPC, OPC und TC-08, mit Live-Plot und CSV-Logging.
'''

import os
import sys
import time
import csv
import ctypes
import threading
import collections
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import numpy as np
import serial
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ── Konfiguration ─────────────────────────────────────────────────────────────
OPC_PORT      = "COM12"
CPC_PORT      = "COM8"
CPC_BAUD      = 115200
MESSDAUER_S   = 30
LOG_DIR       = "data"
PLOT_WINDOW_S = 30.0
AVG_WINDOW_S  = 10.0

# TC-08 Kanäle, die ausgelesen werden sollen
TC08_KANAELE = [1, 2, 3, 4]
# ─────────────────────────────────────────────────────────────────────────────

# Gemeinsamer Zustand, wird von den Lese-Threads geschrieben und vom GUI gelesen
data_lock = threading.Lock()
live_data = {
    "cpc_conc":   float("nan"),
    "opc_conc":   float("nan"),
    "opc_flow":   float("nan"),
    "opc_bins":   [float("nan")] * 16,
    "t1": float("nan"), "t2": float("nan"), "t3": float("nan"), "t4": float("nan"),
}


def fmt(v, dec=4):
    """NaN-sichere Formatierung für CSV / Anzeige."""
    return "" if (v != v) else f"{v:.{dec}f}"


def disp(v, dec=2):
    """NaN-sichere Formatierung für die GUI-Anzeige (zeigt '–' bei NaN)."""
    return "–" if (v != v) else f"{v:.{dec}f}"


# ── TC-08 ─────────────────────────────────────────────────────────────────────
class TC08:
    UNITS_CELSIUS = 0
    TYPE_K        = ctypes.c_int8(75)   # ord('K')

    def __init__(self, kanaele):
        self.kanaele    = kanaele
        self._handle    = None
        self._temp      = np.zeros(9, dtype=np.float32)
        self._overflow  = ctypes.c_int16(0)
        self._ok        = False

        try:
            from picosdk.usbtc08 import usbtc08 as tc08lib
            from picosdk.functions import assert_pico2000_ok
            self._lib    = tc08lib
            self._assert = assert_pico2000_ok
            self._mode   = "picosdk"
        except ImportError:
            try:
                self._lib  = ctypes.windll.LoadLibrary("usbtc08.dll")
                self._mode = "ctypes"
            except OSError:
                print("TC-08: weder picosdk noch usbtc08.dll gefunden – Temperaturen werden nicht geloggt")
                return

        self._open()

    def _open(self):
        try:
            if self._mode == "picosdk":
                handle = self._lib.usb_tc08_open_unit()
                self._assert(handle)
                self._handle = handle
                self._lib.usb_tc08_set_mains(self._handle, 0)
                self._lib.usb_tc08_set_channel(self._handle, 0, ctypes.c_int8(32))
                for ch in self.kanaele:
                    self._lib.usb_tc08_set_channel(self._handle, ch, self.TYPE_K)
            else:
                self._handle = self._lib.usb_tc08_open_unit()
                self._lib.usb_tc08_set_mains(self._handle, 50)
                self._lib.usb_tc08_set_channel(self._handle, 0, 0)
                for ch in self.kanaele:
                    self._lib.usb_tc08_set_channel(self._handle, ch, ord('K'))
            self._ok = True
            print("TC-08 verbunden")
        except Exception as e:
            print(f"TC-08 Fehler beim Öffnen: {e}")

    def read(self) -> dict:
        result = {ch: float("nan") for ch in self.kanaele}
        if not self._ok or self._handle is None:
            return result
        try:
            self._lib.usb_tc08_get_single(
                self._handle,
                self._temp.ctypes.data,
                ctypes.byref(self._overflow),
                self.UNITS_CELSIUS
            )
            for ch in self.kanaele:
                result[ch] = float(self._temp[ch])
        except Exception as e:
            print(f"TC-08 Lesefehler: {e}")
        return result

    def close(self):
        if self._ok and self._handle is not None:
            try:
                self._lib.usb_tc08_close_unit(self._handle)
            except Exception:
                pass


# ── Lese-Threads (laufen dauerhaft im Hintergrund, 1x pro Sekunde) ────────────
def tc08_thread(tc08_obj, stop_event):
    while not stop_event.is_set():
        temps = tc08_obj.read()
        with data_lock:
            live_data["t1"] = temps.get(1, float("nan"))
            live_data["t2"] = temps.get(2, float("nan"))
            live_data["t3"] = temps.get(3, float("nan"))
            live_data["t4"] = temps.get(4, float("nan"))
        time.sleep(1)


def opc_thread(stop_event):
    print(f"[OPC] Verbinde {OPC_PORT} ...")
    try:
        from usbiss.spi import SPI
        import opcng as opc
        spi = SPI(OPC_PORT)
        spi.mode, spi.max_speed_hz, spi.lsbfirst = 1, 500000, False
        dev = opc.detect(spi)
        dev.on()
        time.sleep(10)
        for _ in range(5):
            dev.histogram()
            time.sleep(1)
    except Exception as e:
        print(f"[OPC] FEHLER beim Verbinden: {e}")
        return

    try:
        while not stop_event.is_set():
            h      = dev.histogram()
            bins   = [h.get(f"Bin {i}", float("nan")) for i in range(16)]
            period = h.get("Sampling Period", 1.0)

            flow_key = next(
                (k for k in h if "flow" in k.lower() or k.lower() == "sfr"),
                None
            )
            flow = h.get(flow_key, float("nan")) if flow_key is not None else float("nan")
            if flow_key is None:
                print(f"[OPC] Warnung: kein 'flow'/'SFR'-Key im histogram()-Dict gefunden. "
                      f"Verfügbare Keys: {list(h.keys())}")

            conc   = sum(b for b in bins if b == b)
            with data_lock:
                live_data["opc_conc"] = conc
                live_data["opc_flow"] = flow
                live_data["opc_bins"] = bins
            time.sleep(1)
    except Exception as e:
        print(f"[OPC] Thread-Fehler: {e}")
    finally:
        try:
            dev.off()
        except Exception:
            pass


def cpc_thread(ser, stop_event):
    def read_line():
        line = bytearray()
        while True:
            c = ser.read(1)
            if not c:
                return None
            line += c
            if line[-1:] == b'\r':
                return line.decode("utf-8", errors="ignore").strip()

    while not stop_event.is_set():
        try:
            ser.write(b"rall\r")
            line = read_line()
            if not line:
                continue
            value = float(line.split(",")[0])
            with data_lock:
                live_data["cpc_conc"] = value
        except Exception:
            pass


# ── Dialog: Material + Fluss abfragen ─────────────────────────────────────────
class MessungDialog:
    def __init__(self, parent):
        self.result = None
        self.top = tk.Toplevel(parent)
        self.top.title("Neue Messung")
        self.top.grab_set()
        self.top.resizable(False, False)

        ttk.Label(self.top, text="Kernmaterial (z.B. NaCl / Russ):").grid(
            row=0, column=0, padx=10, pady=(10, 2), sticky="w")
        self.material_var = tk.StringVar()
        ttk.Entry(self.top, textvariable=self.material_var, width=25).grid(
            row=1, column=0, padx=10, pady=(0, 10))

        ttk.Label(self.top, text="Fluss [lpm]:").grid(
            row=2, column=0, padx=10, pady=(0, 2), sticky="w")
        self.fluss_var = tk.StringVar()
        ttk.Entry(self.top, textvariable=self.fluss_var, width=25).grid(
            row=3, column=0, padx=10, pady=(0, 10))

        ttk.Label(self.top, text="Durchmesser [nm]:").grid(
            row=4, column=0, padx=10, pady=(0, 2), sticky="w")
        self.durchmesser_var = tk.StringVar()
        ttk.Entry(self.top, textvariable=self.durchmesser_var, width=25).grid(
            row=5, column=0, padx=10, pady=(0, 10))

        ttk.Label(self.top, text="Kommentar (optional):").grid(
            row=6, column=0, padx=10, pady=(0, 2), sticky="w")
        self.kommentar_text = tk.Text(self.top, width=30, height=3)
        self.kommentar_text.grid(row=7, column=0, padx=10, pady=(0, 10))

        btn_frame = ttk.Frame(self.top)
        btn_frame.grid(row=8, column=0, pady=(0, 10))
        ttk.Button(btn_frame, text="Start", command=self._ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Abbrechen", command=self._cancel).pack(side="left", padx=5)

        self.top.protocol("WM_DELETE_WINDOW", self._cancel)

    def _ok(self):
        material    = self.material_var.get().strip()
        fluss       = self.fluss_var.get().strip()
        durchmesser = self.durchmesser_var.get().strip()
        kommentar   = self.kommentar_text.get("1.0", "end").strip().replace("\n", " ")
        if not material or not fluss or not durchmesser:
            messagebox.showwarning("Fehlende Angabe", "Bitte Material, Fluss und Durchmesser angeben.")
            return
        self.result = (material, fluss, durchmesser, kommentar)
        self.top.destroy()

    def _cancel(self):
        self.result = None
        self.top.destroy()


# ── Haupt-GUI ─────────────────────────────────────────────────────────────────
class PilsGUI:
    def __init__(self, root):
        self.root = root
        root.title("PILS Live-Messung")

        self.messung_aktiv       = False
        self.csv_file            = None
        self.csv_writer          = None
        self.messung_start_time  = None
        self.aktuelles_material  = ""
        self.aktueller_fluss     = ""
        self.aktueller_durchmesser = ""
        self.aktueller_kommentar = ""

        # Verlauf für Live-Plot & gleitenden Mittelwert: (timestamp, cpc, opc)
        self.history = collections.deque()

        self._build_layout()
        self.update_loop()

    def _build_layout(self):
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")

        # -- Temperaturen --
        temp_frame = ttk.LabelFrame(main, text="TC-08 Temperaturen [°C]", padding=8)
        temp_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        self.temp_vars = {}
        for i, ch in enumerate(TC08_KANAELE):
            ttk.Label(temp_frame, text=f"Kanal {ch}:").grid(row=i, column=0, sticky="w", padx=4, pady=2)
            var = tk.StringVar(value="–")
            self.temp_vars[ch] = var
            ttk.Label(temp_frame, textvariable=var, width=10, anchor="e").grid(row=i, column=1, padx=4, pady=2)

        # -- CPC / OPC Übersicht --
        conc_frame = ttk.LabelFrame(main, text="CPC / OPC Übersicht", padding=8)
        conc_frame.grid(row=0, column=1, sticky="nsew", pady=(0, 8))

        self.cpc_var  = tk.StringVar(value="–")
        self.opc_var  = tk.StringVar(value="–")
        self.flow_var = tk.StringVar(value="–")

        ttk.Label(conc_frame, text="CPC Konzentration [#/cm³]:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(conc_frame, textvariable=self.cpc_var, width=12, anchor="e").grid(row=0, column=1, padx=4, pady=2)

        ttk.Label(conc_frame, text="OPC Konzentration [#/mL]:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(conc_frame, textvariable=self.opc_var, width=12, anchor="e").grid(row=1, column=1, padx=4, pady=2)

        ttk.Label(conc_frame, text="OPC Sample Flow Rate:").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(conc_frame, textvariable=self.flow_var, width=12, anchor="e").grid(row=2, column=1, padx=4, pady=2)

        # -- OPC Bins --
        bins_frame = ttk.LabelFrame(main, text="OPC-N2 Bins (0-15)", padding=8)
        bins_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
        self.bin_vars = []
        for i in range(16):
            r, c = divmod(i, 4)
            ttk.Label(bins_frame, text=f"Bin {i}:").grid(row=r, column=2 * c, sticky="w", padx=4, pady=2)
            var = tk.StringVar(value="–")
            self.bin_vars.append(var)
            ttk.Label(bins_frame, textvariable=var, width=9, anchor="e").grid(row=r, column=2 * c + 1, padx=4, pady=2)

        # -- Steuerung --
        ctrl_frame = ttk.Frame(main)
        ctrl_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.start_button = ttk.Button(ctrl_frame, text="Neue Messung starten (30 s)",
                                        command=self.on_start_messung)
        self.start_button.pack(side="left")

        # -- Live-Plot (letzte 30 s) --
        plot_frame = ttk.LabelFrame(main, text=f"Live-Plot – letzte {PLOT_WINDOW_S:.0f} s", padding=8)
        plot_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 8))

        self.fig = Figure(figsize=(7, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)

        self.ax.set_xlabel("t [s]")
        self.ax.set_ylabel("Konzentration")

        (self.line_cpc,) = self.ax.plot([], [], color="tab:blue", label="CPC [#/cm³]")
        (self.line_opc,) = self.ax.plot([], [], color="tab:orange", label="OPC [#/mL]")
        self.ax.legend(loc="upper left")
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # -- Gleitender 10s-Mittelwert & Verhältnis --
        avg_frame = ttk.LabelFrame(main, text=f"Gleitender Mittelwert ({AVG_WINDOW_S:.0f} s)", padding=8)
        avg_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(0, 8))

        self.cpc_avg_var   = tk.StringVar(value="–")
        self.opc_avg_var   = tk.StringVar(value="–")
        self.ratio_avg_var = tk.StringVar(value="–")

        ttk.Label(avg_frame, text="CPC Ø [#/cm³]:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(avg_frame, textvariable=self.cpc_avg_var, width=12, anchor="e").grid(row=0, column=1, padx=4, pady=2)

        ttk.Label(avg_frame, text="OPC Ø [#/mL]:").grid(row=0, column=2, sticky="w", padx=(20, 4), pady=2)
        ttk.Label(avg_frame, textvariable=self.opc_avg_var, width=12, anchor="e").grid(row=0, column=3, padx=4, pady=2)

        ttk.Label(avg_frame, text="Verhältnis OPC/CPC:").grid(row=0, column=4, sticky="w", padx=(20, 4), pady=2)
        ttk.Label(avg_frame, textvariable=self.ratio_avg_var, width=12, anchor="e").grid(row=0, column=5, padx=4, pady=2)

        # -- Statusbar --
        self.status_var = tk.StringVar(value="Bereit.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=4)
        status_bar.grid(row=1, column=0, sticky="ew")

    # ── Periodischer Update-Loop (1x pro Sekunde: Anzeige + Logging) ──────────
    def update_loop(self):
        with data_lock:
            snap = {
                "cpc_conc": live_data["cpc_conc"],
                "opc_conc": live_data["opc_conc"],
                "opc_flow": live_data["opc_flow"],
                "opc_bins": list(live_data["opc_bins"]),
                "t1": live_data["t1"], "t2": live_data["t2"],
                "t3": live_data["t3"], "t4": live_data["t4"],
            }

        self._update_labels(snap)
        self._update_history_and_plot(snap)

        if self.messung_aktiv:
            elapsed = time.time() - self.messung_start_time
            self._log_row(snap, elapsed)
            if elapsed >= MESSDAUER_S:
                self._stop_messung()
            else:
                self.status_var.set(f"Messung läuft: {elapsed:.0f} / {MESSDAUER_S} s "
                                     f"({self.aktuelles_material}, {self.aktueller_fluss} lpm, "
                                     f"{self.aktueller_durchmesser} nm)")

        self.root.after(1000, self.update_loop)

    def _update_labels(self, snap):
        for ch, var in self.temp_vars.items():
            key = f"t{ch}"
            var.set(disp(snap[key]))
        self.cpc_var.set(disp(snap["cpc_conc"], dec=2))
        self.opc_var.set(disp(snap["opc_conc"], dec=2))
        self.flow_var.set(disp(snap["opc_flow"], dec=3))
        for i, var in enumerate(self.bin_vars):
            var.set(disp(snap["opc_bins"][i], dec=1))

    def _update_history_and_plot(self, snap):
        now = time.time()
        self.history.append((now, snap["cpc_conc"], snap["opc_conc"]))
        # nur die letzten PLOT_WINDOW_S Sekunden behalten
        while self.history and (now - self.history[0][0]) > PLOT_WINDOW_S:
            self.history.popleft()

        # -- gleitender 10s-Mittelwert + Verhältnis --
        recent = [(t, c, o) for (t, c, o) in self.history if (now - t) <= AVG_WINDOW_S]
        cpc_vals = [c for (_, c, _) in recent if c == c]
        opc_vals = [o for (_, _, o) in recent if o == o]
        cpc_avg = np.mean(cpc_vals) if cpc_vals else float("nan")
        opc_avg = np.mean(opc_vals) if opc_vals else float("nan")
        ratio_avg = (opc_avg / cpc_avg) if (cpc_avg == cpc_avg and cpc_avg != 0 and opc_avg == opc_avg) else float("nan")

        self.cpc_avg_var.set(disp(cpc_avg, dec=2))
        self.opc_avg_var.set(disp(opc_avg, dec=2))
        self.ratio_avg_var.set(disp(ratio_avg, dec=4))

        # -- Plot aktualisieren (letzte PLOT_WINDOW_S Sekunden, x-Achse relativ) --
        if self.history:
            t0 = self.history[-1][0]
            xs   = [t - t0 for (t, _, _) in self.history]
            cpcs = [c for (_, c, _) in self.history]
            opcs = [o for (_, _, o) in self.history]

            self.line_cpc.set_data(xs, cpcs)
            self.line_opc.set_data(xs, opcs)

            self.ax.set_xlim(-PLOT_WINDOW_S, 0)
            self.ax.relim(); self.ax.autoscale_view(scalex=False, scaley=True)

            self.canvas.draw_idle()

    # ── Messung starten / loggen / stoppen ────────────────────────────────────
    def on_start_messung(self):
        dialog = MessungDialog(self.root)
        self.root.wait_window(dialog.top)
        if dialog.result is None:
            return
        material, fluss, durchmesser, kommentar = dialog.result

        os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(
            LOG_DIR, f"{material}_{fluss}lpm_{durchmesser}nm_{timestamp}.csv")

        try:
            self.csv_file = open(filename, "w", newline="")
        except Exception as e:
            messagebox.showerror("Fehler", f"CSV konnte nicht erstellt werden:\n{e}")
            return

        self.csv_writer = csv.writer(self.csv_file, delimiter=";")
        header = (
            ["Zeit_s", "Material", "Fluss_lpm", "Durchmesser_nm", "Kommentar",
             "CPC_conc", "OPC_conc", "OPC_SampleFlow"]
            + [f"OPC_Bin{i}" for i in range(16)]
            + ["T1_C", "T2_C", "T3_C", "T4_C"]
        )
        self.csv_writer.writerow(header)

        self.aktuelles_material   = material
        self.aktueller_fluss      = fluss
        self.aktueller_durchmesser = durchmesser
        self.aktueller_kommentar  = kommentar
        self.messung_start_time = time.time()
        self.messung_aktiv      = True
        self.start_button.config(state="disabled")
        self.status_var.set(
            f"Messung gestartet ({material}, {fluss} lpm, {durchmesser} nm"
            + (f", Kommentar: {kommentar}" if kommentar else "")
            + f"). Datei: {filename}")

    def _log_row(self, snap, elapsed):
        row = (
            [f"{elapsed:.1f}", self.aktuelles_material, self.aktueller_fluss, self.aktueller_durchmesser,
             self.aktueller_kommentar,
             fmt(snap["cpc_conc"]), fmt(snap["opc_conc"]), fmt(snap["opc_flow"])]
            + [fmt(v) for v in snap["opc_bins"]]
            + [fmt(snap["t1"], 2), fmt(snap["t2"], 2), fmt(snap["t3"], 2), fmt(snap["t4"], 2)]
        )
        self.csv_writer.writerow(row)
        self.csv_file.flush()

    def _stop_messung(self):
        self.messung_aktiv = False
        try:
            self.csv_file.close()
        except Exception:
            pass
        self.csv_file   = None
        self.csv_writer = None
        self.start_button.config(state="normal")
        self.status_var.set("Messung abgeschlossen. Bereit für neue Messung.")


# ── Programmstart ─────────────────────────────────────────────────────────────
def main():
    stop_event = threading.Event()

    # CPC verbinden
    try:
        cpc_ser = serial.Serial(CPC_PORT, CPC_BAUD, timeout=2)
        cpc_ser.flushInput(); cpc_ser.flushOutput()
        print(f"CPC verbunden: {CPC_PORT}")
    except Exception as e:
        print(f"[CPC] FEHLER: {e}")
        sys.exit(1)

    tc08_obj = TC08(TC08_KANAELE)

    # Lese-Threads starten (laufen im Hintergrund weiter, unabhängig vom Logging)
    t_tc08 = threading.Thread(target=tc08_thread, args=(tc08_obj, stop_event), daemon=True)
    t_opc  = threading.Thread(target=opc_thread, args=(stop_event,), daemon=True)
    t_cpc  = threading.Thread(target=cpc_thread, args=(cpc_ser, stop_event), daemon=True)
    t_tc08.start(); t_opc.start(); t_cpc.start()

    root = tk.Tk()
    app = PilsGUI(root)

    def on_close():
        stop_event.set()
        try:
            cpc_ser.close()
        except Exception:
            pass
        tc08_obj.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()