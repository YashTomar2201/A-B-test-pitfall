"""Is the Criteo cross-section usable as a randomized experiment? Check covariate balance."""
import duckdb
import numpy as np

con = duckdb.connect("data/warehouse/lab.duckdb", read_only=True)
df = con.execute("SELECT * FROM raw.criteo").df()
feats = [f"f{i}" for i in range(12)]
t = df.treatment.values == 1

print("standardized mean differences (treated - control) / pooled sd:")
for f in feats:
    a, b = df.loc[~t, f], df.loc[t, f]
    smd = (b.mean() - a.mean()) / np.sqrt((a.var() + b.var()) / 2)
    print(f"  {f}: {smd:+.4f}")

# Is the file position related to treatment? Treatment share per block of 20,000 rows.
blk = df.user_id.values // 20_000
share = df.groupby(blk).treatment.mean()
print("\ntreatment share by sampled block: min %.3f  median %.3f  max %.3f  (n=%d blocks)"
      % (share.min(), share.median(), share.max(), len(share)))
print("sd across blocks: %.4f  (iid sampling would give ~%.4f)"
      % (share.std(), np.sqrt(0.85 * 0.15 / 20_000)))
