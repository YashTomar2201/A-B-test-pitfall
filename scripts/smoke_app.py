"""Headless smoke test of every Streamlit page (no server needed)."""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
pages = ["app/Home.py", "app/pages/1_Pitfall_Playground.py", "app/pages/2_Power_Calculator.py",
         "app/pages/3_Health_Checker.py", "app/pages/4_Audit.py"]
pages = [str(ROOT / p) for p in pages]
failed = 0
for p in pages:
    at = AppTest.from_file(p, default_timeout=120).run()
    status = "OK" if not at.exception else f"EXCEPTION: {at.exception[0].value[:300]}"
    failed += bool(at.exception)
    print(f"{p}: {status}  (metrics={len(at.metric)}, errors={len(at.error)})")

# exercise the interactive pieces
at = AppTest.from_file(str(ROOT / "app/pages/1_Pitfall_Playground.py"), default_timeout=120).run()
for choice in at.selectbox[0].options:
    at.selectbox[0].select(choice).run()
    print(f"  playground '{choice}': {'OK' if not at.exception else 'EXCEPTION ' + at.exception[0].value[:200]}")
    failed += bool(at.exception)
at = AppTest.from_file(str(ROOT / "app/pages/3_Health_Checker.py"), default_timeout=120).run()
for choice in at.selectbox[0].options:
    at.selectbox[0].select(choice).run()
    verdict = [e.value for e in list(at.error) + list(at.warning) + list(at.success) if "Verdict" in e.value]
    print(f"  checker '{choice}': {verdict[0] if verdict else 'NO VERDICT'}")
    failed += bool(at.exception)
sys.exit(1 if failed else 0)
