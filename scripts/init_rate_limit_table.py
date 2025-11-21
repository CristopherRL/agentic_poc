"""
Script to initialize the rate_limit table in the SQLite database.

This script creates the rate_limit table if it doesn't exist.
It's safe to run multiple times (idempotent).
"""

from __future__ import annotations

import logging
from src.app.infrastructure.rate_limit_db import init_rate_limit_table

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Initialize the rate_limit table."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    LOGGER.info("Initializing rate_limit table...")
    init_rate_limit_table()
    LOGGER.info("Rate limit table initialized successfully.")


if __name__ == "__main__":
    main()

