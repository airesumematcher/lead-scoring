"""
Tests for Step 7: Batch Pipeline & Data Integration.
Tests database models, batch processing, Pandas operations, and monitoring.
"""

import pytest
import tempfile
import os
from lead_scoring.database.connection import DatabaseConfig, DatabaseManager, init_db
from lead_scoring.database.models import Lead, Score, Feedback, AuditLog, BatchJob
from lead_scoring.batch import BatchScoringPipeline
from lead_scoring.pandas_ops import PandasBulkOperations
from lead_scoring.monitoring import SystemMetrics, AlertingSystem, setup_logging


class TestDatabaseConnection:
    """Test database connection and setup."""
    
    def test_database_config_creation(self):
        """Test database config initialization."""
        # Create in-memory SQLite for testing
        config = DatabaseConfig("sqlite:///:memory:")
        
        assert config is not None
        assert config.db_url == "sqlite:///:memory:"
    
    def test_create_tables(self):
        """Test table creation."""
        config = DatabaseConfig("sqlite:///:memory:")
        config.create_tables()
        
        # Tables should exist (this would fail if not)
        assert config.engine is not None
    
    def test_get_session(self):
        """Test session creation."""
        config = DatabaseConfig("sqlite:///:memory:")
        session = config.get_session()
        
        assert session is not None
    
    def test_database_manager_initialization(self):
        """Test DatabaseManager creation."""
        config = DatabaseConfig("sqlite:///:memory:")
        config.create_tables()
        
        db = DatabaseManager(config.get_session())
        
        assert db is not None
        assert db.session is not None


class TestDatabaseModels:
    """Test database ORM models."""
    
    @pytest.fixture
    def db_manager(self):
        """Create test database manager."""
        config = DatabaseConfig("sqlite:///:memory:")
        config.create_tables()
        manager = DatabaseManager(config.get_session())
        yield manager
        manager.close()
    
    def test_add_lead(self, db_manager):
        """Test adding a lead to database."""
        lead = db_manager.add_lead(
            lead_id="TEST-001",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            company_name="Acme Corp"
        )
        
        assert lead.lead_id == "TEST-001"
        assert lead.email == "test@example.com"
    
    def test_get_lead(self, db_manager):
        """Test retrieving a lead."""
        # Add a lead first
        db_manager.add_lead(
            lead_id="TEST-002",
            email="test2@example.com",
            first_name="Jane",
            last_name="Smith",
            company_name="Tech Inc"
        )
        
        # Retrieve it
        lead = db_manager.get_lead("TEST-002")
        
        assert lead is not None
        assert lead.lead_id == "TEST-002"
    
    def test_add_score(self, db_manager):
        """Test adding a score."""
        # Add lead first
        db_manager.add_lead(
            lead_id="TEST-003",
            email="test3@example.com",
            first_name="Bob",
            last_name="Johnson",
            company_name="Start Inc"
        )
        
        # Add score
        score = db_manager.add_score(
            lead_id="TEST-003",
            score=75.5,
            grade="B",
            confidence="High"
        )
        
        assert score.lead_id == "TEST-003"
        assert score.score == 75.5
        assert score.grade == "B"
    
    def test_add_feedback(self, db_manager):
        """Test adding feedback."""
        # Add lead first
        db_manager.add_lead(
            lead_id="TEST-004",
            email="test4@example.com",
            first_name="Alice",
            last_name="Brown",
            company_name="Growth Co"
        )
        
        # Add feedback
        feedback = db_manager.add_feedback(
            lead_id="TEST-004",
            outcome="accepted",
            reason="excellent_fit",
            provided_score=80.0
        )
        
        assert feedback.lead_id == "TEST-004"
        assert feedback.outcome == "accepted"
    
    def test_add_audit_log(self, db_manager):
        """Test adding audit log."""
        log = db_manager.add_audit_log(
            operation="score",
            lead_id="TEST-005",
            status="success",
            details="Scored successfully"
        )
        
        assert log.operation == "score"
        assert log.status == "success"
    
    def test_batch_job_tracking(self, db_manager):
        """Test batch job creation and completion."""
        # Start job
        job = db_manager.start_batch_job("test_batch")
        
        assert job.status == "running"
        assert job.job_name == "test_batch"
        
        # Complete job
        completed_job = db_manager.complete_batch_job(job.id, 10, 2)
        
        assert completed_job.status == "completed"
        assert completed_job.successful_leads == 10
        assert completed_job.failed_leads == 2


