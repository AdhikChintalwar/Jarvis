from pathlib import Path
import subprocess
import sys

root=Path.cwd()

checks=[
    ("Frontend package", root/"frontend"/"package.json"),
    ("FastAPI app", root/"baby_ui_backend"/"app.py"),
    ("Monitor database module", root/"investor"/"production"/"investment_monitor.py"),
    ("Frontend API helper", root/"frontend"/"src"/"lib"/"api.js"),
]

bad=False
for label,p in checks:
    ok=p.exists()
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {p}")
    bad |= not ok

print("\n== frontend build ==")
r=subprocess.run(["npm","run","build"],cwd=root/"frontend")
if r.returncode:
    print("FAIL  frontend build")
    bad=True
else:
    print("PASS  frontend build")

print("\n== backend syntax ==")
for p in [
    root/"baby_ui_backend"/"app.py",
    root/"investor"/"production"/"investment_monitor.py",
]:
    try:
        subprocess.run([sys.executable,"-m","py_compile",str(p)],check=True)
        print("PASS ",p)
    except subprocess.CalledProcessError:
        print("FAIL ",p)
        bad=True

print("\n== sensitive files ==")
for name in [".env",".env.production",".env.local"]:
    p=root/name
    if p.exists():
        print("CHECK ",p,"exists; confirm it is ignored by Git.")

print("\n== database ==")
db=root/"data"/"baby_investment_monitor.db"
if db.exists():
    print("PASS ",db)
else:
    print("INFO  monitor DB does not exist yet.")

print("\n== requirements ==")
req=root/"requirements.txt"
if req.exists():
    print("PASS ",req)
else:
    print("WARN  requirements.txt is missing. Create/freeze one before VM deployment.")

if bad:
    raise SystemExit("\nBABY CLOUD READINESS: FAIL")

print("\nBABY CLOUD READINESS: PASS")
