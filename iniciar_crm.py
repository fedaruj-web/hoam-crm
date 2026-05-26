import subprocess
import sys
from pathlib import Path

base = Path(__file__).resolve().parent
requirements = base / "requirements.txt"
app = base / "app.py"

print("Instalando/validando dependencias...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements)])

print("Iniciando Hoam CRM Comercial...")
subprocess.check_call([sys.executable, "-m", "streamlit", "run", str(app)])
