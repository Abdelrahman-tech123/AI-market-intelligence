import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# 1. Get the absolute path of the 'backend' folder where config.py lives
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Pinpoint the exact absolute path to the .env file inside 'backend'
ENV_PATH = os.path.join(BACKEND_DIR, ".env")

class Settings(BaseSettings):
    # Make the app id optional at import-time to avoid a ValidationError if .env is missing.
    # The app should still warn so the developer knows to provide it.
    ebay_app_id: Optional[str] = None
    ebay_cert_id: Optional[str] = None
    debug_mode: bool = False

    # 3. Tell Pydantic to look at that exact, unshakeable path
    model_config = SettingsConfigDict(env_file=ENV_PATH, env_file_encoding="utf-8")

settings = Settings()

# Friendly runtime warning if the key is missing (avoids hard failure on import)
if not settings.ebay_app_id:
    print("⚠️  EBAY_APP_ID not set. Create a .env in backend/ with EBAY_APP_ID=your_app_id to enable eBay features.")