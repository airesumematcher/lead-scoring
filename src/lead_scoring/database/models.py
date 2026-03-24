"""SQLAlchemy ORM models for lead scoring system."""

from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from lead_scoring.database import Base


class Lead(Base):
    """Lead entity in database."""
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True)
    lead_id = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    job_title = Column(String(100))
    company_name = Column(String(255))
    domain = Column(String(100), index=True)
    industry = Column(String(100))
    company_size = Column(String(50))
    campaign_id = Column(String(100), index=True)
    source_partner = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    scores = relationship("Score", back_populates="lead", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="lead", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Lead(lead_id={self.lead_id}, email={self.email})>"


class Score(Base):
    """Lead score entity."""
    __tablename__ = "scores"
    
    id = Column(Integer, primary_key=True)
    lead_id = Column(String(50), ForeignKey("leads.lead_id"), nullable=False, index=True)
    score = Column(Float, nullable=False)
    grade = Column(String(1), nullable=False)
    confidence = Column(String(20))
    accuracy_subscore = Column(Float)
    client_fit_subscore = Column(Float)
    engagement_subscore = Column(Float)
    freshness_status = Column(String(20))
    recommended_action = Column(String(50))
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    lead = relationship("Lead", back_populates="scores")
    
    def __repr__(self):
        return f"<Score(lead_id={self.lead_id}, score={self.score}, grade={self.grade})>"


class Feedback(Base):
    """Feedback entity for model improvements."""
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True)
    lead_id = Column(String(50), ForeignKey("leads.lead_id"), nullable=False, index=True)
    outcome = Column(String(20), nullable=False)  # accepted, rejected, neutral
    reason = Column(String(100))
    provided_score = Column(Float)  # Score user expected
    actual_score = Column(Float)    # Score model gave
    submitted_by = Column(String(100))
    submitted_at = Column(DateTime, default=datetime.utcnow, index=True)
    notes = Column(Text)
    
    # Relationship
    lead = relationship("Lead", back_populates="feedback")
    
    def __repr__(self):
        return f"<Feedback(lead_id={self.lead_id}, outcome={self.outcome})>"


class AuditLog(Base):
    """Audit trail for all operations."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    operation = Column(String(50), nullable=False)  # score, feedback, retrain
    lead_id = Column(String(50), index=True)
    details = Column(Text)
    status = Column(String(20))  # success, error
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<AuditLog(operation={self.operation}, lead_id={self.lead_id})>"


class BatchJob(Base):
    """Batch processing jobs."""
    __tablename__ = "batch_jobs"
    
    id = Column(Integer, primary_key=True)
    job_name = Column(String(100), nullable=False)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    total_leads = Column(Integer, default=0)
    successful_leads = Column(Integer, default=0)
    failed_leads = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text)
    
    def __repr__(self):
        return f"<BatchJob(job_name={self.job_name}, status={self.status})>"


class ScoreAuditRecord(Base):
    """PRD-aligned score audit log stored for every scored lead."""

    __tablename__ = "score_audit_records"

    id = Column(Integer, primary_key=True)
    lead_id = Column(String(50), nullable=False, index=True)
    campaign_id = Column(String(100), nullable=False, index=True)
    client_id = Column(String(100), nullable=True, index=True)
    account_domain = Column(String(255), nullable=False, index=True)
    predicted_outcome = Column(String(20), nullable=False)
    actual_outcome = Column(String(20), nullable=True, index=True)
    delivery_decision = Column(String(20), nullable=False)
    approval_score = Column(Float, nullable=False)
    quadrant = Column(String(20), nullable=False)
    campaign_mode = Column(String(20), nullable=False)
    model_version = Column(String(100), nullable=False)
    reasons_json = Column(Text, nullable=False)
    features_json = Column(Text, nullable=False)
    request_json = Column(Text, nullable=False)
    response_json = Column(Text, nullable=False)
    outcome_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return (
            f"<ScoreAuditRecord(lead_id={self.lead_id}, campaign_id={self.campaign_id}, "
            f"approval_score={self.approval_score})>"
        )
