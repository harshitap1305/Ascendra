import os
import pytest

# Set required environment variables before app modules are imported
os.environ["MONGODB_URI"] = "mongodb://localhost:27017/test_db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-testing-1234567890"
os.environ["GROQ_API_KEY"] = "gsk_test_api_key_dummy"
os.environ["DATABASE_NAME"] = "test_ascendra"
