"""Automatic database and vector store ingestion on startup."""
import logging
import sqlite3
from pathlib import Path

from src.app.config import settings

logger = logging.getLogger(__name__)


def check_sql_database_exists() -> bool:
    """Check if SQLite database exists and has all required data tables."""
    db_path = settings.sqlite_path
    logger.info(f"Checking SQL database at: {db_path}")
    
    if not db_path.exists():
        logger.info(f"  → Database file does not exist")
        return False
    
    logger.info(f"  → Database file exists")
    
    try:
        connection = sqlite3.connect(str(db_path))
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row[0] for row in cursor.fetchall()}
            
            logger.info(f"  → Found {len(existing_tables)} table(s) in database: {sorted(existing_tables)}")
            
            # Check if all required data tables exist
            required_tables = set(settings.required_data_tables)
            logger.info(f"  → Required tables ({len(required_tables)}): {sorted(required_tables)}")
            
            missing_tables = required_tables - existing_tables
            if missing_tables:
                logger.info(f"  → Missing {len(missing_tables)} required table(s): {sorted(missing_tables)}")
                return False
            
            logger.info(f"  → ✓ All required tables exist")
            return True
        finally:
            connection.close()
    except Exception as e:
        logger.error(f"  → ✗ Error checking database: {e}", exc_info=True)
        return False


def check_vector_store_exists() -> bool:
    """Check if FAISS vector store exists and is complete."""
    index_dir = settings.faiss_index_dir
    index_faiss = index_dir / "index.faiss"
    index_pkl = index_dir / "index.pkl"
    
    logger.info(f"Checking vector store at: {index_dir}")
    
    # Check if directory exists
    if not index_dir.exists():
        logger.info(f"  → Vector store directory does not exist")
        return False
    
    # Check for required FAISS files
    # FAISS typically saves both index.faiss (vectors) and index.pkl (metadata)
    if index_faiss.exists():
        if index_pkl.exists():
            logger.info(f"  → ✓ Vector store exists and is complete (found index.faiss and index.pkl)")
            return True
        else:
            # Some FAISS configurations may not use .pkl, so just .faiss is acceptable
            logger.info(f"  → ✓ Vector store exists (found index.faiss)")
            return True
    else:
        logger.info(f"  → Vector store does not exist (missing index.faiss)")
        return False


def auto_ingest_if_needed() -> None:
    """Automatically ingest SQL and RAG data if databases don't exist."""
    logger.info("")
    logger.info("  [Auto-Ingest] Starting verification process...")
    logger.info("")
    
    # Check SQL database
    logger.info("  [SQL Database] Verifying...")
    sql_exists = check_sql_database_exists()
    
    if not sql_exists:
        logger.info("")
        logger.info("  [SQL Database] ⚠ Not found or incomplete. Starting ingestion...")
        logger.info("")
        try:
            import sys
            # Find backend directory - try multiple approaches
            # 1. Try current working directory (works in Render)
            cwd = Path.cwd()
            if (cwd / "scripts" / "ingest_sql.py").exists():
                backend_dir = cwd
            # 2. Try relative to this file (works in local development)
            elif (Path(__file__).resolve().parents[3] / "scripts" / "ingest_sql.py").exists():
                backend_dir = Path(__file__).resolve().parents[3]
            # 3. Try using project_root from settings
            elif (settings.project_root / "scripts" / "ingest_sql.py").exists():
                backend_dir = settings.project_root
            else:
                # Fallback: assume we're in backend directory
                backend_dir = Path.cwd()
            
            scripts_path = backend_dir / "scripts" / "ingest_sql.py"
            if not scripts_path.exists():
                logger.warning(
                    f"  [SQL Database] ⚠ Scripts not found at {scripts_path}. "
                    f"Skipping auto-ingest. Data should be pre-ingested."
                )
                return
            
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            
            logger.info("  [SQL Database] Importing ingest script...")
            from scripts.ingest_sql import ingest as ingest_sql
            
            logger.info("  [SQL Database] Running ingestion (this may take a while)...")
            ingest_sql()
            logger.info("  [SQL Database] ✓ Ingestion completed successfully")
            logger.info("")
        except Exception as e:
            logger.error(f"  [SQL Database] ✗ Ingestion failed: {e}", exc_info=True)
            raise
    else:
        logger.info("  [SQL Database] ✓ Already exists and is complete")
        logger.info("")
    
    # Check vector store
    logger.info("  [Vector Store] Verifying...")
    vector_exists = check_vector_store_exists()
    
    if not vector_exists:
        logger.info("")
        logger.info("  [Vector Store] ⚠ Not found. Starting RAG ingestion...")
        logger.info("")
        try:
            import sys
            # Find backend directory - try multiple approaches
            # 1. Try current working directory (works in Render)
            cwd = Path.cwd()
            if (cwd / "scripts" / "ingest_rag.py").exists():
                backend_dir = cwd
            # 2. Try relative to this file (works in local development)
            elif (Path(__file__).resolve().parents[3] / "scripts" / "ingest_rag.py").exists():
                backend_dir = Path(__file__).resolve().parents[3]
            # 3. Try using project_root from settings
            elif (settings.project_root / "scripts" / "ingest_rag.py").exists():
                backend_dir = settings.project_root
            else:
                # Fallback: assume we're in backend directory
                backend_dir = Path.cwd()
            
            scripts_path = backend_dir / "scripts" / "ingest_rag.py"
            if not scripts_path.exists():
                logger.warning(
                    f"  [Vector Store] ⚠ Scripts not found at {scripts_path}. "
                    f"Skipping auto-ingest. Data should be pre-ingested."
                )
                return
            
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            
            logger.info("  [Vector Store] Importing RAG ingest script...")
            from scripts.ingest_rag import ingest as ingest_rag
            
            logger.info("  [Vector Store] Running ingestion (this may take a while)...")
            ingest_rag()
            logger.info("  [Vector Store] ✓ Ingestion completed successfully")
            logger.info("")
        except Exception as e:
            logger.error(f"  [Vector Store] ✗ Ingestion failed: {e}", exc_info=True)
            raise
    else:
        logger.info("  [Vector Store] ✓ Already exists")
        logger.info("")
    
    logger.info("  [Auto-Ingest] ✓ Verification process completed")
    logger.info("")

