import sys
from pathlib import Path

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
