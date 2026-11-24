"""Check the published site: python verify.py --base URL --slugs SLUG ... (see src/cora_mcp/verify.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from cora_mcp.verify import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
