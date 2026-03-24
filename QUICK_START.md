# Quick Start Guide - Production Deployment

## 5-Minute Setup

### Option 1: Local Python (Fastest)

```bash
# 1. Create environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -e .

# 3. Verify the project
python verify_setup.py

# 4. Start the API
uvicorn src.lead_scoring.api.app:app --host 0.0.0.0 --port 8000

# 5. Verify
curl http://localhost:8000/health
open http://localhost:8000/docs
```

### Option 2: Local Docker (Development/Testing)

```bash
# 1. Clone and navigate
cd /tmp/lead-scoring

# 2. Start services
docker-compose up -d

# 3. Verify API is running
curl http://localhost:8000/health

# 4. View Swagger docs
open http://localhost:8000/docs

# 5. Done! API is running on http://localhost:8000
```

### Option 3: Kubernetes (Production)

```bash
# 1. Configure kubectl to your cluster
kubectl config set-context your-cluster-context

# 2. Verify cluster access
kubectl cluster-info

# 3. Deploy with one command
kubectl apply -f k8s/

# 4. Monitor deployment
kubectl get pods -n lead-scoring -w

# 5. Port forward to test
kubectl port-forward -n lead-scoring svc/lead-scoring-api 8000:80

# 6. Test API
curl http://localhost:8000/health
```

## Pre-Flight Checklist

Before deploying to production:

- [ ] **Secrets Created**
  ```bash
  kubectl create secret generic lead-scoring-secrets \
    --from-literal=DATABASE_URL='your-db-url' \
    --from-literal=API_KEY_SECRET='your-secret' \
    -n lead-scoring
  ```

- [ ] **Database Ready**
  - PostgreSQL 15+ running and accessible
  - Database initialized (scripts/init_db.sql applied)
  - Connection string tested

- [ ] **Configuration Updated**
  - Edit `k8s/configmap.yaml` with your settings
  - Edit `k8s/secrets.yaml` with credentials
  - Review `k8s/deployment.yaml` resource limits

- [ ] **Container Images Built**
  ```bash
  docker build -t your-registry/lead-scoring:v1.0.0 .
  docker push your-registry/lead-scoring:v1.0.0
  ```

- [ ] **Kubernetes Cluster Ready**
  - Cluster running 1.27+
  - 3+ nodes with 2CPU/4GB RAM each
  - Persistent storage configured
  - Ingress controller installed (nginx recommended)

- [ ] **Monitoring Setup**
  - Prometheus installed
  - Grafana dashboards created
  - Alert rules configured

## Deployment Steps

### Step 1: Prepare Environment

```bash
# Copy environment template
cp .env.example .env.production
# Edit with production values
nano .env.production

# Create namespace
kubectl create namespace lead-scoring

# Create secrets
kubectl create secret generic lead-scoring-secrets \
  --from-env-file=.env.production \
  -n lead-scoring
```

### Step 2: Initialize Database

```bash
# Apply database initialization
kubectl apply -f k8s/postgres.yaml

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=Ready pod \
  -l app=postgres -n lead-scoring --timeout=300s

# Initialize schema
kubectl exec postgres-0 -n lead-scoring -- \
  psql -U lead_user -d lead_scoring_db < scripts/init_db.sql
```

### Step 3: Deploy API

```bash
# Apply all Kubernetes manifests
kubectl apply -f k8s/

# Monitor deployment
kubectl rollout status deployment/lead-scoring-api -n lead-scoring

# Verify pods are running
kubectl get pods -n lead-scoring
```

### Step 4: Verify Deployment

```bash
# Port forward
kubectl port-forward -n lead-scoring svc/lead-scoring-api 8000:80 &

# Test API
curl http://localhost:8000/health
# Expected: {"status": "healthy", "version": "1.0.0"}

# View Swagger docs
open http://localhost:8000/docs

# Check logs
kubectl logs -f deployment/lead-scoring-api -n lead-scoring
```

### Step 5: Setup Monitoring

```bash
# Install Prometheus (optional)
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace

# Install Grafana (optional)
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Access Grafana at http://localhost:3000
```

## Common Commands

