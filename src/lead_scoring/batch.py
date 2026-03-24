"""
Batch processing pipeline for lead scoring.
Handles bulk lead scoring with progress tracking and error handling.
"""

import logging
from typing import List, Dict, Tuple
from datetime import datetime
from lead_scoring.models import LeadInput, LeadScore
from lead_scoring.config import load_config
from lead_scoring.scoring.scorer import score_lead
from lead_scoring.database.connection import DatabaseManager, get_session
from lead_scoring.database.models import BatchJob, Feedback

logger = logging.getLogger(__name__)


class BatchScoringPipeline:
    """Pipeline for batch processing leads."""
    
    def __init__(self, batch_size: int = 100):
        """
        Initialize batch pipeline.
        
        Args:
            batch_size: Number of leads to process before committing
        """
        self.batch_size = batch_size
        self.config = load_config()
        self.db_manager = DatabaseManager(get_session())
        self.stats = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "errors": []
        }
    
    def score_batch(self, leads: List[LeadInput], job_name: str = "batch_scoring") -> BatchJob:
        """
        Score a batch of leads.
        
        Args:
            leads: List of LeadInput objects
            job_name: Name for batch job tracking
            
        Returns:
            Completed BatchJob with results
        """
        # Initialize batch job
        job = self.db_manager.start_batch_job(job_name)
        self.stats["total"] = len(leads)
        
        logger.info(f"Starting batch job {job.id}: {job_name} with {len(leads)} leads")
        
        try:
            # Process leads in chunks
            for i in range(0, len(leads), self.batch_size):
                chunk = leads[i:i + self.batch_size]
                self._process_chunk(chunk)
        
        except Exception as e:
            logger.error(f"Batch job {job.id} failed: {str(e)}")
            job = self.db_manager.complete_batch_job(
                job.id, 
                self.stats["successful"], 
                self.stats["failed"]
            )
            job.error_message = str(e)
            self.db_manager.session.commit()
            raise
        
        # Complete the job
        job = self.db_manager.complete_batch_job(
            job.id,
            self.stats["successful"],
            self.stats["failed"]
        )
        
        logger.info(
            f"Batch job {job.id} completed: "
            f"{self.stats['successful']} successful, {self.stats['failed']} failed"
        )
        
        return job
    
    def _process_chunk(self, leads: List[LeadInput]):
        """Process a chunk of leads."""
        for lead in leads:
            try:
                # Score the lead
                score = score_lead(lead, self.config)
                
                # Store in database
                self._store_score(lead, score)
                
                self.stats["successful"] += 1
                logger.debug(f"Scored lead {lead.lead_id}: {score.score}")
                
            except Exception as e:
                self.stats["failed"] += 1
                error_msg = f"Failed to score {lead.lead_id}: {str(e)}"
                self.stats["errors"].append(error_msg)
                logger.error(error_msg)
                
                # Log audit trail
                self.db_manager.add_audit_log(
                    operation="score",
                    lead_id=lead.lead_id,
                    status="error",
                    error_message=str(e)
                )
    
    def _store_score(self, lead: LeadInput, score: LeadScore):
        """Store score in database."""
        # Ensure lead exists
        db_lead = self.db_manager.get_lead(lead.lead_id)
        if not db_lead:
            db_lead = self.db_manager.add_lead(
                lead_id=lead.lead_id,
                email=lead.contact.email,
                first_name=lead.contact.first_name,
                last_name=lead.contact.last_name,
                job_title=lead.contact.job_title,
                company_name=lead.company.company_name if lead.company else None,
                domain=lead.company.domain if lead.company else None,
                industry=lead.company.industry if lead.company else None,
                campaign_id=lead.campaign.campaign_id if lead.campaign else None,
                source_partner=lead.source_partner,
            )
        
        # Store score
        self.db_manager.add_score(
            lead_id=lead.lead_id,
            score=score.score,
            grade=score.grade.value,
            confidence=score.confidence.value,
            accuracy_subscore=score.ace_breakdown.accuracy if score.ace_breakdown else None,
            freshness_status=score.freshness.status if score.freshness else None,
            recommended_action=score.narrative.recommended_action.value if score.narrative else None,
            summary=score.narrative.summary if score.narrative else None,
        )
        
        # Log audit
        self.db_manager.add_audit_log(
            operation="score",
            lead_id=lead.lead_id,
            status="success",
            details=f"Score: {score.score}, Grade: {score.grade.value}"
        )
    
    def get_stats(self) -> Dict:
        """Get processing statistics."""
        return self.stats.copy()
    
    def close(self):
        """Close database connection."""
        self.db_manager.close()


class BatchRetrainingPipeline:
    """Pipeline for retraining based on feedback."""
    
    def __init__(self):
        """Initialize retraining pipeline."""
        self.db_manager = DatabaseManager(get_session())
        self.logger = logging.getLogger(__name__)
    
    def get_feedback_summary(self) -> Dict:
        """Get summary of feedback."""
        from sqlalchemy import func
        
        session = self.db_manager.session
        
        # Count feedback by outcome
        feedback_count = session.query(
            Feedback.outcome,
            func.count(Feedback.id)
        ).group_by(Feedback.outcome).all()
        
        # Calculate acceptance rate
        feedback_list = session.query(Feedback).all()
        if not feedback_list:
            return {"total": 0, "outcomes": {}}
        
        total = len(feedback_list)
        outcomes = {outcome: count for outcome, count in feedback_count}
        
        acceptance_rate = outcomes.get("accepted", 0) / total if total > 0 else 0
        
        return {
            "total_feedback": total,
            "outcomes": outcomes,
            "acceptance_rate": acceptance_rate,
            "timestamp": datetime.utcnow()
        }
    
    def close(self):
        """Close database connection."""
        self.db_manager.close()
