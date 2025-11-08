from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine


LOGGER = logging.getLogger(__name__)

PROJ_ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = PROJ_ROOT/"docs"/"public"/"data"
DB_PATH = PROJ_ROOT/"data"/"db"/"app.db"


def load_csvs(csv_dir: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for csv_file in sorted(csv_dir.glob("*.csv")):
        table_name = csv_file.stem.upper()
        LOGGER.info("Loading %s into table %s", csv_file.name, table_name)
        frames[table_name] = pd.read_csv(csv_file)
    if not frames:
        raise FileNotFoundError(f"No CSV files found in {csv_dir}")
    return frames


def persist_frames(frames: dict[str, pd.DataFrame], db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        for table_name, frame in frames.items():
            LOGGER.info("Writing table %s (%d rows)", table_name, len(frame))
            frame.to_sql(table_name, engine, if_exists="replace", index=False)
    finally:
        engine.dispose()


def ingest() -> None:
    frames = load_csvs(CSV_DIR)
    persist_frames(frames, DB_PATH)
    LOGGER.info("SQLite database written to %s", DB_PATH)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ingest()
