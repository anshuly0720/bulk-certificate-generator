import os
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./certificates.db")
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", "./storage"))
MAX_RECIPIENTS = int(os.environ.get("MAX_RECIPIENTS", "5000"))