import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temporary = tempfile.TemporaryDirectory(prefix="hse-browser-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(temporary.name) / "hse.db")
os.environ["MEDIA_DIR"] = str(Path(temporary.name) / "evidence")
os.environ["DEMO_MODE"] = "true"
os.environ["OPERATOR_TOKEN"] = ""
os.environ["REDIS_URL"] = ""
os.environ["S3_ENDPOINT"] = ""

if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run("backend.main:app", host="127.0.0.1", port=8010)
    finally:
        from backend.database import engine

        engine.dispose()
        temporary.cleanup()
