import os
import sys
from pathlib import Path

# Windows: force UTF-8 for stdout/stderr to prevent Korean text corruption
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# Load .env from project root (if present) before anything else
try:
    from dotenv import load_dotenv
    _env = Path(__file__).parent.parent.parent / ".env"
    if _env.exists():
        load_dotenv(_env, override=True)
except ImportError:
    pass

from infradx.tui.app import InfraDxApp


def main() -> None:
    app = InfraDxApp()
    app.run()


if __name__ == "__main__":
    main()
