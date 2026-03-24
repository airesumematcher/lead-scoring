# Production Deployment Guide

## Overview

This guide covers deploying the Lead Scoring System to production using Kubernetes and Docker.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Docker Setup](#docker-setup)
3. [Local Testing](#local-testing)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Configuration](#configuration)
6. [Monitoring](#monitoring)
7. [Scaling](#scaling)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools
- Docker & Docker Compose
- kubectl 1.27+
- Kubernetes cluster 1.27+
- Helm 3.0+ (optional, for package management)
- PostgreSQL 15+ (managed or self-hosted)
- Redis 7+ (optional, for caching)

### Required Accounts/Access
- Container registry access (Docker Hub, ECR, GCR, etc.)
- Kubernetes cluster credentials
- PostgreSQL database access
- Secrets management (Vault, AWS Secrets Manager, etc.)

### System Requirements
- Minimum cluster: 3 nodes with 2 CPU, 4GB RAM each
- Storage: 10GB+ persistent volume for database
- Network: Low-latency connection to database

## Docker Setup

### 1. Build Docker Image

```bash
# Build image locally
docker build -t lead-scoring:latest .

# Tag for registry
docker tag lead-scoring:latest myregistry.azurecr.io/lead-scoring:v1.0.0

# Push to registry
docker push myregistry.azurecr.io/lead-scoring:v1.0.0
```

### 2. Test Locally with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check services
docker-compose ps

# View logs
docker-compose logs -f api

# Run tests
docker-compose exec api pytest tests/

# Stop services
docker-compose down

# Clean up volumes
docker-compose down -v
```

### 3. Environment Variables

Copy and customize environment file:

```bash
cp .env.example .env
# Edit .env with your values
```

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `API_KEY_SECRET` - API authentication secret
- `JWT_SECRET` - JWT signing secret
- `REDIS_URL` - Redis connection (optional)

## Local Testing

### 1. Start Local Environment

```bash
# Start services
docker-compose up -d

# Wait for database to initialize (5-10 seconds)
sleep 10

# Check API is running
curl http://localhost:8000/health
```

### 2. Run Tests

```bash
# Run all tests
docker-compose exec api pytest tests/ -v

# Run with coverage
docker-compose exec api pytest tests/ --cov=src/lead_scoring --cov-report=html

# Run specific test file
docker-compose exec api pytest tests/test_comprehensive.py -v
```

### 3. Test API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Score a lead
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "LEAD-001",
    "email": "john@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "company_name": "ACME Corp",
    "title": "VP Sales"
  }'

# API docs
open http://localhost:8000/docs
```

## Kubernetes Deployment

### 1. Prerequisites Setup

```bash
# Create namespace
kubectl create namespace lead-scoring

# Create secrets (replace with your actual values!)
kubectl create secret generic lead-scoring-secrets \
  --from-literal=DATABASE_URL='postgresql://user:pass@postgres:5432/db' \
  --from-literal=API_KEY_SECRET='your-secret-key' \
  -n lead-scoring

# Verify
kubectl get secrets -n lead-scoring
```

### 2. Deploy with kubectl

```bash
# Apply all manifests
kubectl apply -f k8s/

# Verify deployment
kubectl get all -n lead-scoring

# Check deployment status
kubectl rollout status deployment/lead-scoring-api -n lead-scoring

# View pods
kubectl get pods -n lead-scoring -w

# View logs
kubectl logs -f deployment/lead-scoring-api -n lead-scoring
```

### 3. Deploy with Kustomize

```bash
# Apply with Kustomize
kubectl apply -k k8s/

# Preview changes
kubectl kustomize k8s/
```

### 4. Verify Deployment

```bash
# Port forward to test
kubectl port-forward -n lead-scoring svc/lead-scoring-api 8000:80

# In another terminal
curl http://localhost:8000/health

# Check pod logs
kubectl logs -n lead-scoring -l app=lead-scoring-api --tail=50 -f

# Check pod resource usage
kubectl top pods -n lead-scoring
```

## Configuration

### 1. Update Configuration

Edit `k8s/configmap.yaml`:

```yaml
data:
  LOG_LEVEL: "INFO"
  API_WORKERS: "4"
  BATCH_SIZE: "100"
  # ... other configs
```

Apply changes:

```bash
kubectl apply -f k8s/configmap.yaml
# Force pod restart
kubectl rollout restart deployment/lead-scoring-api -n lead-scoring
```

### 2. Secrets Management

For production, use:
- **AWS Secrets Manager**: `aws secretsmanager`
- **Azure Key Vault**: `az keyvault`
- **HashiCorp Vault**: `vault`
- **Kubernetes Secrets**: `kubectl create secret`

Example with Vault:

```bash
# Store secret
vault kv put secret/lead-scoring/db \
  url=postgresql://user:pass@db:5432/lead-scoring

# Reference in deployment:
# - name: DATABASE_URL
#   valueFrom:
#     secretKeyRef:
#       name: vault-secret
#       key: database-url
```

### 3. TLS/SSL Certificates

Setup Let's Encrypt with cert-manager:

```bash
# Install cert-manager
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace

# Create ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourdomain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

# Update ingress.yaml to use issuer
# cert-manager.io/cluster-issuer: "letsencrypt-prod"
```

## Monitoring

### 1. Enable Metrics

Metrics are available at `http://api:9090/metrics`

```bash
# Port forward
kubectl port-forward -n lead-scoring svc/lead-scoring-api 9090:9090

# Access Prometheus metrics
curl http://localhost:9090/metrics
```

### 2. Setup Prometheus

```bash
# Install Prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace

# Update values for lead-scoring targets
# Add ServiceMonitor for lead-scoring
```

### 3. Setup Grafana Dashboards

```bash
# Get Grafana password
kubectl get secret prometheus-grafana \
  --namespace monitoring \
  -o jsonpath="{.data.admin-password}" | base64 --decode

# Port forward
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Access http://localhost:3000 (admin/password)
# Add Prometheus datasource
# Import/create dashboards
```

### 4. Alerts

Update Prometheus AlertRules:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: lead-scoring-alerts
  namespace: lead-scoring
spec:
  groups:
  - name: lead-scoring
    interval: 30s
    rules:
    - alert: HighErrorRate
      expr: rate(lead_scoring_errors_total[5m]) > 0.1
      for: 5m
      annotations:
        summary: "High error rate in Lead Scoring API"
```

## Scaling

### 1. Horizontal Pod Autoscaling

HPA is configured in `hpa-ingress.yaml`:

```yaml
minReplicas: 3
maxReplicas: 10
metrics:
  - resource:
      name: cpu
      target:
        averageUtilization: 70
  - resource:
      name: memory
      target:
        averageUtilization: 80
```

Check status:

```bash
kubectl get hpa -n lead-scoring
kubectl describe hpa lead-scoring-api-hpa -n lead-scoring
```

### 2. Manual Scaling

```bash
# Scale to specific replicas
kubectl scale deployment lead-scoring-api \
  --replicas=5 -n lead-scoring

# Check replicas
kubectl get replicas -n lead-scoring
```

### 3. Database Scaling

PostgreSQL scaling options:

```bash
# Increase connection pool
# Edit k8s/configmap.yaml
DB_POOL_SIZE: "50"       # Increase from 20
DB_MAX_OVERFLOW: "100"   # Increase from 40

# For high traffic, consider:
# - Read replicas
# - Connection pooler (pgBouncer, pgpool)
# - Partitioning large tables
```

## Troubleshooting

### 1. Pod Won't Start

```bash
# Check pod status
kubectl describe pod <pod-name> -n lead-scoring

# Check logs
kubectl logs <pod-name> -n lead-scoring

# Check events
kubectl get events -n lead-scoring

# Common issues:
# - Secret not found: verify secrets are created
# - Database connection: check DATABASE_URL and connectivity
# - Resource limits: check available resources on nodes
```

### 2. Database Connection Issues

```bash
# Test connectivity from pod
kubectl exec -it <pod-name> -n lead-scoring -- psql \
  postgresql://user:pass@postgres:5432/lead_scoring_db

# Check database logs
kubectl logs postgres-0 -n lead-scoring

# Verify service
kubectl get svc postgres -n lead-scoring
kubectl describe svc postgres -n lead-scoring
```

### 3. Performance Issues

```bash
# Check resource usage
kubectl top pods -n lead-scoring
kubectl top nodes

# Check logs for errors
kubectl logs -f deployment/lead-scoring-api -n lead-scoring

# Check database performance
# Login to database and run:
# SELECT * FROM pg_stat_statements ORDER BY total_time DESC;
```

### 4. Disk Space Issues

```bash
# Check PVC usage
kubectl get pvc -n lead-scoring
kubectl describe pvc postgres-storage-postgres-0 -n lead-scoring

# Cleanup old logs/data
kubectl exec -it postgres-0 -n lead-scoring -- \
  psql lead_scoring_db -c "DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '90 days';"
```

## Maintenance

### 1. Backup Database

```bash
# Backup PostgreSQL
kubectl exec -it postgres-0 -n lead-scoring -- \
  pg_dump lead_scoring_db > backup.sql

# Restore
kubectl exec -i postgres-0 -n lead-scoring -- \
  psql lead_scoring_db < backup.sql
```

### 2. Update Deployment

```bash
# Update image
kubectl set image deployment/lead-scoring-api \
  api=myregistry.azurecr.io/lead-scoring:v1.1.0 \
  -n lead-scoring

# Or edit and apply
kubectl edit deployment lead-scoring-api -n lead-scoring
kubectl apply -f k8s/deployment.yaml

# Check rollout
kubectl rollout status deployment/lead-scoring-api -n lead-scoring
kubectl rollout history deployment/lead-scoring-api -n lead-scoring

# Rollback if needed
kubectl rollout undo deployment/lead-scoring-api -n lead-scoring
```

### 3. Monitor Rollout

```bash
# Watch deployment
kubectl rollout status deployment/lead-scoring-api -n lead-scoring -w

# Watch pods
kubectl get pods -n lead-scoring -w

# View recent events
kubectl get events -n lead-scoring --sort-by='.lastTimestamp' | tail -20
```

## Success Checklist

- [ ] All pods in `Running` state
- [ ] Database migrations completed
- [ ] Health checks passing
- [ ] API responding to `/health`
- [ ] Logs showing no errors
- [ ] Metrics available at `/metrics`
- [ ] Database backups configured
- [ ] Monitoring and alerts configured
- [ ] TLS certificates valid
- [ ] Load tests passed at expected scale
- [ ] Documentation updated
- [ ] Team trained on operations

---

## Support

For issues or questions:
1. Check logs: `kubectl logs -f deployment/lead-scoring-api -n lead-scoring`
2. Review events: `kubectl get events -n lead-scoring`
3. Check status: `kubectl describe deployment lead-scoring-api -n lead-scoring`
4. Contact support team
