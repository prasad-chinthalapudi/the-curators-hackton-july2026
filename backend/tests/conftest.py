import os

# API tests are deterministic, offline, and never spend OpenAI tokens.
os.environ["PIH_DATA_MODE"] = "mock"
