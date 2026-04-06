import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from inventory.service import low_stock_skus

items = [
    {"sku": "z-last", "stock": 1},
    {"sku": "ignore", "stock": 5},
    {"sku": "a-first", "stock": 2},
]
assert low_stock_skus(items, threshold=5) == ["z-last", "a-first"]
print('ok')