class TestBatchPipeline:
    """Test batch scoring pipeline."""
    
    @pytest.fixture
    def batch_pipeline(self):
        """Create batch pipeline with test database."""
        from lead_scoring.database.connection import DatabaseConfig
        
        config = DatabaseConfig("sqlite:///:memory:")
        config.create_tables()
        
        # Monkey-patch to use test database
        import lead_scoring.batch as batch_module
        original_get_session = batch_module.get_session
        original_DatabaseManager = batch_module.DatabaseManager
        
        def mock_get_session():
            return config.get_session()
        
        batch_module.get_session = mock_get_session
        
        pipeline = BatchScoringPipeline()
        
        yield pipeline
        
        # Restore
        batch_module.get_session = original_get_session
        pipeline.close()
    
    def test_batch_pipeline_initialization(self, batch_pipeline):
        """Test batch pipeline setup."""
        assert batch_pipeline.batch_size == 100
        assert batch_pipeline.config is not None
    
    def test_batch_pipeline_stats(self, batch_pipeline):
        """Test batch pipeline statistics tracking."""
        stats = batch_pipeline.get_stats()
        
        assert stats["total"] == 0
        assert stats["successful"] == 0
        assert stats["failed"] == 0


class TestLogging:
    """Test logging setup."""
    
    def test_setup_logging(self):
        """Test logging configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = setup_logging(tmpdir, "INFO")
            
            assert logger is not None
            assert logger.name == "lead_scoring"
    
    def test_system_metrics(self):
        """Test system metrics tracking."""
        from lead_scoring.database.connection import DatabaseConfig
        
        config = DatabaseConfig("sqlite:///:memory:")
        config.create_tables()
        
        db = DatabaseManager(config.get_session())
        
        # Add some test data
        db.add_lead(
            lead_id="METRIC-001",
            email="metric@example.com",
            first_name="Test",
            last_name="User",
            company_name="Metric Corp"
        )
        
        db.add_audit_log(
            operation="score",
            lead_id="METRIC-001",
            status="success",
            details="Test"
        )
        
        # Note: Actual metrics would need populated database
        # This just tests the interface exists
        metrics = SystemMetrics()
        assert metrics is not None
        metrics.close()
        db.close()


class TestMonitoring:
    """Test monitoring and alerting."""
    
    def test_alerting_system_creation(self):
        """Test alert system initialization."""
        # Initialize the database first
        init_db()
        
        alerts = AlertingSystem()
        
        assert alerts is not None
        assert alerts.logger is not None
        
        alerts.close()
    
    def test_error_rate_check(self):
        """Test error rate monitoring."""
        # Initialize the database first
        init_db()
        
        # Create AlertingSystem (it will use the initialized database)
        alerts = AlertingSystem()
        
        # Result should be valid (empty database will have 0% error rate)
        result = alerts.check_error_rate(threshold=0.5)
        
        assert "alert" in result
        assert "error_rate" in result
        
        alerts.close()


class TestDatabaseIntegration:
    """Integration tests for database."""
    
    def test_full_workflow(self):
        """Test complete workflow from lead to score."""
        config = DatabaseConfig("sqlite:///:memory:")
        config.create_tables()
        
        db = DatabaseManager(config.get_session())
        
        # Add lead
        lead = db.add_lead(
            lead_id="WORKFLOW-001",
            email="workflow@example.com",
            first_name="Integration",
            last_name="Test",
            company_name="Integration Corp"
        )
        
        # Add score
        score = db.add_score(
            lead_id="WORKFLOW-001",
            score=65.0,
            grade="C"
        )
        
        # Add feedback
        feedback = db.add_feedback(
            lead_id="WORKFLOW-001",
            outcome="neutral"
        )
        
        # Add audit log
        audit = db.add_audit_log(
            operation="score",
            lead_id="WORKFLOW-001",
            status="success"
        )
        
        # Verify all data
        retrieved_lead = db.get_lead("WORKFLOW-001")
        assert retrieved_lead is not None
        
        scores = db.get_scores_for_lead("WORKFLOW-001")
        assert len(scores) == 1
        
        db.close()


class TestDatabasePersistence:
    """Test database persistence."""
    
    def test_file_based_database(self):
        """Test file-based SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            config = DatabaseConfig(f"sqlite:///{db_path}")
            config.create_tables()
            
            # Add data
            db = DatabaseManager(config.get_session())
            db.add_lead(
                lead_id="FILE-001",
                email="file@example.com",
                first_name="File",
                last_name="Test",
                company_name="File Corp"
            )
            db.close()
            
            # Verify file exists
            assert os.path.exists(db_path)
