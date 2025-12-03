"""Allow running CLI as `python -m wks.cli`."""

import sys
from . import main

if __name__ == "__main__":
    sys.exit(main())
