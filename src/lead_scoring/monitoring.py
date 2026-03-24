"""
Monitoring and logging for lead scoring system.
Provides metrics, alerts, and audit trail tracking.
"""

import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from lead_scoring.database.connection import DatabaseManager, get_session
from lead_scoring.database.models import AuditLog


# Configure logging
def setup_logging(log_dir: str = None, level: str = "INFO"):
    """
    Setup logging for the system.
    
    Args:
        log_dir: Directory for log files
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    if log_dir is None:
        log_dir = Path(__file__).parent.parent.parent / "logs"
    
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger("lead_scoring")
    root_logger.setLevel(getattr(logging, level))
    
    # File handler
    log_file = log_path / "lead_scoring.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(getattr(logging, level))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, "INFO"))
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return root_logger


class SystemMetrics:
    """Track system metrics."""
    
    def __init__(self):
        """Initialize metrics tracker."""
        self.db_manager = DatabaseManager(get_session())
        self.logger = logging.getLogger(__name__)
    
    def get_daily_metrics(self) -> Dict:
        """Get daily metrics."""
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        session = self.db_manager.session
        
        # Get metrics for last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # Leads processed
        leads_processed = session.query(
            func.count(AuditLog.id)
        ).filter(
            AuditLog.operation == "score",
            AuditLog.created_at >= yesterday
        ).scalar() or 0
        
        # Processing errors
        errors = session.query(
            func.count(AuditLog.id)
        ).filter(
            AuditLog.operation == "score",
            AuditLog.status == "error",
            AuditLog.created_at >= yesterday
        ).scalar() or 0
        
        success_rate = (leads_processed - errors) / leads_processed if leads_processed > 0 else 0
        
        return {
            "date": datetime.utcnow().date().isoformat(),
            "leads_processed": leads_processed,
            "errors": errors,
            "success_rate": success_rate,
        }
    
    def get_overall_metrics(self) -> Dict:
        """Get overall system metrics."""
        from sqlalchemy import func
        from lead_scoring.database.models import Lead, Score, Feedback
        
        session = self.db_manager.session
        
        total_leads = session.query(func.count(Lead.id)).scalar() or 0
        total_scores = session.query(func.count(Score.id)).scalar() or 0
        total_feedback = session.query(func.count(Feedback.id)).scalar() or 0
        
        # Score distribution
        scores = session.query(Score).all()
        
        return {
            "total_leads": total_leads,
            "total_scores": total_scores,
            "total_feedback": total_feedback,
            "avg_score": sum(s.score for s in scores) / len(scores) if scores else 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def get_audit_trail(self, lead_id: str = None, days: int = 30) -> List[Dict]:
        """
        Get audit trail.
        
        Args:
            lead_id: Optional filter by lead_id
            days: Number of days to look back
            
        Returns:
            List of audit log entries
        """
        from datetime import timedelta
        
        session = self.db_manager.session
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = session.query(AuditLog).filter(AuditLog.created_at >= cutoff)
        
        if lead_id:
            query = query.filter(AuditLog.lead_id == lead_id)
        
        logs = query.order_by(AuditLog.created_at.desc()).all()
        
        return [
            {
                "id": log.id,
                "operation": log.operation,
                "lead_id": log.lead_id,
                "status": log.status,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    
    def export_metrics(self, output_path: str = None) -> str:
        """Export metrics as JSON."""
        metrics = {
            "daily": self.get_daily_metrics(),
            "overall": self.get_overall_metrics(),
        }
        
        json_str = json.dumps(metrics, indent=2)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(json_str)
        
        return json_str
    
    def close(self):
        """Close database connection."""
        self.db_manager.close()


class AlertingSystem:
    """Alert system for anomalies."""
    
    def __init__(self):
        """Initialize alerting system."""
        self.logger = logging.getLogger(__name__)
        self.db_manager = DatabaseManager(get_session())
    
    def check_error_rate(self, threshold: float = 0.1) -> Dict:
        """
        Check error rate.
        
        Args:
            threshold: Error rate threshold (0.0-1.0)
            
        Returns:
            Alert status
        """
        from sqlalchemy import func
        from datetime import timedelta
        
        session = self.db_manager.session
        
        # Last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        total = session.query(
            func.count(AuditLog.id)
        ).filter(
            AuditLog.created_at >= one_hour_ago
        ).scalar() or 0
        
        errors = session.query(
            func.count(AuditLog.id)
        ).filter(
            AuditLog.status == "error",
            AuditLog.created_at >= one_hour_ago
        ).scalar() or 0
        
        error_rate = errors / total if total > 0 else 0
        
        alert = error_rate > threshold
        
        if alert:
            self.logger.warning(
                f"High error rate detected: {error_rate:.2%} "
                f"({errors}/{total} errors in last hour)"
            )
        
        return {
            "alert": alert,
            "error_rate": error_rate,
            "errors": errors,
            "total": total,
        }
    
    def check_performance(self, target_avg_time: float = 1.0) -> Dict:
        """Check system performance."""
        metrics = SystemMetrics()
        daily = metrics.get_daily_metrics()
        
        return {
            "success_rate": daily["success_rate"],
            "performance_ok": daily["success_rate"] >= 0.95,
        }
    
    def close(self):
        """Close database connection."""
        self.db_manager.close()
