import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from billing.calc import invoice_total

# discount should be applied before tax
assert invoice_total(100.0, 0.1, discount=20.0) == 88.0
print('ok')
