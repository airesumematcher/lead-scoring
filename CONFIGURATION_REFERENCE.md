# Configuration Reference - Lead Scoring System

Complete reference for all 45+ configuration parameters and environment variables.

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Application Settings](#application-settings)
3. [Database Configuration](#database-configuration)
4. [API Configuration](#api-configuration)
5. [Security Settings](#security-settings)
6. [Monitoring & Logging](#monitoring--logging)
7. [Feature Flags](#feature-flags)
8. [Scoring Parameters](#scoring-parameters)
9. [Integration Settings](#integration-settings)
10. [Cloud Provider Settings](#cloud-provider-settings)

---

## Quick Reference

### Most Important Settings

```env
# Database (REQUIRED)
DATABASE_URL=postgresql://user:password@localhost:5432/lead_scoring

# API Security (REQUIRED)
API_KEY_SECRET=change-this-to-random-secret
JWT_SECRET=change-this-to-random-jwt-secret

# Environment
ENVIRONMENT=production  # or: development, staging

# Ports
API_PORT=8000
PROMETHEUS_PORT=9090
```

---

## Application Settings

### `ENVIRONMENT`
- **Type:** String
- **Default:** `development`
- **Options:** `development`, `staging`, `production`
- **Description:** Deployment environment. Affects logging level, error verbosity.
- **Example:** `ENVIRONMENT=production`

### `API_HOST`
- **Type:** String
- **Default:** `0.0.0.0`
- **Description:** Host to bind API server
- **Example:** `API_HOST=0.0.0.0`

### `API_PORT`
- **Type:** Integer
- **Default:** `8000`
- **Range:** 1024-65535
- **Description:** Port number for API server
- **Example:** `API_PORT=8000`

### `API_VERSION`
- **Type:** String
- **Default:** `1.0.0`
- **Description:** API version number
- **Example:** `API_VERSION=1.0.0`

### `APP_NAME`
- **Type:** String
- **Default:** `Lead Scoring API`
- **Description:** Application name displayed in docs/headers
- **Example:** `APP_NAME=Lead Scoring API`

### `WORKERS`
- **Type:** Integer
- **Default:** `4`
- **Range:** 1-32
- **Description:** Number of worker threads for async processing
- **Example:** `WORKERS=4`

### `RELOAD_ON_CHANGE`
- **Type:** Boolean
- **Default:** `false`
- **Options:** `true`, `false`
- **Description:** Auto-reload when code changes (development only)
- **Example:** `RELOAD_ON_CHANGE=true`

---

## Database Configuration

### `DATABASE_URL`
- **Type:** String (URI)
- **Required:** Yes
- **Format:** `postgresql://[user[:password]@][host[:port]][/dbname][?param=value]`
- **Description:** PostrgreSQL connection string
- **Examples:**
  ```
  development:  postgresql://localhost/lead_scoring
  production:   postgresql://user:pw@prod-db.rds.amazonaws.com:5432/lead_scoring
  with-params:  postgresql://user:pw@host/lead_scoring?sslmode=require&connect_timeout=10
  ```

### `DATABASE_POOL_SIZE`
- **Type:** Integer
- **Default:** `20`
- **Range:** 5-100
- **Description:** Number of connections in pool (active connections)
- **Note:** Adjust for concurrent load
- **Example:** `DATABASE_POOL_SIZE=20`

### `DATABASE_POOL_MAX_OVERFLOW`
- **Type:** Integer
- **Default:** `10`
- **Range:** 0-50
- **Description:** Extra connections allowed beyond pool size for spikes
- **Example:** `DATABASE_POOL_MAX_OVERFLOW=10`

### `DATABASE_POOL_TIMEOUT`
- **Type:** Integer (seconds)
- **Default:** `30`
- **Range:** 5-300
- **Description:** Time to wait for a connection from pool
- **Example:** `DATABASE_POOL_TIMEOUT=30`

### `DATABASE_ECHO_SQL`
- **Type:** Boolean
- **Default:** `false`
- **Options:** `true`, `false`
- **Description:** Log all SQL queries (verbose, development only)
- **Example:** `DATABASE_ECHO_SQL=false`

### `DATABASE_ISOLATION_LEVEL`
- **Type:** String
- **Default:** `READ_COMMITTED`
- **Options:** `READ_COMMITTED`, `SERIALIZABLE`, `REPEATABLE_READ`
- **Description:** Transaction isolation level
- **Example:** `DATABASE_ISOLATION_LEVEL=READ_COMMITTED`

---

## API Configuration

### `ALLOWED_ORIGINS`
- **Type:** String (comma-separated)
- **Default:** `http://localhost:8000`
- **Description:** CORS allowed origins
- **Example:** `ALLOWED_ORIGINS=https://yourdomain.com,https://crm.yourdomain.com`

### `CORS_CREDENTIALS`
- **Type:** Boolean
- **Default:** `true`
- **Options:** `true`, `false`
- **Description:** Allow cookies in CORS requests
- **Example:** `CORS_CREDENTIALS=true`

### `CORS_METHODS`
- **Type:** String (comma-separated)
- **Default:** `GET,POST,PUT,DELETE,OPTIONS`
- **Description:** Allowed HTTP methods
- **Example:** `CORS_METHODS=GET,POST,PUT,DELETE`

### `CORS_HEADERS`
- **Type:** String (comma-separated)
- **Default:** `Content-Type,Authorization,X-API-Key`
- **Description:** Allowed request headers
- **Example:** `CORS_HEADERS=Content-Type,Authorization,X-API-Key`

### `MAX_BATCH_SIZE`
- **Type:** Integer
- **Default:** `1000`
- **Range:** 10-10000
- **Description:** Maximum leads per batch request
- **Example:** `MAX_BATCH_SIZE=1000`

### `BATCH_CHUNK_SIZE`
- **Type:** Integer
- **Default:** `100`
- **Range:** 10-1000
- **Description:** Leads per internal processing chunk
- **Example:** `BATCH_CHUNK_SIZE=100`

### `REQUEST_TIMEOUT_SECONDS`
- **Type:** Integer
- **Default:** `30`
- **Range:** 5-300
- **Description:** HTTP request timeout
- **Example:** `REQUEST_TIMEOUT_SECONDS=30`

### `RESPONSE_COMPRESSION`
- **Type:** Boolean
- **Default:** `true`
- **Options:** `true`, `false`
- **Description:** Enable gzip response compression
- **Example:** `RESPONSE_COMPRESSION=true`

---

## Security Settings

### `API_KEY_SECRET`
- **Type:** String
- **Required:** Yes
- **Minimum Length:** 32 characters
- **Description:** Secret key for API authentication
- **Generation:**
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **Example:** `API_KEY_SECRET=your-generated-secret-key`

### `JWT_SECRET`
- **Type:** String
- **Required:** Yes
- **Minimum Length:** 32 characters
- **Description:** Secret key for JWT token signing
- **Generation:**
  ```bash
  openssl rand -base64 32
  ```
- **Example:** `JWT_SECRET=your-jwt-secret`

### `JWT_ALGORITHM`
- **Type:** String
- **Default:** `HS256`
- **Options:** `HS256`, `RS256`, `HS512`
- **Description:** JWT signing algorithm
- **Example:** `JWT_ALGORITHM=HS256`

### `JWT_EXPIRATION_HOURS`
- **Type:** Integer
- **Default:** `24`
- **Range:** 1-8760 (1 year)
- **Description:** JWT token expiration
- **Example:** `JWT_EXPIRATION_HOURS=24`

### `ENABLE_HTTPS`
- **Type:** Boolean
- **Default:** `true` (production)
- **Options:** `true`, `false`
- **Description:** Require HTTPS in production
- **Example:** `ENABLE_HTTPS=true`

### `SSL_CERT_PATH`
- **Type:** String (file path)
- **Default:** NULL
- **Description:** Path to SSL certificate file (for HTTPS)
- **Example:** `SSL_CERT_PATH=/etc/ssl/certs/api.crt`

### `SSL_KEY_PATH`
- **Type:** String (file path)
- **Default:** NULL
- **Description:** Path to SSL private key file
- **Example:** `SSL_KEY_PATH=/etc/ssl/private/api.key`

### `HSTS_ENABLED`
- **Type:** Boolean
- **Default:** `true` (production)
- **Options:** `true`, `false`
- **Description:** Enable HTTP Strict Transport Security
- **Example:** `HSTS_ENABLED=true`

### `HSTS_MAX_AGE`
- **Type:** Integer (seconds)
- **Default:** `31536000` (1 year)
- **Description:** HSTS max age header
- **Example:** `HSTS_MAX_AGE=31536000`

---

## Monitoring & Logging

### `LOG_LEVEL`
- **Type:** String
- **Default:** `INFO`
- **Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Description:** Logging verbosity level
- **Example:** `LOG_LEVEL=INFO`

### `DEBUG_MODE`
- **Type:** Boolean
- **Default:** `false`
- **Options:** `true`, `false`
- **Description:** Enable verbose debugging output
- **Example:** `DEBUG_MODE=false`

### `LOG_FORMAT`
- **Type:** String
- **Default:** `json`
- **Options:** `json`, `text`
- **Description:** Log output format
- **Example:** `LOG_FORMAT=json`

### `ENABLE_QUERY_LOGGING`
- **Type:** Boolean
- **Default:** `false`
- **Options:** `true`, `false`
- **Description:** Log all database queries (expensive)
- **Example:** `ENABLE_QUERY_LOGGING=false`

### `QUERY_LOG_THRESHOLD_MS`
- **Type:** Integer
- **Default:** `100`
- **Range:** 0-5000
- **Description:** Log queries slower than this (milliseconds)
- **Example:** `QUERY_LOG_THRESHOLD_MS=100`

### `PROMETHEUS_METRICS_PORT`
- **Type:** Integer
- **Default:** `9090`
- **Range:** 1024-65535
- **Description:** Port for Prometheus metrics endpoint
- **Example:** `PROMETHEUS_METRICS_PORT=9090`

### `ENABLE_PROFILING`
- **Type:** Boolean
- **Default:** `false`
- **Options:** `true`, `false`
- **Description:** Enable performance profiling (high overhead)
- **Example:** `ENABLE_PROFILING=false`

### `SENTRY_DSN`
- **Type:** String (optional)
- **Default:** NULL
- **Description:** Sentry error tracking DSN
- **Example:** `SENTRY_DSN=https://key@sentry.io/123456`

---

## Feature Flags

### `ENABLE_BATCH_PROCESSING`
- **Type:** Boolean
- **Default:** `true`
- **Options:** `true`, `false`
- **Description:** Enable /score-batch endpoint
- **Example:** `ENABLE_BATCH_PROCESSING=true`

### `ENABLE_FEEDBACK_COLLECTION`
- **Type:** Boolean
- **Default:** `true`
- **Options:** `true`, `false`
- **Description:** Enable /feedback endpoint
- **Example:** `ENABLE_FEEDBACK_COLLECTION=true`

### `ENABLE_RETRAINING`
- **Type:** Boolean
- **Default:** `true`
- **Options:** `true`, `false`
- **Description:** Enable /retrain endpoint
- **Example:** `ENABLE_RETRAINING=true`

### `ENABLE_DRIFT_DETECTION`
- **Type:** Boolean
- **Default:** `true`
- **Options:** `true`, `false`
- **Description:** Enable drift monitoring
- **Example:** `ENABLE_DRIFT_DETECTION=true`

### `ENABLE_CACHING`
- **Type:** Boolean
- **Default:** `false`
- **Options:** `true`, `false`
- **Description:** Enable Redis response caching
- **Example:** `ENABLE_CACHING=false`

### `ENABLE_WEBHOOKS`
- **Type:** Boolean
- **Default:** `true`
- **Options:** `true`, `false`
- **Description:** Enable webhook notifications
- **Example:** `ENABLE_WEBHOOKS=true`

---

## Scoring Parameters

### `ACCURACY_WEIGHT`
- **Type:** Float
- **Default:** `0.35`
- **Range:** 0.0-1.0
- **Description:** Weight for accuracy in composite score
- **Note:** Sum of all weights should = 1.0
- **Example:** `ACCURACY_WEIGHT=0.35`

### `CLIENT_FIT_WEIGHT`
- **Type:** Float
- **Default:** `0.40`
- **Range:** 0.0-1.0
- **Description:** Weight for client fit in composite score
- **Example:** `CLIENT_FIT_WEIGHT=0.40`

### `ENGAGEMENT_WEIGHT`
- **Type:** Float
- **Default:** `0.25`
- **Range:** 0.0-1.0
- **Description:** Weight for engagement in composite score
- **Example:** `ENGAGEMENT_WEIGHT=0.25`

### `GATING_ENABLED`
- **Type:** Boolean
- **Default:** `true`
- **Options:** `true`, `false`
- **Description:** Enable hard gating (email validation, etc.)
- **Example:** `GATING_ENABLED=true`

### `EMAIL_VALIDATION_REQUIRED`
- **Type:** Boolean
- **Default:** `true`
- **Options:** `true`, `false`
- **Description:** Fail score if email invalid
- **Example:** `EMAIL_VALIDATION_REQUIRED=true`

---

## Drift Detection Settings

### `DRIFT_THRESHOLD`
- **Type:** Float
- **Default:** `0.10`
- **Range:** 0.0-1.0
- **Description:** Threshold for drift detection (10% = warning)
- **Example:** `DRIFT_THRESHOLD=0.10`

### `ACCEPTANCE_RATE_THRESHOLD`
- **Type:** Float
- **Default:** `0.50`
- **Range:** 0.0-1.0
- **Description:** Minimum acceptable acceptance rate
- **Example:** `ACCEPTANCE_RATE_THRESHOLD=0.50`

### `CONFIDENCE_THRESHOLD`
- **Type:** Float
- **Default:** `0.70`
- **Range:** 0.0-1.0
- **Description:** Minimum acceptable confidence level
- **Example:** `CONFIDENCE_THRESHOLD=0.70`

### `MIN_FEEDBACK_FOR_RETRAIN`
- **Type:** Integer
- **Default:** `50`
- **Range:** 5-10000
- **Description:** Feedback samples needed before auto-retrain
- **Example:** `MIN_FEEDBACK_FOR_RETRAIN=50`

### `MAX_SAL_WEIGHT`
- **Type:** Float
- **Default:** `0.30`
- **Range:** 0.0-1.0
- **Description:** Max weight for Sales Accepted Lead feedback signal
- **Example:** `MAX_SAL_WEIGHT=0.30`

---

## Integration Settings

### `SALESFORCE_ENABLED`
- **Type:** Boolean
- **Default:** `false`
- **Options:** `true`, `false`
- **Description:** Enable Salesforce integration
- **Example:** `SALESFORCE_ENABLED=false`

### `SALESFORCE_CLIENT_ID`
- **Type:** String
- **Default:** NULL
- **Description:** Salesforce OAuth2 client ID
- **Example:** `SALESFORCE_CLIENT_ID=your-client-id`

### `SALESFORCE_CLIENT_SECRET`
- **Type:** String
- **Default:** NULL
- **Description:** Salesforce OAuth2 client secret
- **Example:** `SALESFORCE_CLIENT_SECRET=your-client-secret`

### `HUBSPOT_ENABLED`
- **Type:** Boolean
- **Default:** `false`
- **Options:** `true`, `false`
- **Description:** Enable HubSpot integration
- **Example:** `HUBSPOT_ENABLED=false`

### `HUBSPOT_API_KEY`
- **Type:** String
- **Default:** NULL
- **Description:** HubSpot private app API key
- **Example:** `HUBSPOT_API_KEY=pat-xxx-xxx-xxx`

### `WEBHOOK_TIMEOUT_SECONDS`
- **Type:** Integer
- **Default:** `10`
- **Range:** 1-60
- **Description:** Timeout for webhook delivery
- **Example:** `WEBHOOK_TIMEOUT_SECONDS=10`

### `WEBHOOK_RETRIES`
- **Type:** Integer
- **Default:** `3`
- **Range:** 0-10
- **Description:** Number of retries for failed webhooks
- **Example:** `WEBHOOK_RETRIES=3`

---

## Cloud Provider Settings

### AWS

```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET=lead-scoring-prod
S3_PREFIX=models/
RDS_ENDPOINT=prod.xxxxx.rds.amazonaws.com
RDS_PORT=5432
```

### Azure

```env
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_RESOURCE_GROUP=lead-scoring-rg
AZURE_COSMOS_DB_KEY=your-cosmos-key
AZURE_STORAGE_ACCOUNT=leadscoringstorage
AZURE_STORAGE_KEY=your-storage-key
```

### GCP

```env
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
FIRESTORE_DATABASE=lead_scoring
CLOUD_STORAGE_BUCKET=lead-scoring-prod
```

---

## Example Configuration Files

### Development (.env.development)

```env
ENVIRONMENT=development
LOG_LEVEL=DEBUG
DEBUG_MODE=true
DATABASE_URL=postgresql://localhost/lead_scoring_dev
API_KEY_SECRET=dev-secret-do-not-use-in-production
JWT_SECRET=dev-jwt-secret
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Staging (.env.staging)

```env
ENVIRONMENT=staging
LOG_LEVEL=INFO
DEBUG_MODE=false
DATABASE_URL=postgresql://user:pass@staging-db.example.com/lead_scoring
API_KEY_SECRET=generate-a-random-secret
JWT_SECRET=generate-a-random-jwt-secret
ALLOWED_ORIGINS=https://staging-api.example.com
SENTRY_DSN=https://key@sentry.io/staging
DATABASE_POOL_SIZE=25
```

### Production (.env.production)

```env
ENVIRONMENT=production
LOG_LEVEL=WARNING
DEBUG_MODE=false
DATABASE_URL=postgresql://user:pass@prod-db.rds.amazonaws.com/lead_scoring
API_KEY_SECRET=use-secrets-manager-in-production
JWT_SECRET=use-secrets-manager-in-production
ALLOWED_ORIGINS=https://api.yourdomain.com,https://crm.yourdomain.com
SENTRY_DSN=https://key@sentry.io/production
ENABLE_HTTPS=true
HSTS_ENABLED=true
DATABASE_POOL_SIZE=50
DATABASE_POOL_MAX_OVERFLOW=20
REQUEST_TIMEOUT_SECONDS=30
```

---

## Configuration Validation

**Check configuration on startup:**

```python
from pydantic_settings import BaseSettings
from pydantic import validator

class AppConfig(BaseSettings):
    environment: str
    api_port: int
    database_url: str
    api_key_secret: str
    jwt_secret: str
    
    @validator('environment')
    def validate_environment(cls, v):
        if v not in ['development', 'staging', 'production']:
            raise ValueError('Invalid environment')
        return v
    
    @validator('database_url')
    def validate_database_url(cls, v):
        if not v.startswith('postgresql://'):
            raise ValueError('Must use PostgreSQL')
        return v

# Load and validate
config = AppConfig()  # Raises validation errors if invalid
```

**Pre-deployment checklist:**

```bash
python -c "
from config import AppConfig
try:
    config = AppConfig()
    print('✓ Configuration valid')
    print(f'Environment: {config.environment}')
    print(f'Database: {config.database_url[:30]}...')
except Exception as e:
    print(f'✗ Configuration invalid: {e}')
    exit(1)
"
```

---

## Best Practices

### Secrets Management

❌ **DO NOT:**
```env
DATABASE_URL=postgresql://user:password@host/db  # Password visible
API_KEY_SECRET=my-simple-secret  # Too weak
```

✅ **DO:**
```bash
# Use environment variable references
# Use secrets manager
export DATABASE_URL=$(aws secretsmanager get-secret-value --secret-id db-prod | jq -r .SecretString)

# Generate strong secrets
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Environment Variables

```bash
# Load from .env file (development)
python -m dotenv run python app.py

# Kubernetes secret
kubectl create secret generic app-config \
  --from-literal=DATABASE_URL="..." \
  --from-literal=API_KEY_SECRET="..."

# Docker
docker run -e DATABASE_URL=... -e API_KEY_SECRET=... api:latest
```

### Configuration Hierarchy

1. **Hardcoded defaults** (safe values)
2. **Config files** (.env, config.yaml)
3. **Environment variables** (override config files)
4. **Secrets manager** (AWS Secrets Manager, Vault)
5. **Command-line args** (CLI overrides)

---

**See Also:**
- [.env.example](.env.example) - Template
- [OPERATIONS_GUIDE.md](OPERATIONS_GUIDE.md)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
