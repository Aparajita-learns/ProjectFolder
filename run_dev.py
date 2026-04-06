"""
Start the FastAPI app without setting PYTHONPATH manually.

Usage (from this folder, terminal stays open while you use the browser):

  python run_dev.py

Then open: http://127.0.0.1:8765  (or set PORT in .env / environment)

Default port is 8765 because Windows often blocks 8000 (WinError 10013).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

if __name__ == "__main__":
    import uvicorn

    # Load .env so PORT=8000 works if you set it there
    try:
        from dotenv import load_dotenv

        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass

    port = int(os.getenv("PORT", "8765"))
    host = os.getenv("HOST", "127.0.0.1")

    print(f"Open http://{host}:{port}  (Ctrl+C to stop)\n")

    uvicorn.run(
        "zomato_recommend.app:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=[str(_SRC)],
    )
