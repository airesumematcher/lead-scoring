"""
Pandas integration for lead scoring.
Handles bulk import/export and data analysis.
"""

import pandas as pd
import logging
from typing import List, Dict, Tuple
from pathlib import Path
from lead_scoring.models import LeadInput, ContactFields, CompanyFields, CampaignFields, EngagementEvent, EngagementType, ProgramType
from lead_scoring.database.connection import DatabaseManager, get_session
from lead_scoring.database.models import Lead, Score, Feedback

logger = logging.getLogger(__name__)


class PandasBulkOperations:
    """Bulk operations using Pandas."""
    
    def __init__(self):
        """Initialize bulk operations."""
        self.db_manager = DatabaseManager(get_session())
    
    def import_leads_from_csv(self, csv_path: str) -> Tuple[int, List[str]]:
        """
        Import leads from CSV file.
        
        Args:
            csv_path: Path to CSV file with lead data
            
        Returns:
            Tuple of (successful_imports, error_messages)
        """
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(df)} leads from {csv_path}")
            
            successful = 0
            errors = []
            
            for idx, row in df.iterrows():
                try:
                    lead = self.db_manager.add_lead(
                        lead_id=str(row.get('lead_id', f'IMPORT-{idx}')),
                        email=row.get('email'),
                        first_name=row.get('first_name'),
                        last_name=row.get('last_name'),
                        company_name=row.get('company_name'),
                        job_title=row.get('job_title'),
                        domain=row.get('domain'),
                        industry=row.get('industry'),
                        company_size=row.get('company_size'),
                        campaign_id=row.get('campaign_id'),
                        source_partner=row.get('source_partner', 'bulk_import'),
                    )
                    successful += 1
                except Exception as e:
                    errors.append(f"Row {idx}: {str(e)}")
            
            logger.info(f"Imported {successful}/{len(df)} leads successfully")
            return successful, errors
            
        except Exception as e:
            logger.error(f"Failed to import from CSV: {str(e)}")
            raise
    
    def export_scores_to_csv(self, output_path: str = None) -> pd.DataFrame:
        """
        Export all lead scores to CSV.
        
        Args:
            output_path: Path to save CSV (optional)
            
        Returns:
            DataFrame with all scores
        """
        session = self.db_manager.session
        
        # Query all scores with associated lead data
        scores = session.query(Score).all()
        
        data = []
        for score in scores:
            data.append({
                'lead_id': score.lead_id,
                'email': score.lead.email if score.lead else None,
                'company': score.lead.company_name if score.lead else None,
                'score': score.score,
                'grade': score.grade,
                'confidence': score.confidence,
                'created_at': score.created_at,
            })
        
        df = pd.DataFrame(data)
        
        if output_path:
            df.to_csv(output_path, index=False)
            logger.info(f"Exported {len(df)} scores to {output_path}")
        
        return df
    
    def get_score_statistics(self) -> Dict:
        """Get statistical summary of scores."""
        session = self.db_manager.session
        
        scores = session.query(Score).all()
        
        if not scores:
            return {"total": 0}
        
        df = pd.DataFrame([
            {'score': s.score, 'grade': s.grade}
            for s in scores
        ])
        
        return {
            "total_scores": len(df),
            "mean_score": df['score'].mean(),
            "median_score": df['score'].median(),
            "std_score": df['score'].std(),
            "min_score": df['score'].min(),
            "max_score": df['score'].max(),
            "grade_distribution": df['grade'].value_counts().to_dict(),
        }
    
    def get_feedback_analysis(self) -> Dict:
        """Analyze feedback data."""
        session = self.db_manager.session
        
        feedback = session.query(Feedback).all()
        
        if not feedback:
            return {"total_feedback": 0}
        
        df = pd.DataFrame([
            {
                'outcome': f.outcome,
                'provided_score': f.provided_score,
                'actual_score': f.actual_score,
                'submitted_at': f.submitted_at,
            }
            for f in feedback
        ])
        
        # Calculate score differences
        df['score_diff'] = df['provided_score'] - df['actual_score']
        
        return {
            "total_feedback": len(df),
            "outcomes": df['outcome'].value_counts().to_dict(),
            "acceptance_rate": (df['outcome'] == 'accepted').sum() / len(df) if len(df) > 0 else 0,
            "avg_score_diff": df['score_diff'].mean() if not df['score_diff'].isna().all() else 0,
            "feedback_by_date": df.groupby(df['submitted_at'].dt.date).size().to_dict(),
        }
    
    def get_leads_dataframe(self) -> pd.DataFrame:
        """Get all leads as DataFrame."""
        session = self.db_manager.session
        
        leads = session.query(Lead).all()
        
        return pd.DataFrame([
            {
                'lead_id': l.lead_id,
                'email': l.email,
                'company': l.company_name,
                'domain': l.domain,
                'industry': l.industry,
                'company_size': l.company_size,
                'campaign_id': l.campaign_id,
                'created_at': l.created_at,
            }
            for l in leads
        ])
    
    def close(self):
        """Close database connection."""
        self.db_manager.close()
