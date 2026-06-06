from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.app_env == "development",
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401 — registers models
    Base.metadata.create_all(bind=engine)
    _migrate_base_resumes_unique(engine)
    _repair_tailored_applications_fk(engine)


def _migrate_base_resumes_unique(engine) -> None:
    """Replace the old over-strict UNIQUE(language, is_default) on
    ``base_resumes`` with a partial unique index that only constrains rows
    where is_default = 1.

    The old constraint blocked users from keeping more than one non-default
    CV per language. SQLite doesn't support ``ALTER TABLE ... DROP
    CONSTRAINT``, so we detect the old constraint via PRAGMA and rebuild the
    table preserving all data. Use ``writable_schema`` after the rebuild to
    redirect any foreign keys in other tables that the rename pointed at the
    transient ``_base_resumes_old`` placeholder — see
    ``_repair_tailored_applications_fk`` for the full story.

    Idempotent: a no-op once the migration has run.
    """
    import logging
    log = logging.getLogger(__name__)
    with engine.begin() as conn:
        # Quick exit if the table doesn't exist yet (fresh DB)
        rows = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='base_resumes'"
        ).fetchall()
        if not rows:
            return

        # Look at the current schema. The old constraint shows up as a
        # UNIQUE index covering both columns; the new partial index shows up
        # with a WHERE clause. If we see the old one, rebuild.
        idx_rows = conn.exec_driver_sql("""
            SELECT name, sql FROM sqlite_master
            WHERE type='index' AND tbl_name='base_resumes'
        """).fetchall()
        has_bad_constraint = any(
            r[1] and "is_default" in (r[1] or "") and "WHERE" not in (r[1] or "").upper()
            for r in idx_rows
        )
        # Also detect an auto-index on (language, is_default) which sqlite
        # creates for the table-level UniqueConstraint — sql is NULL in that
        # case, so check via PRAGMA index_list / index_info.
        if not has_bad_constraint:
            for r in conn.exec_driver_sql("PRAGMA index_list(base_resumes)").fetchall():
                idx_name, unique = r[1], r[2]
                if not unique:
                    continue
                cols = [c[2] for c in conn.exec_driver_sql(
                    f"PRAGMA index_info('{idx_name}')").fetchall()]
                if cols == ["language", "is_default"]:
                    # Whether explicit or auto-generated, this is the bad one.
                    # The partial index we want has just ['language'].
                    has_bad_constraint = True
                    break
        if not has_bad_constraint:
            return

        log.info("Migrating base_resumes: dropping bad UNIQUE(language, is_default)")
        # Recreate the table without the over-strict constraint. We use the
        # standard SQLite "rename, create, copy, drop" recipe rather than
        # ALTER TABLE because SQLite can't drop constraints.
        conn.exec_driver_sql("ALTER TABLE base_resumes RENAME TO _base_resumes_old")
        conn.exec_driver_sql("""
            CREATE TABLE base_resumes (
                id INTEGER NOT NULL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                language VARCHAR(8) NOT NULL DEFAULT 'en',
                is_default BOOLEAN DEFAULT 0,
                data JSON NOT NULL,
                version INTEGER DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME
            )
        """)
        conn.exec_driver_sql("""
            INSERT INTO base_resumes (id, name, language, is_default, data, version, created_at, updated_at)
            SELECT id, name, language, is_default, data, version, created_at, updated_at
            FROM _base_resumes_old
        """)
        conn.exec_driver_sql("DROP TABLE _base_resumes_old")
        conn.exec_driver_sql("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_base_resume_default_per_language
            ON base_resumes(language) WHERE is_default = 1
        """)
        log.info("base_resumes migration complete")


def _repair_tailored_applications_fk(engine) -> None:
    """Repair the foreign key on ``tailored_applications.base_resume_id`` if it
    still points at ``_base_resumes_old``.

    The earlier release of this app shipped ``_migrate_base_resumes_unique``
    which renamed ``base_resumes`` → ``_base_resumes_old``, recreated the
    correct table, copied rows, then dropped ``_base_resumes_old``. SQLite's
    ``ALTER TABLE ... RENAME`` rewrites foreign keys in OTHER tables that
    referenced the renamed table — which is what we wanted for the rename
    step but also what corrupted the schema once the placeholder was
    dropped: ``tailored_applications.base_resume_id`` now had a FK pointing
    at a non-existent ``_base_resumes_old``.

    Symptom: every INSERT into ``tailored_applications`` silently rolled
    back, the Tailor & Apply UI appeared to hang forever, and the user got
    no error message because foreign-key violations on a missing table are
    treated as integrity errors that SQLAlchemy autoflushes around.

    Fix: rebuild ``tailored_applications`` with the correct FK target.
    Idempotent — checks the schema text first.
    """
    import logging
    log = logging.getLogger(__name__)
    with engine.begin() as conn:
        rows = conn.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='tailored_applications'"
        ).fetchall()
        if not rows:
            return  # fresh DB — nothing to fix
        schema_sql = rows[0][0] or ""
        if "_base_resumes_old" not in schema_sql:
            return  # already healthy
        log.info("Repairing tailored_applications: FK still points at _base_resumes_old")

        # Standard SQLite "rebuild table" recipe. We disable FK enforcement
        # for the duration so the ON DELETE CASCADE FK on jobs doesn't cause
        # row loss while the table is being swapped.
        conn.exec_driver_sql("PRAGMA foreign_keys = OFF")
        try:
            conn.exec_driver_sql("ALTER TABLE tailored_applications RENAME TO _tailored_applications_old")
            conn.exec_driver_sql("""
                CREATE TABLE tailored_applications (
                    id INTEGER NOT NULL PRIMARY KEY,
                    job_id INTEGER NOT NULL,
                    base_resume_id INTEGER NOT NULL,
                    tailored_resume_data JSON NOT NULL,
                    cover_letter_text TEXT NOT NULL,
                    resume_pdf_path VARCHAR(512),
                    cover_letter_pdf_path VARCHAR(512),
                    ai_model_used VARCHAR(128) NOT NULL,
                    ai_cost_usd FLOAT NOT NULL,
                    tailoring_notes JSON NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                    FOREIGN KEY (base_resume_id) REFERENCES base_resumes(id)
                )
            """)
            conn.exec_driver_sql("""
                INSERT INTO tailored_applications (
                    id, job_id, base_resume_id, tailored_resume_data, cover_letter_text,
                    resume_pdf_path, cover_letter_pdf_path, ai_model_used, ai_cost_usd,
                    tailoring_notes, created_at
                )
                SELECT id, job_id, base_resume_id, tailored_resume_data, cover_letter_text,
                       resume_pdf_path, cover_letter_pdf_path, ai_model_used, ai_cost_usd,
                       tailoring_notes, created_at
                FROM _tailored_applications_old
            """)
            conn.exec_driver_sql("DROP TABLE _tailored_applications_old")
        finally:
            conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        log.info("tailored_applications FK repaired")
