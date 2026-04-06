import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["TARGET_WORKDIR"])
from config_loader import load_config

def expect_value_error(payload):
    try:
        load_config(payload)
    except ValueError:
        return
    raise AssertionError(f"expected ValueError for {payload}")

assert load_config({"APP_DEBUG": "YES", "APP_RETRIES": "7"}) == {"debug": True, "retries": 7}
expect_value_error({"APP_DEBUG": "maybe"})
expect_value_error({"APP_RETRIES": "nope"})
print("hidden-ok")
