"""Configuration helpers for the market analysis agent scaffold."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "ecommerce_agents"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANALYSIS_DB_PATH = PROJECT_ROOT / ".adk" / "analysis_history.db"
DEFAULT_MODEL = os.getenv("ADK_MODEL", "gemini-3.1-pro-preview")
DEFAULT_MARKET = os.getenv("DEFAULT_MARKET", "CA")
ANALYSIS_DB_PATH = os.getenv("ANALYSIS_DB_PATH", str(DEFAULT_ANALYSIS_DB_PATH))
