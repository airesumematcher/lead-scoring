# Operations Guide - Lead Scoring Platform

Complete operational documentation for deployment, maintenance, monitoring, and troubleshooting of the lead scoring system.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Deployment Methods](#deployment-methods)
3. [Post-Deployment Validation](#post-deployment-validation)
4. [Monitoring Setup](#monitoring-setup)
5. [Backup & Recovery](#backup--recovery)
6. [Common Issues & Solutions](#common-issues--solutions)
7. [Performance Tuning](#performance-tuning)
8. [Maintenance Windows](#maintenance-windows)
9. [Troubleshooting Guide](#troubleshooting-guide)

---

## Pre-Deployment Checklist

### Infrastructure Prerequisites

- [ ] Kubernetes cluster available (1.27+) OR Docker Compose environment
- [ ] PostgreSQL 15 installed or managed service provisioned
- [ ] Redis 7 available (optional, for caching)
- [ ] Domain name configured (for production)
- [ ] SSL/TLS certificate ready (production)
- [ ] Container registry access (Docker Hub, ECR, GCR, or private)
- [ ] kubectl configured with cluster access
- [ ] 2+ GB disk space available
- [ ] 2+ GB RAM available (per pod)
- [ ] Network bandwidth: 10+ Mbps

### Software Prerequisites

```bash
# Check required tools
which docker      # Docker 20.10+
which kubectl     # Kubernetes CLI 1.27+
which psql        # PostgreSQL client 15+
docker --version
kubectl version --client
psql --version
```

### Credentials & Secrets

Prepare the following (fill .env file):

```env
# Database
DATABASE_URL=postgresql://user:password@host:5432/lead_scoring
DATABASE_POOL_SIZE=20
DATABASE_POOL_MAX_OVERFLOW=10

# API
API_HOST=0.0.0.0
API_PORT=8000
API_KEY_SECRET=your-secret-key-here
JWT_SECRET=your-jwt-secret-here

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG_MODE=false

# CORS & Security
ALLOWED_ORIGINS=https://yourdomain.com,https://crm.yourdomain.com
CORS_CREDENTIALS=true

# Monitoring
SENTRY_DSN=https://key@sentry.yourorg.io/project-id
PROMETHEUS_METRICS_PORT=9090
ENABLE_PROFILING=false

# Scaling
MAX_BATCH_SIZE=1000
BATCH_CHUNK_SIZE=100
WORKER_THREADS=4

# Drift Detection
DRIFT_THRESHOLD=0.10
ACCEPTANCE_RATE_THRESHOLD=0.50
MIN_FEEDBACK_FOR_RETRAIN=50

# (See CONFIGURATION_REFERENCE.md for all 45+ parameters)
```

---

## Deployment Methods

### Method 1: Docker Compose (Development/Testing)

**Quick start (5 minutes):**

```bash
# 1. Clone or prepare directory
cd lead-scoring-system

# 2. Set up environment
cp .env.example .env
# Edit .env with your values

# 3. Build and start
docker-compose up -d

# 4. Verify
docker-compose ps
curl http://localhost:8000/health

# 5. View logs
docker-compose logs -f api
docker-compose logs -f postgres

# 6. Stop
docker-compose down
```

**Configuration:**
- PostgreSQL: Host `postgres`, Port 5432
- API: Host `localhost`, Port 8000
- Redis: Host `redis`, Port 6379 (if enabled)

**Common Docker Compose Commands:**

```bash
docker-compose up -d              # Start services
docker-compose down               # Stop & remove containers
docker-compose ps                 # List running services
docker-compose logs api           # View API logs
docker-compose exec api bash      # Shell into API container
docker-compose exec postgres psql # Access database CLI
docker-compose restart api        # Restart API service
docker-compose pull               # Update images
docker-compose build --no-cache   # Rebuild images
```

---

### Method 2: Kubernetes - kubectl (Production)

**Prerequisites:**
- kubectl configured
- Cluster access verified: `kubectl cluster-info`
- Sufficient RBAC permissions

**Deployment (5 steps):**

```bash
# 1. Create namespace
kubectl create namespace lead-scoring

# 2. Create secrets
kubectl create secret generic api-secrets \
  --from-literal=DATABASE_URL="postgresql://..." \
  --from-literal=API_KEY_SECRET="..." \
  --from-literal=JWT_SECRET="..." \
  -n lead-scoring

# 3. Create ConfigMap
kubectl create configmap api-config \
  --from-literal=LOG_LEVEL=INFO \
  --from-literal=DEBUG_MODE=false \
  -n lead-scoring

# 4. Apply manifests in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/hpa-ingress.yaml
kubectl apply -f k8s/resilience.yaml

# 5. Verify deployment
kubectl get all -n lead-scoring
kubectl get pods -n lead-scoring
kubectl describe deployment api -n lead-scoring
```

**Post-Deployment:**

```bash
# Check pod status
kubectl get pods -n lead-scoring -w  # Watch pods starting

# Check logs
kubectl logs -n lead-scoring -l app=api -f

# Port forward (if no ingress)
kubectl port-forward -n lead-scoring service/api 8000:8000

# Test endpoint
curl http://localhost:8000/health

# Scale manually (if HPA disabled)
kubectl scale deployment api --replicas=5 -n lead-scoring
```

---

### Method 3: Kubernetes - Kustomize (Single Command)

**Simplest Kubernetes deployment:**

```bash
# One command to deploy everything
kubectl apply -k k8s/

# Verify
kubectl get all -n lead-scoring

# Update (after editing manifests)
kubectl apply -k k8s/

# Delete everything
kubectl delete -k k8s/
```

**Customization:**
Edit `k8s/kustomization.yaml` to change:
- Replica counts
- Image versions
- ConfigMap values
- Resource limits

---

### Method 4: GitOps (ArgoCD - Automated)

**For continuous deployment:**

```bash
# 1. Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 2. Create ArgoCD Application
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: lead-scoring-api
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/yourorg/lead-scoring
    targetRevision: main
    path: k8s/
  destination:
    server: https://kubernetes.default.svc
    namespace: lead-scoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
EOF

# 3. Access UI
kubectl port-forward -n argocd svc/argocd-server 8080:443

# 4. Get admin password
kubectl get secret -n argocd argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Push commits to main branch → auto deployment
```

---

## Post-Deployment Validation

### 1. Service Health Checks

```bash
# API Health
curl -X GET http://localhost:8000/health
# Expected response:
# {"status": "healthy", "version": "1.0.0", "timestamp": "2025-03-13T..."}

# API Readiness (basic)
curl -X GET http://localhost:8000/ 2>/dev/null | grep -q "openapi" && echo "Ready"

# Database Connection
kubectl exec -it -n lead-scoring deployment/api -- \
  python -c "from database.connection import engine; print(engine.connect())"
```

### 2. Endpoint Validation

```bash
# Test all 8 endpoints exist
for endpoint in health score score-batch feedback feedback/lead-001 retrain drift-status drift-settings; do
  echo -n "Testing /$endpoint ... "
  curl -s "http://localhost:8000/$endpoint" > /dev/null && echo "✓" || echo "✗"
done
```

### 3. Database Validation

```bash
# Verify database exists and tables created
psql -h localhost -U postgres -d lead_scoring -c "
  SELECT table_name FROM information_schema.tables 
  WHERE table_schema = 'public';
"

# Expected tables:
# - leads
# - scores
# - feedback
# - audit_logs
# - batch_jobs
# - model_weights

# Check table row counts
psql -h localhost -U postgres -d lead_scoring -c "
  SELECT 
    'leads' as table_name, COUNT(*) as row_count FROM leads
  UNION ALL
  SELECT 'scores', COUNT(*) FROM scores
  UNION ALL
  SELECT 'feedback', COUNT(*) FROM feedback;
"
```

### 4. Functional Test

```bash
# Test single lead scoring with curl
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "TEST-001",
    "email": "test@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "title": "VP Sales",
    "company_name": "Test Corp",
    "engagement_score": 75
  }' | jq .

# Expected fields in response:
# - score (0-100)
# - grade (A-F)
# - confidence (High/Medium/Low)
# - narrative
# - feature_importance
# - recommendations
```

---

## Monitoring Setup

### Prometheus Metrics

**Configuration:**

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'api'
    static_configs:
      - targets: ['localhost:9090']
    
  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']
    
  - job_name: 'kubernetes'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - lead-scoring
```

**Key Metrics to Monitor:**

```
# API Performance
http_requests_total{endpoint="/score"}
http_request_duration_seconds{endpoint="/score"}
http_requests_in_progress{endpoint="/score"}

# Model Performance
model_score_distribution{grade="A"}
model_confidence_levels{level="High"}
model_inference_time_seconds

# Database
db_query_duration_seconds
db_connection_pool_size
db_connection_pool_available

# System
process_cpu_seconds_total
process_resident_memory_bytes
process_virtual_memory_bytes

# Application
app_feedback_total
app_retrain_duration_seconds
app_drift_detected_total
```

### Grafana Dashboards

**Pre-configured dashboards (optional setup):**

1. **API Performance Dashboard**
   - Request throughput
   - Response latency (p50, p95, p99)
   - Error rates by endpoint
   - Uptime/availability

2. **Model Performance Dashboard**
   - Score distribution
   - Grade distribution
   - Confidence levels
   - Feature importance trends

3. **Database Performance Dashboard**
   - Query latency
   - Connection pool utilization
   - Transaction throughput
   - Index efficiency

4. **System Resource Dashboard**
   - CPU usage
   - Memory consumption
   - Disk I/O
   - Network throughput

### Alert Rules

```yaml
groups:
- name: api_alerts
  interval: 30s
  rules:
  
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    annotations:
      summary: "High error rate (>5%) detected"
  
  - alert: SlowResponses
    expr: histogram_quantile(0.95, http_request_duration_seconds) > 1.0
    for: 5m
    annotations:
      summary: "p95 latency >1s"
  
  - alert: DriftDetected
    expr: app_drift_detected_total > 0
    for: 1m
    annotations:
      summary: "Model drift detected - consider retraining"
  
  - alert: HighMemoryUsage
    expr: process_resident_memory_bytes / 1024 / 1024 > 512
    for: 10m
    annotations:
      summary: "Memory usage >512MB"
  
  - alert: DatabaseDown
    expr: up{job="postgres"} == 0
    for: 1m
    annotations:
      summary: "PostgreSQL database unreachable"
```

---

## Backup & Recovery

### Daily Backups

```bash
#!/bin/bash
# backup_database.sh

BACKUP_DIR="/backups/lead-scoring"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_NAME="lead_scoring"
DB_USER="postgres"

mkdir -p "$BACKUP_DIR"

# PostgreSQL backup
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" \
  | gzip > "$BACKUP_DIR/lead_scoring_$DATE.sql.gz"

# Keep last 30 days
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/lead_scoring_$DATE.sql.gz"
```

**Kubernetes CronJob:**

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: db-backup
  namespace: lead-scoring
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:15-alpine
            command:
            - /bin/sh
            - -c
            - |
              pg_dump -h postgres -U $POSTGRES_USER $POSTGRES_DB | \
              gzip > /backups/lead_scoring_$(date +\%Y\%m\%d_\%H\%M\%S).sql.gz
            env:
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: username
            - name: POSTGRES_DB
              value: lead_scoring
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: password
            volumeMounts:
            - name: backup-storage
              mountPath: /backups
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

### Recovery Procedure

```bash
# 1. Restore from backup
gunzip < lead_scoring_2025-03-13_02-00-00.sql.gz | \
  psql -h localhost -U postgres -d lead_scoring

# 2. Verify data integrity
psql -h localhost -U postgres -d lead_scoring -c "
  SELECT COUNT(*) FROM leads;
  SELECT COUNT(*) FROM scores;
"

# 3. Restart API services
kubectl rollout restart deployment/api -n lead-scoring

# 4. Validate service is up
curl http://localhost:8000/health
```

---

## Common Issues & Solutions

### Issue 1: API Pod Won't Start

**Symptoms:**
```
kubectl get pods -n lead-scoring
NAME                   READY   STATUS        RESTARTS   AGE
api-xyz-abc            0/2     CrashLoopBackOff  5      2m
```

**Diagnosis:**
```bash
kubectl describe pod -n lead-scoring pod/api-xyz-abc
kubectl logs -n lead-scoring pod/api-xyz-abc
```

**Common Causes & Fixes:**

| Cause | Check | Fix |
|-------|-------|-----|
| Missing DATABASE_URL | `kubectl get secrets -n lead-scoring` | Create secret with `kubectl create secret generic` |
| Missing image | `kubectl describe pod` → Status | Update image in deployment: `kubectl set image` |
| Insufficient resources | `kubectl describe nodes` | Request more resources or add nodes |
| Liveness probe failing | `kubectl logs` → Health check fails | Ensure database is reachable |

---

### Issue 2: Database Connection Errors

**Error:** `psycopg2.OperationalError: FATAL: too many connections`

**Solution:**
```python
# Adjust connection pool in .env
DATABASE_POOL_SIZE=20      # Increase from 5
DATABASE_POOL_MAX_OVERFLOW=10  # Increase from 0
```

**Also check:**
```bash
# View active connections
psql -h localhost -U postgres -c "
  SELECT datname, usename, count(*) 
  FROM pg_stat_activity 
  GROUP BY datname, usename;
"
```

---

### Issue 3: High Memory Usage

**Symptoms:** Pod OOMKilled (Out Of Memory)

**Diagnosis:**
```bash
kubectl top pods -n lead-scoring
kubectl describe pod -n lead-scoring <pod-name>
# Look for: "Reason: OOMKilled"
```

**Solutions:**
1. Increase memory limits in deployment.yaml:
```yaml
resources:
  limits:
    memory: "1Gi"
```

2. Enable memory profiling:
```bash
export DEBUG_MODE=true
# Restart and check memory profile
```

3. Check for memory leaks:
```bash
# Monitor memory trend
kubectl top pods -n lead-scoring --use-protocol-buffers=false \
  --container-name=api -w
```

---

### Issue 4: Slow Model Inferencing

**Symptoms:** API responses taking >1 second

**Measures:**
```bash
# Check API metrics
curl http://localhost:9090/metrics | grep http_request_duration_seconds

# View detailed operation timing
export LOG_LEVEL=DEBUG
kubectl rollout restart deployment/api -n lead-scoring
kubectl logs -f deployment/api -n lead-scoring | grep "duration"
```

**Optimizations:**

```python
# In code: Enable caching
from functools import lru_cache

@lru_cache(maxsize=1000)
def score_lead(lead_features: str) -> float:
    # Caches results for identical feature sets
    pass

# Or use Redis caching
redis_client.set(f"score:{lead_id}", score, ex=3600)
```

---

### Issue 5: Model Drift Alerts

**Symptoms:**
```
webhook: Drift Status: warning
Drift Score: 0.45 (threshold: 0.10)
Reason: Acceptance rate dropped from 75% to 58%
```

**Response:**

```bash
# 1. Check drift status
curl http://localhost:8000/drift-status

# 2. View recent feedback
psql -h localhost -U postgres -d lead_scoring -c "
  SELECT outcome, COUNT(*) FROM feedback 
  WHERE created_at > NOW() - INTERVAL '7 days'
  GROUP BY outcome;
"

# 3. Trigger retraining
curl -X POST http://localhost:8000/retrain \
  -H "Content-Type: application/json" \
  -d '{"min_feedback_samples": 50, "dry_run": false}'

# 4. Monitor retraining
curl http://localhost:8000/drift-status
```

---

## Performance Tuning

### Database Query Optimization

```bash
# Enable slow query logging
psql -h localhost -U postgres -d lead_scoring -c "
  ALTER SYSTEM SET log_min_duration_statement = 1000;
  SELECT pg_reload_conf();
"

# View slow queries
psql -h localhost -U postgres -d lead_scoring -c "
  SELECT mean_exec_time, calls, query 
  FROM pg_stat_statements 
  WHERE mean_exec_time > 100 
  ORDER BY mean_exec_time DESC;
"
```

### API Caching

```bash
# Enable Redis caching in config
REDIS_URL=redis://localhost:6379/0
ENABLE_RESPONSE_CACHING=true
CACHE_TTL=3600  # 1 hour

# Cache certain endpoints
# GET /feedback/{lead_id} - cached 1 hour
# GET /drift-status - cached 5 minutes
```

### Connection Pool Tuning

```yaml
# In deployment.yaml
env:
  - name: DATABASE_POOL_SIZE
    value: "20"     # Default connections
  - name: DATABASE_POOL_MAX_OVERFLOW
    value: "10"     # Extra for spikes
  - name: DATABASE_POOL_TIMEOUT
    value: "30"     # Wait max 30 seconds
```

---

## Maintenance Windows

### Zero-Downtime Deployment

```bash
# Using rolling updates (Kubernetes default)
kubectl set image deployment/api \
  api=myrepo/api:v2.0.0 \
  -n lead-scoring

# Monitor rollout
kubectl rollout status deployment/api -n lead-scoring

# Rollback if needed
kubectl rollout undo deployment/api -n lead-scoring
```

### Scheduled Maintenance

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
  namespace: lead-scoring
spec:
  minAvailable: 2  # Always keep 2 pods running
  selector:
    matchLabels:
      app: api
```

---

## Troubleshooting Guide

### Debug Mode

Enable debug logging:
```bash
kubectl set env deployment/api LOG_LEVEL=DEBUG -n lead-scoring
kubectl logs -f deployment/api -n lead-scoring | tail -50
```

### Database Access

```bash
# Shell into database container
kubectl exec -it -n lead-scoring statefulset/postgres -- \
  psql -U postgres -d lead_scoring

# Or from outside
psql -h localhost -U postgres -d lead_scoring
```

### Network Diagnostics

```bash
# Test pod-to-pod communication
kubectl run -it debugging --image=curlimages/curl --restart=Never -- \
  curl http://api:8000/health

# Check DNS
kubectl run -it debugging --image=busybox --restart=Never -- \
  nslookup api.lead-scoring.svc.cluster.local

# Test ingress
curl -H "Host: api.yourdomain.com" http://ingress-ip
```

### Resource Analysis

```bash
# Check pod resource usage
kubectl top pods -n lead-scoring

# Check node resources
kubectl top nodes

# Check if HPA is scaling
kubectl get hpa -n lead-scoring
kubectl describe hpa api-hpa -n lead-scoring

# Check events
kubectl get events -n lead-scoring --sort-by='.lastTimestamp'
```

---

## Emergency Procedures

### Service Restart

```bash
# Graceful restart
kubectl rollout restart deployment/api -n lead-scoring

# Wait for readiness
kubectl rollout status deployment/api -n lead-scoring
```

### Database Failover

If using managed database (AWS RDS, Azure DB):
```bash
# Trigger manual failover in console
# Or command:
aws rds promote-read-replica --db-instance-identifier lead-scoring-read-replica
```

### Clear Cache

```bash
# If using Redis
redis-cli FLUSHDB

# Or from pod:
kubectl exec -it redis-deployment -- redis-cli FLUSHDB
```

### Emergency Scale Down

```bash
# If resources exhausted
kubectl scale deployment api --replicas=1 -n lead-scoring
# (Some requests may queue but system remains responsive)
```

---

## Monitoring Dashboard Quick Links

- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000`
- **API Docs**: `http://localhost:8000/docs`
- **API Redoc**: `http://localhost:8000/redoc`
- **ArgoCD** (if deployed): `https://localhost:8080`

---

**See Also:**
- [API_REFERENCE.md](API_REFERENCE.md) - Endpoint documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) - All config options
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Detailed troubleshooting
