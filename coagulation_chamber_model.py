import numpy as np
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# Konstanten
# -----------------------------------------------------------------------------
k_B = 1.380649e-23      # J/K
T = 298.15              # K
mu = 1.83e-5            # Pa·s
lambda_air = 6.6e-8     # m

# -----------------------------------------------------------------------------
# Systemparameter
# -----------------------------------------------------------------------------
aerosol_flow_L_min = 10.0
dp_small_um = 0.1
dp_small_m = dp_small_um * 1e-6

droplet_sizes_um = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0])
throughputs_ml_min = np.array([0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0])

# -----------------------------------------------------------------------------
# Modelle
# -----------------------------------------------------------------------------
def cunningham(dp):
    Kn = 2 * lambda_air / dp
    return 1 + Kn * (1.257 + 0.4 * np.exp(-1.1 / Kn))


def diffusion(dp):
    return (k_B * T * cunningham(dp)) / (3 * np.pi * mu * dp)


def coagulation_kernel(dp1, dp2):
    D1 = diffusion(dp1)
    D2 = diffusion(dp2)
    K_m3_s = 2 * np.pi * (D1 + D2) * (dp1 + dp2)
    return K_m3_s * 1e6  # cm³/s


def chamber_properties(droplet_m, throughput_ml_min):
    K12 = coagulation_kernel(dp_small_m, droplet_m)

    throughput_m3_s = throughput_ml_min * 1e-6 / 60
    r = droplet_m / 2
    V_drop = (4 / 3) * np.pi * r**3
    droplets_s = throughput_m3_s / V_drop

    aerosol_flow_m3_s = aerosol_flow_L_min * 1e-3 / 60
    N2_cm3 = (droplets_s / aerosol_flow_m3_s) / 1e6

    tau = 1 / (K12 * N2_cm3)
    chamber_volume_L = aerosol_flow_m3_s * tau * 1000

    return tau, chamber_volume_L, K12, N2_cm3

# -----------------------------------------------------------------------------
# Berechnung
# -----------------------------------------------------------------------------
tau = np.zeros((len(droplet_sizes_um), len(throughputs_ml_min)))
volume = np.zeros_like(tau)
K12 = np.zeros_like(tau)
N2 = np.zeros_like(tau)

print("Droplet (µm) | Throughput (ml/min) | K12 (cm³/s) | N2 (1/cm³) | τ (s) | Volume (L)")
print("-" * 85)

for i, d_um in enumerate(droplet_sizes_um):
    for j, tp in enumerate(throughputs_ml_min):
        t, v, k, n = chamber_properties(d_um * 1e-6, tp)
        tau[i, j] = t
        volume[i, j] = v
        K12[i, j] = k
        N2[i, j] = n

        print(f"{d_um:10.1f} | {tp:17.2f} | {k:10.2e} | {n:10.2e} | {t:6.2f} | {v:8.2f}")

# -----------------------------------------------------------------------------
# Plots
# -----------------------------------------------------------------------------
plt.rcParams.update({"font.size": 10})

def plot_vs_size(y, ylabel, title, logy=False):
    plt.figure(figsize=(9, 5))
    for j, tp in enumerate(throughputs_ml_min):
        plt.plot(droplet_sizes_um, y[:, j], marker="o", label=f"{tp:.2f} ml/min")
    plt.xlabel("Droplet size (µm)")
    plt.ylabel(ylabel)
    plt.title(title)
    if logy:
        plt.yscale("log")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_vs_throughput(y, ylabel, title):
    plt.figure(figsize=(9, 5))
    for i, d in enumerate(droplet_sizes_um):
        plt.plot(throughputs_ml_min, y[i, :], marker="o", label=f"{d:.1f} µm")
    plt.xlabel("Throughput (ml/min)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


plot_vs_size(K12, "K$_{12}$ (cm³/s)", "Brownian coagulation coefficient", logy=True)
plot_vs_size(tau, "Time constant τ (s)", "Coagulation time constant")
plot_vs_size(volume, "Chamber volume (L)", "Required chamber volume")

plot_vs_throughput(tau, "Time constant τ (s)", "τ vs throughput")
plot_vs_throughput(volume, "Chamber volume (L)", "Volume vs throughput")
