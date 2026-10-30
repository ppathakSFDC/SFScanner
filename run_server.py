"""PyInstaller entry-point. Runs the SF Scanner server as a standalone executable."""
import sys
import os
from pathlib import Path

# When running as a PyInstaller bundle, sys._MEIPASS is the temp extraction dir.
# Make the backend package importable and point static file serving at the
# bundled frontend/dist inside the executable.
if getattr(sys, "frozen", False):
    bundle_dir = Path(sys._MEIPASS)
    sys.path.insert(0, str(bundle_dir))
    os.environ.setdefault("SFSCANNER_BUNDLE_DIR", str(bundle_dir))

import uvicorn
from backend.main import app  # import the object directly — avoids dynamic import inside frozen bundle


def main():
    port = int(os.environ.get("PORT", 8080))
    print(f"SF Scanner starting on http://localhost:{port}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
