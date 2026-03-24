# Troubleshooting Guide - Lead Scoring System

Comprehensive troubleshooting guide for common issues, errors, and edge cases.

## Table of Contents

1. [Installation & Setup Issues](#installation--setup-issues)
2. [API Errors](#api-errors)
3. [Database Issues](#database-issues)
4. [Performance Problems](#performance-problems)
5. [Model & Scoring Issues](#model--scoring-issues)
6. [Deployment Issues](#deployment-issues)
7. [Integration Problems](#integration-problems)
8. [Error Code Reference](#error-code-reference)

---

## Installation & Setup Issues

### Problem: Python Module Not Found

**Error:**
```
ModuleNotFoundError: No module named 'lead_scoring'
```

**Solutions:**

1. **Check Python path:**
```bash
python -c "import sys; print(sys.path)"
cd /path/to/project
export PYTHONPATH="${PWD}:$PYTHONPATH"
```

2. **Install in development mode:**
```bash
pip install -e .
```

3. **Verify imports:**
```bash
python -c "from lead_scoring.features import accuracy_features; print('OK')"
```

---

### Problem: Database Connection Failed

**Error:**
```
psycopg2.OperationalError: could not connect to server: 
Connection refused. Is the server running locally?
```

**Checklist:**

```bash
# 1. PostgreSQL running?
postgresql -V
ps aux | grep postgres

# 2. localhost:5432 accessible?
nc -zv localhost 5432

# 3. Correct credentials?
psql -h localhost -U postgres -W
SHOW ALL;

# 4. Database exists?
psql -h localhost -U postgres -l | grep lead_scoring

# 5. Check .env file
cat .env | grep DATABASE_URL
```

**Fix:**

```bash
# If using local PostgreSQL
brew services start postgresql@15    # macOS
sudo systemctl start postgresql       # Linux
docker run -d -e POSTGRES_PASSWORD=... postgres:15

# If using Docker Compose
docker-compose up postgres

# Update .env with correct URL
DATABASE_URL=postgresql://postgres:password@localhost:5432/lead_scoring
```

---

### Problem: Missing Environment Variables

**Error:**
```
KeyError: 'DATABASE_URL'
pydantic_core._pydantic_core.ValidationError: 1 validation error
```

**Fix:**

```bash
# Copy template
cp .env.example .env

# Fill required fields
nano .env

# Verify all required vars present
python -c "
from dotenv import load_dotenv
import os
load_dotenv()
required = ['DATABASE_URL', 'API_KEY_SECRET', 'JWT_SECRET']
for var in required:
    print(f'{var}: {\"OK\" if os.getenv(var) else \"MISSING\"}')"
```

---

## API Errors

### 400 Bad Request

**Cause:** Invalid request parameters

**Example:**
```json
{
  "status": "error",
  "error_code": "INVALID_INPUT",
  "message": "Invalid email format: invalid-email",
  "details": {"field": "email", "expected": "valid email"}
}
```

**Fix:**
- Validate email format: `name@domain.com`
- Ensure all required fields present
- Check data types match schema
- See [API_REFERENCE.md](API_REFERENCE.md) for field specs

---

### 404 Not Found

**Cause:** Endpoint doesn't exist or resource not found

**Example:**
```
GET /scor  → 404 (typo in endpoint)
GET /feedback/INVALID-ID → 404 (lead doesn't exist)
```

**Fix:**

1. Check endpoint spelling:
```bash
# Valid endpoints:
/health
/score
/score-batch
/feedback
/retrain
/drift-status
/drift-settings
```

2. Verify resource exists:
```bash
# Check if lead exists in database
psql -h localhost -U postgres -d lead_scoring -c "
  SELECT * FROM leads WHERE lead_id = 'LEAD-001';"
```

---

### 422 Unprocessable Entity

**Cause:** Missing or invalid required fields

**Example:**
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Fix:**

Ensure all required fields in request:

```bash
# Required for /score:
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "L1",
    "email": "test@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "title": "VP Sales",
    "company_name": "ACME Corp"
  }'
```

---

### 429 Too Many Requests

**Cause:** Rate limiting exceeded

**Solution:**

1. Check rate limit headers:
```bash
curl -i http://localhost:8000/score | grep X-RateLimit
```

2. Increase rate limits (if self-hosted):
```python
# In config
RATE_LIMIT_PER_MINUTE = 2000  # Default: 1000
RATE_LIMIT_BURST = 200        # Default: 100
```

3. Implement retry logic:
```python
import time
import requests

max_retries = 3
retry_count = 0
while retry_count < max_retries:
    try:
        response = requests.post(...)
        if response.status_code != 429:
            break
        retry_count += 1
        wait_time = 2 ** retry_count
        print(f"Rate limited. Waiting {wait_time}s")
        time.sleep(wait_time)
    except Exception as e:
        print(f"Error: {e}")
        break
```

---

### 500 Internal Server Error

**Cause:** Server-side error (unexpected exception)

**Investigation:**

```bash
# Check API logs
curl http://localhost:8000/score 2>&1 | grep -i error

# Check application logs
docker logs api-container
kubectl logs deployment/api -n lead-scoring

# Check system logs
journalctl -u api.service -n 100
tail -f /var/log/api/error.log
```

**Common Root Causes:**

| Symptom | Check | Fix |
|---------|-------|-----|
| JSON decode error | Request body format | Use `application/json` header |
| Database connection lost | PostgreSQL status | Restart DB, check firewall |
| Model inference error | Model file exists | Restore backup model file |
| Memory allocation failed | Free memory | Increase pod memory limit |

---

## Database Issues

### Connection Pool Exhaustion

**Symptom:**
```
psycopg2.OperationalError: FATAL: too many connections
```

**Analysis:**

```bash
# Check current connections
psql -h localhost -U postgres -c "
  SELECT datname, count(*) 
  FROM pg_stat_activity 
  GROUP BY datname;"

# Identify long-running queries
psql -h localhost -U postgres -c "
  SELECT pid, usename, duration, query 
  FROM pg_stat_statements 
  WHERE query NOT LIKE '%pg_stat_statements%'
  ORDER BY duration DESC 
  LIMIT 10;"
```

**Solutions:**

1. **Increase pool size:**
```env
DATABASE_POOL_SIZE=50
DATABASE_POOL_MAX_OVERFLOW=20
```

2. **Kill idle connections:**
```sql
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' 
AND state_change < NOW() - INTERVAL '30 minutes';
```

3. **Add PgBouncer connection pooler:**
```ini
[databases]
lead_scoring = host=postgres port=5432 dbname=lead_scoring

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

---

### Slow Database Queries

**Identify slow queries:**

```sql
-- Enable query logging
ALTER SYSTEM SET log_min_duration_statement = 100;  -- Log queries >100ms
SELECT pg_reload_conf();

-- View logged slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
WHERE mean_time > 100 
ORDER BY mean_time DESC;
```

**Optimize indexes:**

```sql
-- Find missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY abs(correlation) DESC;

-- Create indexes on frequently filtered columns
CREATE INDEX idx_leads_email ON leads(email);
CREATE INDEX idx_scores_lead_id_created ON scores(lead_id, created_at);
CREATE INDEX idx_feedback_outcome ON feedback(outcome);

-- Check index size and usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

---

### Data Consistency Issues

**Check for orphaned records:**

```sql
-- Leads without scores
SELECT l.lead_id, l.email 
FROM leads l
LEFT JOIN scores s ON l.lead_id = s.lead_id
WHERE s.score_id IS NULL;

-- Feedback without corresponding scores
SELECT f.feedback_id, f.lead_id
FROM feedback f
LEFT JOIN leads l ON f.lead_id = l.lead_id
WHERE l.lead_id IS NULL;
```

**Fix inconsistencies:**

```sql
-- Remove orphaned feedback
DELETE FROM feedback 
WHERE lead_id NOT IN (SELECT lead_id FROM leads);

-- Reset sequences if needed
SELECT setval('leads_id_seq', (SELECT MAX(id) FROM leads));
```

---

## Performance Problems

### High API Latency

**Measure latency distribution:**

```bash
# Using curl with timing
curl -w "
  time_namelookup:  %{time_namelookup}\n
  time_connect:     %{time_connect}\n
  time_appconnect:  %{time_appconnect}\n
  time_pretransfer: %{time_pretransfer}\n
  time_redirect:    %{time_redirect}\n
  time_starttransfer: %{time_starttransfer}\n
  time_total:       %{time_total}\n" \
  -o /dev/null -s \
  http://localhost:8000/score \
  -X POST \
  -d '{"lead_id":"L1","email":"test@example.com",...}'
```

**Bottleneck Analysis:**

| Timing High | Likely Cause | Fix |
|-------------|--------------|-----|
| `time_connect` | Network latency | Check network, use local DB |
| `time_starttransfer` | Server processing | Profile code, optimize queries |
| `time_appconnect` | TLS overhead | Keep-alive connections, session resumption |

**Profiling:**

```python
# Add to API code
import cProfile
import pstats
from io import StringIO

pr = cProfile.Profile()
pr.enable()

# Your code here
score = score_lead(features)

pr.disable()
s = StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
ps.print_stats(10)
print(s.getvalue())
```

---

### High Memory Usage

**Monitor memory:**

```bash
# Real-time memory
watch -n 1 'ps aux | grep api | grep -v grep'

# Memory profiling
python -m memory_profiler main.py

# Check for leaks
pympler: python -m pdb to set breakpoints
```

**Common memory hogs:**

1. **Large DataFrames not freed:**
```python
# Bad
data = pd.read_csv('huge_file.csv')

# Good
with pd.read_csv('huge_file.csv', chunksize=1000) as reader:
    for chunk in reader:
        process(chunk)
del data
gc.collect()
```

2. **Circular references:**
```python
# Check for reference cycles
import gc
gc.set_debug(gc.DEBUG_SAVEALL)
gc.collect()
print(f"Garbage: {len(gc.garbage)} objects")
```

---

## Model & Scoring Issues

### Unexpected Score Values

**Diagnose:**

```bash
# Get detailed response
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{...}' | jq '.feature_importance'

# Check feature calculations
export DEBUG=true
python -c "
from lead_scoring.features import extract_features
features = extract_features(...)
print(features)
"
```

**Common issues:**

1. **Features out of range:**
```python
# Accuracy score should be 0-100
assert 0 <= accuracy_score <= 100, f"Invalid: {accuracy_score}"

# Engagement score normalized
assert 0 <= engagement_normalized <= 1, f"Invalid: {engagement_normalized}"
```

2. **Weight sum != 100%:**
```python
# These weights should sum to 1.0
weights = [0.35, 0.40, 0.25]
assert sum(weights) == 1.0, f"Weights sum to {sum(weights)}"
```

---

### Model Drift Not Detected

**Check drift settings:**

```bash
# Get current settings
curl http://localhost:8000/drift-status

# Expected output:
{
  "status": "warning|critical|ok",
  "drift_detected": true/false,
  "metrics": {
    "acceptance_rate": 0.58,
    "acceptance_rate_change": -0.12
  }
}
```

**Verify feedback collection:**

```sql
-- Check recent feedback count
SELECT outcome, COUNT(*) 
FROM feedback 
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY outcome;

-- Should see mix of accepted/rejected for drift detection to work
```

**Adjust thresholds if too sensitive:**

```bash
curl -X PUT http://localhost:8000/drift-settings \
  -H "Content-Type: application/json" \
  -d '{
    "acceptance_rate_threshold": 0.45,
    "confidence_threshold": 0.65,
    "min_feedback_for_retrain": 100
  }'
```

---

### Retraining Fails

**Check logs:**

```bash
# Get retrain job status
curl http://localhost:8000/retrain \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Monitor progress
kubectl logs -f deployment/api -n lead-scoring | grep -i retrain
```

**Common issues:**

1. **Insufficient feedback samples:**
```sql
SELECT COUNT(*) FROM feedback;
-- If < 50, retraining won't trigger
```

2. **Feature extraction errors:**
```python
# Verify feature extraction on feedback data
from lead_scoring.features import extract_features
features = extract_features(record)
# Should not raise exceptions
```

---

## Deployment Issues

### Pod CrashLoopBackOff

**Check pod status:**

```bash
kubectl describe pod -n lead-scoring <pod-name>
kubectl logs -n lead-scoring <pod-name>
```

**Common causes:**

| Cause | Check | Fix |
|-------|-------|-----|
| Health check failing | `readinessProbe` in logs | Ensure DB is reachable |
| Missing secret | `kubectl get secrets -n lead-scoring` | Create with `kubectl create secret` |
| Image not found | `docker pull myrepo/api:tag` | Verify image exists, credentials |
| Port conflict | `netstat -tulpn \| grep 8000` | Change port in deployment |

---

### Persistent Volume Issues

**Check volume status:**

```bash
kubectl get pvc -n lead-scoring
kubectl describe pvc -n lead-scoring postgres-pvc

# Check volume capacity
kubectl exec -it postgres-0 -n lead-scoring -- \
  df -h /var/lib/postgresql/data
```

**Expand volume:**

```bash
# Edit PVC
kubectl patch pvc postgres-pvc -n lead-scoring -p \
  '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'

# Verify expansion
kubectl get pvc -n lead-scoring
```

---

### Ingress Not Working

**Check ingress:**

```bash
kubectl describe ingress api-ingress -n lead-scoring
kubectl get ingress -n lead-scoring

# Check backend services
kubectl get service -n lead-scoring
kubectl describe service api -n lead-scoring
```

**Test directly:**

```bash
# Port forward
kubectl port-forward service/api 8000:8000 -n lead-scoring

# Test
curl http://localhost:8000/health
```

---

## Integration Problems

### Webhook Failures

**Check webhook delivery:**

```python
# In application code
import logging
logging.basicConfig(level=logging.DEBUG)

# Monitor webhook sends
webhook_response = requests.post(webhook_url, json=payload, timeout=5)
logging.info(f"Webhook status: {webhook_response.status_code}")
```

**Test webhook endpoint:**

```bash
# Webhook simulation
curl -X POST https://your-webhook-url \
  -H "Content-Type: application/json" \
  -d '{
    "event": "score.created",
    "lead_id": "TEST-001",
    "score": 78.5
  }'
```

---

### CRM Sync Issues

**Verify CRM credentials:**

```bash
# Test CRM connection
python -c "
from integrations.crm import SalesforceClient
client = SalesforceClient(
    username='...',
    password='...',
    security_token='...'
)
client.test_connection()
"
```

**Check sync logs:**

```bash
# View recent syncs
curl http://localhost:8000/sync-status

# Check error details
kubectl logs -f deployment/api -n lead-scoring | grep -i "sync\|error"
```

---

## Error Code Reference

### API Error Codes

| Code | HTTP Status | Meaning | Solution |
|------|------------|---------|----------|
| INVALID_INPUT | 400 | Bad request parameters | Check request schema |
| MISSING_REQUIRED | 422 | Missing required field | Add all required fields |
| LEAD_NOT_FOUND | 404 | Lead ID doesn't exist | Verify lead_id exists |
| DATABASE_ERROR | 500 | Database connection/query error | Check DB status, logs |
| MODEL_ERROR | 500 | Scoring model error | Check model file, logs |
| RATE_LIMITED | 429 | Too many requests | Wait before retry |
| INTERNAL_ERROR | 500 | Unexpected error | Check logs, contact support |
| UNAUTHORIZED | 401 | Invalid API key | Provide valid API key |
| FORBIDDEN | 403 | Insufficient permissions | Check user permissions |

---

## Getting Help

**Logs to collect:**

```bash
# API logs (last 100 lines)
kubectl logs -n lead-scoring deployment/api | tail -100

# Database logs
docker logs postgres-container | tail -100

# System logs
journalctl -u api.service -n 100

# Browser console (if using web UI)
F12 → Console tab
```

**Information to include in bug reports:**

1. Error message (complete)
2. Steps to reproduce
3. Logs (see above)
4. Environment (Python version, OS, K8s version)
5. Request/response (sanitized)

**Support channels:**

- GitHub Issues: Feature requests, bugs
- GitHub Discussions: Questions, help
- Slack: Real-time support (if available)
- Email: enterprise@yourdomain.com

---

**See Also:**
- [OPERATIONS_GUIDE.md](OPERATIONS_GUIDE.md)
- [API_REFERENCE.md](API_REFERENCE.md)
- [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md)
