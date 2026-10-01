"""Load the real randomized datasets into DuckDB.

Hillstrom (MineThatData email test, 64,000 customers) - full file.
Criteo Uplift v2.1 - the FULL 13.98M-row file (311 MB gz). The raw file is sorted by treatment, so a
prefix or block sample is NOT a valid experiment; always use all rows.

Run from the repo root:  python src/load/load_real.py
"""
from pathlib import Path

import duckdb

DB = Path("data/warehouse/lab.duckdb")
HILL = Path("data/raw/hillstrom.csv")
CRITEO = Path("data/raw/criteo-research-uplift-v2.1.csv.gz")


def main() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    if HILL.exists():
        con.execute(f"""
            CREATE OR REPLACE TABLE raw.hillstrom AS
            SELECT row_number() OVER () AS user_id, *
            FROM read_csv_auto('{HILL.as_posix()}')
        """)
    if CRITEO.exists():
        # FLOAT (not DOUBLE) for the anonymised features keeps the 14M-row table compact.
        con.execute(f"""
            CREATE OR REPLACE TABLE raw.criteo AS
            SELECT row_number() OVER () AS user_id,
                   f0, f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11,
                   treatment::TINYINT AS treatment, conversion::TINYINT AS conversion,
                   visit::TINYINT AS visit, exposure::TINYINT AS exposure
            FROM read_csv('{CRITEO.as_posix()}', header = true,
                          columns = {{'f0':'FLOAT','f1':'FLOAT','f2':'FLOAT','f3':'FLOAT','f4':'FLOAT',
                                     'f5':'FLOAT','f6':'FLOAT','f7':'FLOAT','f8':'FLOAT','f9':'FLOAT',
                                     'f10':'FLOAT','f11':'FLOAT','treatment':'INTEGER',
                                     'conversion':'INTEGER','visit':'INTEGER','exposure':'INTEGER'}})
        """)
    for t in ("hillstrom", "criteo"):
        try:
            n = con.execute(f"SELECT count(*) FROM raw.{t}").fetchone()[0]
            print(f"raw.{t}: {n:,} rows")
        except duckdb.CatalogException:
            print(f"raw.{t}: not loaded")
    con.close()


if __name__ == "__main__":
    main()
