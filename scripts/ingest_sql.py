from __future__ import annotations
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from src.app.config import settings

LOGGER = logging.getLogger(__name__)

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

def reset_database(db_path: Path | None = None) -> None:
    target = db_path or settings.sqlite_path
    if target.exists():
        target.unlink()
        LOGGER.info("Removed existing database at %s", target)

def ingest(csv_dir: Path | None = None, db_path: Path | None = None) -> None:
    source_dir = csv_dir or settings.csv_dir
    target_db = db_path or settings.sqlite_path
    frames = load_csvs(source_dir)
    persist_frames(frames, target_db)
    LOGGER.info("SQLite database written to %s", target_db)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ingest()
