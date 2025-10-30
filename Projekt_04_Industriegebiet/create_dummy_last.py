import pandas as pd, numpy as np
idx = pd.date_range("2025-01-01", periods=96*365, freq="15min")
df = pd.DataFrame({
    "time": idx,
    "elec_kw": 300 + 100*np.sin(np.linspace(0, 20*np.pi, len(idx)))
})
df.to_csv("data/defaults/standard_lastgang_elec_15min.csv", index=False)
