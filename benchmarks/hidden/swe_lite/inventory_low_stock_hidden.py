import os
import sys
from pathlib import Path

workdir = Path(os.environ['TARGET_WORKDIR'])
sys.path.insert(0, str(workdir / 'src'))
from inventory.service import low_stock_skus

items = [
    {"sku": "old-item", "stock": 0, "archived": True},
    {"sku": "live-low", "stock": 1, "archived": False},
    {"sku": "live-ok", "stock": 7, "archived": False},
]
assert low_stock_skus(items, threshold=5) == ["live-low"]
print('hidden-ok')
