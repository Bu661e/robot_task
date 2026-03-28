from __future__ import annotations

import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    response = {
        "backend": "sam3",
        "status": "not_implemented",
        "mode": payload.get("mode"),
    }
    json.dump(response, sys.stdout, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
