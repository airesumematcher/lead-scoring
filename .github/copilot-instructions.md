<!-- Lead Scoring System - Workspace Instructions -->

# Lead Scoring System (B2B ABM with ACE Framework)

## Project Setup Checklist

- [x] **Clarify Project Requirements** — Completed
  - Python machine learning project for B2B lead scoring
  - ACE framework (Accuracy | Client Fit | Engagement)
  - Feature engineering, ML pipeline, REST API, explainability layer

- [x] **Scaffold the Project** — Completed
  - Created modular structure: features (accuracy/client_fit/engagement/derived), models, config, api, explainability
  - Added sample data, test script, configuration system
  - All Pydantic models and feature extractors in place

- [x] **Customize the Project** — Completed (Steps 1-5 Complete, 90% Done)
  - ✅ Step 1: Feature extraction modules for all ACE pillars
  - ✅ Step 2: Scoring architecture (Layer 1 gates + Layer 2 composite)
  - ✅ Step 3: Explainability layer (narratives + feature importance)
  - ✅ Step 4: REST API (FastAPI with /score and /score-batch endpoints)
  - ✅ Step 5: Feedback Loop (drift detection, retraining triggers, guardrails)
  - ⏳ Step 6-7: Tests, deployment

- [ ] **Install Required Extensions** — Skipped (Python project, no special extensions needed)

- [x] **Compile the Project** — Completed
  - ✅ Dependencies installed (pydantic, pyyaml, email-validator, fastapi, uvicorn, requests)
  - ✅ Feature extraction tested
  - ✅ End-to-end scoring tested
  - ✅ Explainability demo tested
  - ✅ API handlers tested (unit tests)
  - ✅ HTTP endpoints tested (integration tests)

- [x] **Create and Run Task** — Completed
  - API test scripts created
  - FastAPI server startup documented

- [ ] **Launch the Project** — In Progress
  - ✅ FastAPI server running on port 8001
  - ✅ Swagger docs available at /docs
  - ⏳ Production deployment configuration pending

- [x] **Ensure Documentation is Complete** — In Progress
  - README.md updated with status and API endpoints
  - Comprehensive docstrings in source code
  - Session memory updated with Steps 1-4 summary
  - API documentation auto-generated via Swagger UI

## Step 1: Feature Engineering — ✅ COMPLETE

**Deliverables:**
1. **Data Models** (Pydantic)
   - LeadInput: Complete input schema
   - AccuracyFeatures: 13 accuracy features + subscore
   - ClientFitFeatures: 9 fit features + subscore
   - EngagementFeatures: 11 engagement features + missing data handling
   - DerivedFeatures: Cross-pillar synergy, balance, decay, confidence, violations
   - ExtractedFeatures: Feature bundle output

2. **Accuracy Pillar Module** (`features/accuracy.py`)
   - Email/phone validation
   - Domain credibility scoring
   - Job title seniority parsing [1-5]
   - Hard gate: email_valid OR delivery_success = False → accuracy ≤ 40
   - Subscore calculation: email (20) + delivery (15) + company (20) + latency (15) + seniority (15) + duplicates (15)

3. **Client Fit Pillar Module** (`features/client_fit.py`)
   - Industry matching: exact (25) / related (15) / no match (0)
   - Company size band mapping (0-25 pts)
   - Revenue band mapping (0-20 pts)
   - Geography matching (0-20 pts)
   - Job title persona matching (0-25 pts)
   - TAL match boost +20 pts
   - Subscore: sum of all weighted components

4. **Engagement Pillar Module** (`features/engagement.py`)
   - Recency calculation (days since last event)
   - Sequence depth (distinct event types)
   - Email opens, asset clicks, asset downloads
   - Time decay: score * exp(-0.1 * days)
   - Missing engagement handling: flag = True → floor at 40 (no penalty)
   - Subscore: time-decay score + asset stage alignment + domain intent

5. **Derived Features Module** (`features/derived.py`)
   - ACE balance score (StdDev of A, C, E)
   - Fit-Intent synergy: (CF * E) / 100
   - Freshness decay conditionals: slow (0.02) if high fit+intent, fast (0.05) else
   - Confidence signal count (13 total possible)
   - ICP violation count (>2 → max score 50)

6. **Feature Extractor Orchestrator** (`features/extractor.py`)
   - Single entry point: `extract_all_features(lead: LeadInput) → ExtractedFeatures`
   - Sequence: Accuracy → ClientFit → Engagement → Derived

7. **Configuration System** (`config.py` + `scoring_config.yaml`)
   - Load/parse YAML config
   - ACE weights by program type (nurture/outbound/ABM/event)
   - Tunable parameters: grade boundaries, time decay rates, freshness thresholds, confidence bands
   - Sensible defaults if YAML not found

8. **Sample Data** (`data/sample_leads.py`)
   - 4 synthetic leads covering: high-fit, medium-fit, no-engagement, bad-data scenarios
   - Ready for baseline testing and model training

9. **Utility Module** (`utils.py`)
   - Grade mapping, confidence determination, freshness classification
   - Feature hashing for audit trail

10. **Test/Demo Script** (`test_feature_extraction.py`)
    - Executable: loads 4 sample leads, extracts features, prints results
    - Demonstrates all components working together

## Step 2: Scoring Architecture (Next)

**Deliverables needed:**
1. Layer 1: Rules-based accuracy gate (hard pass/fail)
2. Layer 2: ML scoring engine with LightGBM
3. Composite score calculation with ACE weights
4. Time decay and freshness multipliers
5. Score → Grade → Confidence mapping
6. Score output schema validation

**Expected structure:**
- `scoring/layer1_gate.py` — Accuracy hard gates
- `scoring/layer2_scorer.py` — LightGBM + weighted composite
- `scoring/score_output.py` — LeadScore object assembly

## Project Conventions

**Code Style:**
- Type hints on all functions
- Docstrings for public functions
- Pure functions (no side effects where possible)
- Modular: each pillar isolated, easy to test

**Testing:**
- Unit tests per module
- Integration tests for full pipeline
- Use pytest framework

**Configuration:**
- YAML for all tunable parameters
- Code defaults shipped in Python module
- Environment variables for secrets (e.g., API keys)

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Extract features from samples
python test_feature_extraction.py

# Run unit tests (when available)
pytest tests/ -v

# Run specific test
pytest tests/test_accuracy.py -v --cov=src/lead_scoring/features
```

## File Locations

- **Source Code:** `/tmp/lead-scoring/src/lead_scoring/`
- **Configuration:** `/tmp/lead-scoring/config/scoring_config.yaml`
- **Sample Data:** `/tmp/lead-scoring/data/sample_leads.py`
- **Tests:** `/tmp/lead-scoring/tests/`

## Next Steps

1. ✅ Step 1: Feature Engineering — Complete
2. ⏳ Step 2: Scoring Architecture — Ready to start
3. ⏳ Step 3: Model Training & Selection
4. ⏳ Step 4: Pipeline Influence Proxy
5. ⏳ Step 5: Lead Prioritization Logic
6. ⏳ Step 6: Explainability Layer
7. ⏳ Step 7: Feedback Loop Design
8. ⏳ Step 8: REST API & Output Schema
9. ⏳ Step 9: Validation & Success Metrics
