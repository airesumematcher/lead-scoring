"""Database connection and session management."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from lead_scoring.database import Base
from lead_scoring.database.models import AuditLog, BatchJob, Feedback, Lead, Score, ScoreAuditRecord


class DatabaseConfig:
    """Database configuration."""

    def __init__(self, db_url: str = None):
        """
        Initialize database config.

        Args:
            db_url: Database connection URL.
                   Defaults to DATABASE_URL env var or local SQLite.
        """
        if db_url is None:
            db_url = os.getenv("DATABASE_URL")

        if db_url is None:
            db_dir = Path(__file__).resolve().parents[3] / "data"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{db_dir / 'leads.db'}"

        connect_args = {}
        if db_url.startswith("sqlite:///"):
            sqlite_path = Path(db_url.replace("sqlite:///", "", 1))
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            connect_args["check_same_thread"] = False
        elif db_url.startswith("sqlite://"):
            connect_args["check_same_thread"] = False

        self.db_url = db_url
        self.engine = create_engine(db_url, echo=False, connect_args=connect_args)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    def create_tables(self):
        """Create all tables in database."""
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()


# Default database instance
_db_config = None


def get_db_config() -> DatabaseConfig:
    """Get or create default database config."""
    global _db_config
    if _db_config is None:
        _db_config = DatabaseConfig()
    return _db_config


def get_session() -> Session:
    """Get a new database session."""
    return get_db_config().get_session()


def init_db():
    """Initialize database tables."""
    get_db_config().create_tables()


class DatabaseManager:
    """Helper class for database operations."""

    def __init__(self, session: Session = None):
        """
        Initialize database manager.

        Args:
            session: SQLAlchemy session. If None, creates new session.
        """
        self.session = session or get_session()

    def add_lead(self, lead_id: str, email: str, first_name: str, 
                 last_name: str, company_name: str, **kwargs) -> Lead:
        """Add a new lead to database."""
        lead = Lead(
            lead_id=lead_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            company_name=company_name,
            **kwargs
        )
        self.session.add(lead)
        self.session.commit()
        return lead

    def add_score(self, lead_id: str, score: float, grade: str, **kwargs) -> Score:
        """Add a score for a lead."""
        score_obj = Score(
            lead_id=lead_id,
            score=score,
            grade=grade,
            **kwargs
        )
        self.session.add(score_obj)
        self.session.commit()
        return score_obj

    def add_feedback(self, lead_id: str, outcome: str, **kwargs) -> Feedback:
        """Add feedback for a lead."""
        feedback_obj = Feedback(
            lead_id=lead_id,
            outcome=outcome,
            **kwargs
        )
        self.session.add(feedback_obj)
        self.session.commit()
        return feedback_obj

    def get_lead(self, lead_id: str) -> Lead:
        """Get lead by ID."""
        return self.session.query(Lead).filter(Lead.lead_id == lead_id).first()

    def get_scores_for_lead(self, lead_id: str) -> list:
        """Get all scores for a lead."""
        return self.session.query(Score).filter(Score.lead_id == lead_id).all()

    def get_feedback_for_lead(self, lead_id: str) -> list:
        """Get all feedback for a lead."""
        return self.session.query(Feedback).filter(Feedback.lead_id == lead_id).all()

    def get_all_feedback(self) -> list:
        """Get all feedback entries, oldest first."""
        return self.session.query(Feedback).order_by(Feedback.submitted_at.asc()).all()

    def delete_all_feedback(self) -> int:
        """Delete all feedback entries and return the number removed."""
        count = self.session.query(Feedback).count()
        self.session.query(Feedback).delete()
        self.session.commit()
        return count

    def add_audit_log(self, operation: str, **kwargs) -> AuditLog:
        """Add audit log entry."""
        log = AuditLog(operation=operation, **kwargs)
        self.session.add(log)
        self.session.commit()
        return log

    def start_batch_job(self, job_name: str) -> BatchJob:
        """Start a batch job."""
        from datetime import datetime
        job = BatchJob(
            job_name=job_name,
            status="running",
            started_at=datetime.utcnow()
        )
        self.session.add(job)
        self.session.commit()
        return job

    def complete_batch_job(self, job_id: int, successful: int, failed: int) -> BatchJob:
        """Complete a batch job."""
        from datetime import datetime
        job = self.session.query(BatchJob).filter(BatchJob.id == job_id).first()
        if job:
            job.status = "completed"
            job.successful_leads = successful
            job.failed_leads = failed
            job.completed_at = datetime.utcnow()
            self.session.commit()
        return job

    def close(self):
        """Close database session."""
        self.session.close()
