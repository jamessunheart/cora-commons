"""Build the static site: python publish.py --src content --out dist (see src/cora_mcp/publish.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from cora_mcp.publish import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
