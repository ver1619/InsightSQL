from __future__ import annotations

import argparse
from pathlib import Path

from insightsql.config import Settings
from insightsql.database import initialize_database


def main() -> None:
    settings = Settings.from_environment()
    parser = argparse.ArgumentParser(description="Initialize the InsightSQL SQLite database.")
    parser.add_argument("--seed", action="store_true", help="Insert synthetic development/demo data.")
    parser.add_argument("--path", type=Path, default=settings.database_path, help="Target SQLite file.")
    arguments = parser.parse_args()
    initialize_database(arguments.path, include_seed=arguments.seed)
    print(f"Initialized {'seeded ' if arguments.seed else ''}InsightSQL database at {arguments.path}")


if __name__ == "__main__":
    main()