```bash
# View deployment status
kubectl get deployment -n lead-scoring
kubectl describe deployment lead-scoring-api -n lead-scoring

# View pods
kubectl get pods -n lead-scoring
kubectl logs <pod-name> -n lead-scoring

# Scale deployment
kubectl scale deployment lead-scoring-api --replicas=5 -n lead-scoring

# Update deployment
kubectl set image deployment/lead-scoring-api \
  api=registry/lead-scoring:v1.1.0 -n lead-scoring

# Delete deployment
kubectl delete namespace lead-scoring

# Port forward for testing
kubectl port-forward -n lead-scoring svc/lead-scoring-api 8000:80

# SSH into pod
kubectl exec -it <pod-name> -n lead-scoring -- /bin/bash
```

## Troubleshooting

### Pods not starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n lead-scoring

# View logs
kubectl logs <pod-name> -n lead-scoring

# Check events
kubectl get events -n lead-scoring
```

### Database connection error

```bash
# Test connectivity
kubectl run -it --rm debug --image=postgres:15-alpine \
  -- psql <DATABASE_URL>

# Check postgres pod
kubectl logs postgres-0 -n lead-scoring

# Port forward to postgres
kubectl port-forward -n lead-scoring postgres-0 5432:5432
psql postgresql://user:password@localhost:5432/lead_scoring_db
```

### API not responding

```bash
# Check deployment
kubectl get deployment lead-scoring-api -n lead-scoring
kubectl describe deployment lead-scoring-api -n lead-scoring

# View logs
kubectl logs -f deployment/lead-scoring-api -n lead-scoring

# Check service
kubectl get svc -n lead-scoring
kubectl describe svc lead-scoring-api -n lead-scoring

# Port forward and test
kubectl port-forward -n lead-scoring svc/lead-scoring-api 8000:80
curl http://localhost:8000/health
```

## Scaling Guide

### Auto-scaling (Recommended)

HPA automatically scales based on CPU/memory. Check status:

```bash
kubectl get hpa -n lead-scoring
kubectl describe hpa lead-scoring-api-hpa -n lead-scoring
```

### Manual Scaling

```bash
# Scale to 5 replicas
kubectl scale deployment lead-scoring-api --replicas=5 -n lead-scoring

# Scale down
kubectl scale deployment lead-scoring-api --replicas=3 -n lead-scoring
```

## Performance Tuning

### API Workers

Edit `k8s/configmap.yaml`:
```yaml
API_WORKERS: "4"  # Set to 2-4 x CPU cores
```

### Database Connection Pool

```yaml
DB_POOL_SIZE: "20"      # Active connections
DB_MAX_OVERFLOW: "40"   # Max overflow connections
DB_POOL_TIMEOUT: "30"   # Timeout in seconds
```

### Resource Limits

Edit `k8s/deployment.yaml`:
```yaml
resources:
  requests:
    cpu: 500m          # Guaranteed
    memory: 512Mi
  limits:
    cpu: 1000m         # Maximum
    memory: 1Gi
```

## Maintenance

### Backup Database

```bash
kubectl exec postgres-0 -n lead-scoring -- \
  pg_dump lead_scoring_db > backup.sql
```

### Restore Database

```bash
kubectl exec -i postgres-0 -n lead-scoring -- \
  psql lead_scoring_db < backup.sql
```

### Update API

```bash
# Build new image
docker build -t registry/lead-scoring:v1.1.0 .
docker push registry/lead-scoring:v1.1.0

# Update deployment
kubectl set image deployment/lead-scoring-api \
  api=registry/lead-scoring:v1.1.0 -n lead-scoring

# Monitor rollout
kubectl rollout status deployment/lead-scoring-api -n lead-scoring

# Rollback if needed
kubectl rollout undo deployment/lead-scoring-api -n lead-scoring
```

## Next Steps

1. **Complete Documentation**: See [DEPLOYMENT.md](DEPLOYMENT.md) for full guide
2. **Setup Monitoring**: Configure Prometheus and Grafana
3. **Configure Backups**: Setup automated database backups
4. **Security Hardening**: Review and implement security best practices
5. **Performance Testing**: Load test at expected scale
6. **Team Training**: Train ops team on deployment and troubleshooting

## Getting Help

- **Logs**: `kubectl logs -f deployment/lead-scoring-api -n lead-scoring`
- **Events**: `kubectl get events -n lead-scoring`
- **Status**: `kubectl describe deployment lead-scoring-api -n lead-scoring`
- **Documentation**: See [DEPLOYMENT.md](DEPLOYMENT.md)

---

**Deployment complete!** Your Lead Scoring API is now running in production. 🚀
