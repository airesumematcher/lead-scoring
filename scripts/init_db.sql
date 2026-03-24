-- PostgreSQL Database Initialization Script for Lead Scoring System
-- This script creates the database schema and initial configuration

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schema
CREATE SCHEMA IF NOT EXISTS lead_scoring;
SET search_path TO lead_scoring, public;

-- Create leads table
CREATE TABLE IF NOT EXISTS leads (
    id BIGSERIAL PRIMARY KEY,
    lead_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    title VARCHAR(255),
    company_name VARCHAR(255),
    company_domain VARCHAR(255),
    industry VARCHAR(255),
    campaign_id VARCHAR(255),
    source_partner VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT leads_email_check CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$' OR email IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_leads_lead_id ON leads(lead_id);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);
CREATE INDEX IF NOT EXISTS idx_leads_campaign_id ON leads(campaign_id);

-- Create scores table
CREATE TABLE IF NOT EXISTS scores (
    id BIGSERIAL PRIMARY KEY,
    lead_id VARCHAR(255) NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    score DECIMAL(5, 2),
    grade VARCHAR(1),
    confidence VARCHAR(50),
    accuracy_score DECIMAL(5, 2),
    client_fit_score DECIMAL(5, 2),
    engagement_score DECIMAL(5, 2),
    freshness_factor DECIMAL(3, 2),
    action VARCHAR(50),
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT scores_score_range CHECK (score >= 0 AND score <= 100),
    CONSTRAINT scores_grade_check CHECK (grade IN ('A', 'B', 'C', 'D', 'F'))
);

CREATE INDEX IF NOT EXISTS idx_scores_lead_id ON scores(lead_id);
CREATE INDEX IF NOT EXISTS idx_scores_created_at ON scores(created_at);
CREATE INDEX IF NOT EXISTS idx_scores_score ON scores(score);

-- Create feedback table
CREATE TABLE IF NOT EXISTS feedback (
    id BIGSERIAL PRIMARY KEY,
    lead_id VARCHAR(255) NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    outcome VARCHAR(20),
    reason VARCHAR(255),
    provided_score DECIMAL(5, 2),
    actual_score DECIMAL(5, 2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT feedback_outcome_check CHECK (outcome IN ('accepted', 'rejected', 'neutral'))
);

CREATE INDEX IF NOT EXISTS idx_feedback_lead_id ON feedback(lead_id);
CREATE INDEX IF NOT EXISTS idx_feedback_outcome ON feedback(outcome);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at);

-- Create audit_logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    operation VARCHAR(50),
    lead_id VARCHAR(255),
    status VARCHAR(20),
    error_message TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT audit_logs_status_check CHECK (status IN ('success', 'error', 'pending'))
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_lead_id ON audit_logs(lead_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_operation ON audit_logs(operation);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

-- Create batch_jobs table
CREATE TABLE IF NOT EXISTS batch_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_name VARCHAR(255),
    status VARCHAR(20),
    total_leads INTEGER,
    successful_leads INTEGER,
    failed_leads INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    CONSTRAINT batch_jobs_status_check CHECK (status IN ('pending', 'running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_started_at ON batch_jobs(started_at);

-- Create model_weights table for storing ACE weights
CREATE TABLE IF NOT EXISTS model_weights (
    id BIGSERIAL PRIMARY KEY,
    program_type VARCHAR(50),
    accuracy_weight DECIMAL(3, 2),
    client_fit_weight DECIMAL(3, 2),
    engagement_weight DECIMAL(3, 2),
    version INTEGER,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT model_weights_unique UNIQUE(program_type, version)
);

CREATE INDEX IF NOT EXISTS idx_model_weights_active ON model_weights(active);

-- Insert default weights
INSERT INTO model_weights (program_type, accuracy_weight, client_fit_weight, engagement_weight, version, active)
VALUES
    ('enterprise', 0.35, 0.40, 0.25, 1, TRUE),
    ('mid-market', 0.35, 0.40, 0.25, 1, TRUE),
    ('smb', 0.35, 0.40, 0.25, 1, TRUE),
    ('startup', 0.35, 0.40, 0.25, 1, TRUE)
ON CONFLICT (program_type, version) DO NOTHING;

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_leads_updated_at BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_model_weights_updated_at BEFORE UPDATE ON model_weights
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for score statistics
CREATE OR REPLACE VIEW lead_scoring.score_statistics AS
SELECT
    DATE(created_at) as date,
    COUNT(*) as total_scores,
    ROUND(AVG(score)::numeric, 2) as avg_score,
    MIN(score) as min_score,
    MAX(score) as max_score,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY score) as median_score,
    COUNT(CASE WHEN grade = 'A' THEN 1 END) as grade_a,
    COUNT(CASE WHEN grade = 'B' THEN 1 END) as grade_b,
    COUNT(CASE WHEN grade = 'C' THEN 1 END) as grade_c,
    COUNT(CASE WHEN grade = 'D' THEN 1 END) as grade_d,
    COUNT(CASE WHEN grade = 'F' THEN 1 END) as grade_f
FROM scores
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Create view for feedback analysis
CREATE OR REPLACE VIEW lead_scoring.feedback_analysis AS
SELECT
    DATE(f.created_at) as date,
    COUNT(*) as total_feedback,
    COUNT(CASE WHEN f.outcome = 'accepted' THEN 1 END) as accepted,
    COUNT(CASE WHEN f.outcome = 'rejected' THEN 1 END) as rejected,
    COUNT(CASE WHEN f.outcome = 'neutral' THEN 1 END) as neutral,
    ROUND(
        100.0 * COUNT(CASE WHEN f.outcome = 'accepted' THEN 1 END) / COUNT(*)
    , 2) as acceptance_rate,
    ROUND(AVG(COALESCE(f.actual_score - f.provided_score, 0))::numeric, 2) as avg_score_diff
FROM feedback f
GROUP BY DATE(f.created_at)
ORDER BY date DESC;

-- Grant permissions to application user
GRANT USAGE ON SCHEMA lead_scoring TO lead_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA lead_scoring TO lead_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA lead_scoring TO lead_user;
GRANT SELECT ON ALL VIEWS IN SCHEMA lead_scoring TO lead_user;

-- Create connection info comment
COMMENT ON DATABASE lead_scoring_db IS 'B2B ABM Lead Scoring System Database';
