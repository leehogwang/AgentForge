import os
import sys

sys.path.insert(0, os.environ["TARGET_WORKDIR"])
from utils import slugify

assert slugify('') == ''
assert slugify('***') == ''
assert slugify('MiXeD__Case---123') == 'mixed-case-123'
assert slugify(' ends with space ') == 'ends-with-space'
print('hidden-ok')
