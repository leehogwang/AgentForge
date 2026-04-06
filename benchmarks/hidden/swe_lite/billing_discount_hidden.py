import os
import sys
from pathlib import Path

workdir = Path(os.environ['TARGET_WORKDIR'])
sys.path.insert(0, str(workdir / 'src'))
from billing.calc import invoice_total

assert invoice_total(50.0, 0.2, discount=5.0) == 54.0
assert invoice_total(10.0, 0.1, discount=50.0) == 0.0
print('hidden-ok')
