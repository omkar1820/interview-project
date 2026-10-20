import os

os.environ["LLM_MODE"] = "mock"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["ADMIN_API_KEY"] = "test-key"
