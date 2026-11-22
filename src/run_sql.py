"""Run sql/01..07 in DuckDB and export the anonymised result tables to data/processed/ (no names).
Run from the repository root:  python src/run_sql.py
"""
import glob
import os

import duckdb

OUT = os.path.join("data", "processed")
EXPORT = ["coverage", "false_signal", "matching_summary", "cross_source_duplicates", "within_source_duplicates",
          "status_by_source", "not_in_registry", "registry_missing_in_open", "drift_summary", "drift_bands",
          "assistant_checks", "consensus", "error_rates", "error_codes", "agreement", "confusion_r1_r2",
          "time_per_task"]
FORBIDDEN = {"name", "name_norm", "address", "ban_label"}

con = duckdb.connect()
for path in sorted(glob.glob(os.path.join("sql", "*.sql"))):
    sql = open(path, encoding="utf-8").read()
    stmts = [s for s in sql.split(";\n") if s.strip() and not all(
        l.strip().startswith("--") or not l.strip() for l in s.splitlines())]
    last = None
    for s in stmts:
        last = con.execute(s)
    print(f"== {os.path.basename(path)}")
    try:
        print(last.df().head(12).to_string(index=False))
    except Exception:
        pass
for t in EXPORT:
    df = con.execute(f"SELECT * FROM {t}").df()
    assert not FORBIDDEN & set(df.columns), f"{t} would publish a name/address column"
    df.to_csv(os.path.join(OUT, f"{t}.csv"), index=False)
print(f"exported {len(EXPORT)} tables to {OUT}")
