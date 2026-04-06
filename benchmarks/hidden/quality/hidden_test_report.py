import os
import sys

sys.path.insert(0, os.environ["TARGET_WORKDIR"])
from report import summarize_orders

assert summarize_orders([]) == {"total_amount": 0, "paid_count": 0, "pending_ids": []}
orders = [
    {"id": "a", "amount": 1, "status": "pending"},
    {"id": "b", "amount": 2, "status": "paid"},
    {"id": "c", "amount": 3, "status": "pending"},
]
assert summarize_orders(orders) == {"total_amount": 6, "paid_count": 1, "pending_ids": ["a", "c"]}
print("hidden-ok")
