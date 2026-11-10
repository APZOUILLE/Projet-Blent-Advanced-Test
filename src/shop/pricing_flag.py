"""The `SHOP_BUG` switch used by the workshop to plant a real regression.

`SHOP_BUG=1` lowers the free-shipping threshold from 5000 to 500 cents. Nothing
else changes. Both implementations read it through this module, at request time.

This exists so that `make sabotage` can ask a single blunt question of a
test suite: *does it notice?* A suite built entirely out of mocks does not.
"""

from __future__ import annotations

import os

FREE_SHIPPING_THRESHOLD_CENTS = 5000
BUGGED_FREE_SHIPPING_THRESHOLD_CENTS = 500


def free_shipping_threshold_cents() -> int:
    """Return the current free-shipping threshold, in cents."""
    if os.environ.get("SHOP_BUG") == "1":
        return BUGGED_FREE_SHIPPING_THRESHOLD_CENTS
    return FREE_SHIPPING_THRESHOLD_CENTS
