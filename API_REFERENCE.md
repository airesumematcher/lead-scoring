# API Reference - Lead Scoring System

Complete API endpoint documentation for the Lead Scoring System.

Current verified baseline:
- `GET /health`
- `POST /score`
- `POST /score-batch`
- `POST /feedback`
- `GET /feedback/{lead_id}`
- `GET /feedback/status`
- `GET /feedback/analytics`
- `GET /drift-status`
- `POST /models/predict-multi`
- `GET /models/comparison-summary`
- `GET /models/recommended-model`
- `POST /score/predict-campaign-aware`

Notes:
- `POST /feedback/submit` remains available as an alias for `POST /feedback`.
- Manual model rebuilds currently run via `python scripts/03_multi_model_comparison.py`.
- Older references in this document to `/retrain` and `/drift-settings` describe planned behavior, not the current verified baseline.

## Base URL

```
Development:  http://localhost:8000
Production:   https://api.yourdomain.com
```

## Authentication

Currently, the API uses API key authentication (optional). In production, add JWT Bearer tokens.

```bash
# With API key (if enabled)
curl -H "X-API-Key: your-api-key" http://localhost:8000/score
```

## Response Format

All responses are JSON with the following structure:

```json
{
  "status": "success|error",
  "data": {},
  "message": "Optional error or info message",
  "timestamp": "2025-03-13T12:34:56Z"
}
```

---

## Endpoints

### 1. Health Check

**GET /health**

Check if the API is running and healthy.

**Request:**
```bash
curl http://localhost:8000/health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-03-13T12:34:56Z"
}
```

**Use Case:** Load balancer health checks, monitoring, deployment verification

---

### 2. Score Single Lead

**POST /score**

Score a single lead with the AI model.

**Request:**
```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d {
    "lead_id": "LEAD-001",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "title": "VP Sales",
    "company_name": "ACME Corp",
    "company_domain": "acme.com",
    "industry": "Technology",
    "campaign_id": "CAMP-Q1-2025",
    "source_partner": "LinkedIn",
    "engagement_score": 85,
    "phone_present": true,
    "email_valid": true
  }
```

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| lead_id | string | ✅ | Unique lead identifier |
| email | string | ✅ | Lead email address |
| first_name | string | ✅ | Lead first name |
| last_name | string | ✅ | Lead last name |
| title | string | ✅ | Job title |
| company_name | string | ✅ | Company name |
| company_domain | string | ❌ | Company domain (optional) |
| industry | string | ❌ | Industry vertical |
| campaign_id | string | ❌ | Campaign identifier |
| source_partner | string | ❌ | Source/partner |
| engagement_score | number | ❌ | Engagement level (0-100) |
| phone_present | boolean | ❌ | Has phone number |
| email_valid | boolean | ❌ | Email validation result |

**Response (200 OK):**
```json
{
  "lead_id": "LEAD-001",
  "score": 78.5,
  "grade": "B",
  "confidence": "High",
  "accuracy_score": 85.0,
  "client_fit_score": 72.0,
  "engagement_score": 75.0,
  "narrative": "Strong B-grade prospect. Excellent email validity (85%) and good client fit profile (72%). Recent engagement activity adds confidence. Recommend outreach with personalized value prop.",
  "feature_importance": [
    {"feature": "email_valid", "importance": 0.35, "impact": "positive"},
    {"feature": "company_fit", "importance": 0.30, "impact": "positive"},
    {"feature": "engagement_velocity", "importance": 0.20, "impact": "positive"},
    {"feature": "title_seniority", "importance": 0.15, "impact": "positive"}
  ],
  "recommendations": [
    "Email delivery is strong - prioritize email campaigns",
    "Company shows good product fit - emphasize ROI benefits",
    "Recent engagement detected - timely outreach recommended"
  ],
  "timestamp": "2025-03-13T12:34:56Z"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| lead_id | string | Echoed from request |
| score | number | 0-100 numeric score |
| grade | string | A-F letter grade |
| confidence | string | High/Medium/Low confidence |
| *_score | number | Component scores (accuracy, fit, engagement) |
| narrative | string | Human-readable explanation |
| feature_importance | array | Ranked contributing factors |
| recommendations | array | Suggested next actions |
| timestamp | string | ISO 8601 timestamp |

**Status Codes:**
- `200 OK` - Successfully scored
- `400 Bad Request` - Invalid input
- `422 Unprocessable Entity` - Missing required fields
- `500 Internal Server Error` - Server error

---

### 3. Score Batch Leads

**POST /score-batch**

Score multiple leads in a single request (up to 1,000).

**Request:**
```bash
curl -X POST http://localhost:8000/score-batch \
  -H "Content-Type: application/json" \
  -d {
    "leads": [
      {"lead_id": "LEAD-001", "email": "john@example.com", ... },
      {"lead_id": "LEAD-002", "email": "jane@example.com", ... }
    ],
    "job_name": "daily_import_2025-03-13"
  }
```

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| leads | array | ✅ | Array of lead objects (max 1,000) |
| job_name | string | ✅ | Name for batch job tracking |

**Response (200 OK):**
```json
{
  "job_id": "job-abc123",
  "status": "completed",
  "total_leads": 2,
  "successful_scores": 2,
  "failed_scores": 0,
  "results": [
    {
      "lead_id": "LEAD-001",
      "score": 78.5,
      "grade": "B",
      "status": "success"
    },
    {
      "lead_id": "LEAD-002",
      "score": 65.3,
      "grade": "C",
      "status": "success"
    }
  ],
  "processing_time_seconds": 2.45,
  "timestamp": "2025-03-13T12:34:56Z"
}
```

**Pagination:**
Batches > 1,000 leads supported via pagination:
```bash
curl "http://localhost:8000/score-batch?offset=1000&limit=1000"
```

**Status Codes:**
- `200 OK` - Batch processed
- `202 Accepted` - Batch queued for async processing
- `400 Bad Request` - Invalid batch
- `413 Payload Too Large` - Batch exceeds size limit
- `500 Internal Server Error` - Server error

---

### 4. Record Feedback

**POST /feedback**

Record user feedback on a scored lead (acceptance/rejection).

**Request:**
```bash
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d {
    "lead_id": "LEAD-001",
    "outcome": "accepted",
    "reason": "Engaged and qualified",
    "provided_score": 78.5,
    "actual_score": 82.0
  }
```

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| lead_id | string | ✅ | Lead to provide feedback on |
| outcome | string | ✅ | accepted/rejected/neutral |
| reason | string | ❌ | Reason for acceptance/rejection |
| provided_score | number | ❌ | Original AI score |
| actual_score | number | ❌ | Human assessment score |
| notes | string | ❌ | Additional notes |

**Response (201 Created):**
```json
{
  "feedback_id": "fb-xyz789",
  "lead_id": "LEAD-001",
  "outcome": "accepted",
  "created_at": "2025-03-13T12:34:56Z",
  "message": "Feedback recorded. Model will be refined based on this signal."
}
```

**Status Codes:**
- `201 Created` - Feedback recorded
- `400 Bad Request` - Invalid outcome value
- `404 Not Found` - Lead not found
- `500 Internal Server Error` - Server error

---

### 5. Get Feedback History

**GET /feedback/{lead_id}**

Retrieve feedback history for a lead.

**Request:**
```bash
curl http://localhost:8000/feedback/LEAD-001
```

**Response (200 OK):**
```json
{
  "lead_id": "LEAD-001",
  "feedback_count": 3,
  "feedback_history": [
    {
      "feedback_id": "fb-001",
      "outcome": "accepted",
      "reason": "Engaged",
      "created_at": "2025-03-13T10:00:00Z"
    },
    {
      "feedback_id": "fb-002",
      "outcome": "rejected",
      "reason": "Budget constraint",
      "created_at": "2025-03-12T15:30:00Z"
    }
  ]
}
```

**Status Codes:**
- `200 OK` - History retrieved
- `404 Not Found` - Lead not found
- `500 Internal Server Error` - Server error

---

### 6. Trigger Retraining

**POST /retrain**

Manually trigger model retraining based on accumulated feedback.

**Request:**
```bash
curl -X POST http://localhost:8000/retrain \
  -H "Content-Type: application/json" \
  -d {
    "min_feedback_samples": 50,
    "dry_run": false
  }
```

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| min_feedback_samples | number | ❌ | Min feedback before retraining |
| dry_run | boolean | ❌ | Simulate without saving |

**Response (202 Accepted):**
```json
{
  "retrain_job_id": "retrain-2025-03-13-001",
  "status": "queued",
  "estimated_completion": "2025-03-13T13:30:00Z",
  "feedback_samples_used": 145,
  "message": "Retraining job queued. Check /retrain-status/{job_id} for progress."
}
```

**Status Codes:**
- `202 Accepted` - Retrain queued
- `400 Bad Request` - Invalid parameters
- `409 Conflict` - Retraining already in progress
- `500 Internal Server Error` - Server error

---

### 7. Check Drift Status

**GET /drift-status**

Check if model performance has drifted beyond acceptable thresholds.

**Request:**
```bash
curl http://localhost:8000/drift-status
```

**Response (200 OK):**
```json
{
  "status": "warning",
  "drift_detected": true,
  "metrics": {
    "acceptance_rate": 0.58,
    "acceptance_rate_change": -0.12,
    "confidence_score": 0.75,
    "recommendation": "Retrain model - 12% drop in acceptance rate detected"
  },
  "last_retrain": "2025-03-01T10:00:00Z",
  "feedback_count": 250,
  "timestamp": "2025-03-13T12:34:56Z"
}
```

**Response Status Values:**
- `ok` - No drift detected, model performing well
- `warning` - Minor drift detected, monitor closely
- `critical` - Significant drift, retrain recommended

**Status Codes:**
- `200 OK` - Status retrieved
- `500 Internal Server Error` - Server error

---

### 8. Update Drift Settings

**PUT /drift-settings**

Configure drift detection thresholds.

**Request:**
```bash
curl -X PUT http://localhost:8000/drift-settings \
  -H "Content-Type: application/json" \
  -d {
    "acceptance_rate_threshold": 0.50,
    "confidence_threshold": 0.70,
    "max_sal_weight": 0.30,
    "min_feedback_for_retrain": 50
  }
```

**Request Parameters:**

| Parameter | Type | Range | Default | Description |
|-----------|------|-------|---------|-------------|
| acceptance_rate_threshold | number | 0.0-1.0 | 0.50 | Min acceptance rate |
| confidence_threshold | number | 0.0-1.0 | 0.70 | Min confidence |
| max_sal_weight | number | 0.0-1.0 | 0.30 | Max SAL influence |
| min_feedback_for_retrain | number | 1-10000 | 50 | Feedback samples needed |

**Response (200 OK):**
```json
{
  "status": "updated",
  "settings": {
    "acceptance_rate_threshold": 0.50,
    "confidence_threshold": 0.70,
    "max_sal_weight": 0.30,
    "min_feedback_for_retrain": 50
  },
  "message": "Drift detection settings updated successfully."
}
```

**Status Codes:**
- `200 OK` - Settings updated
- `400 Bad Request` - Invalid parameter values
- `500 Internal Server Error` - Server error

---

## Error Handling

### Error Response Format

```json
{
  "status": "error",
  "error_code": "INVALID_INPUT",
  "message": "Invalid email format provided",
  "details": {
    "field": "email",
    "value": "not-an-email",
    "expected": "valid email address"
  },
  "timestamp": "2025-03-13T12:34:56Z"
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| INVALID_INPUT | 400 | Invalid request parameters |
| MISSING_REQUIRED | 422 | Required field missing |
| LEAD_NOT_FOUND | 404 | Lead ID doesn't exist |
| DATABASE_ERROR | 500 | Database connection/query error |
| MODEL_ERROR | 500 | Scoring model error |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Unexpected server error |

---

## Rate Limiting

- **Default**: 1,000 requests/minute per client
- **Burst**: 100 requests/10 seconds
- **Response Header**: `X-RateLimit-Remaining`

```bash
curl -i http://localhost:8000/score
# Returns: X-RateLimit-Remaining: 999
# Returns: X-RateLimit-Limit: 1000
# Returns: X-RateLimit-Reset: 1710328496
```

---

## Pagination

For endpoints returning large result sets:

```bash
GET /results?offset=0&limit=100&sort=-created_at&filter=grade:A
```

**Parameters:**
- `offset` - Number of items to skip
- `limit` - Number of items to return (max 1000)
- `sort` - Sort field (prefix - for descending)
- `filter` - Filter criteria

---

## Webhooks (Optional)

Post-deployment, integrate webhooks for async notifications:

```bash
# Register webhook
POST /webhooks
{
  "url": "https://yoursystem.com/lead-scoring-events",
  "events": ["score.created", "retrain.completed", "drift.detected"]
}

# Event payload
{
  "event": "score.created",
  "lead_id": "LEAD-001",
  "score": 78.5,
  "timestamp": "2025-03-13T12:34:56Z"
}
```

---

## Examples

### Python Client

```python
import requests

api_url = "http://localhost:8000"

# Score a lead
response = requests.post(f"{api_url}/score", json={
    "lead_id": "LEAD-001",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "title": "VP Sales",
    "company_name": "ACME Corp"
})

score = response.json()
print(f"Score: {score['score']}, Grade: {score['grade']}")

# Record feedback
requests.post(f"{api_url}/feedback", json={
    "lead_id": "LEAD-001",
    "outcome": "accepted",
    "reason": "Engaged"
})

# Check drift
drift = requests.get(f"{api_url}/drift-status").json()
print(f"Drift Status: {drift['status']}")
```

### JavaScript/Node.js

```javascript
const apiUrl = "http://localhost:8000";

// Score a lead
const response = await fetch(`${apiUrl}/score`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    lead_id: "LEAD-001",
    email: "john@example.com",
    first_name: "John",
    last_name: "Doe",
    title: "VP Sales",
    company_name: "ACME Corp"
  })
});

const score = await response.json();
console.log(`Score: ${score.score}, Grade: ${score.grade}`);

// Record feedback
await fetch(`${apiUrl}/feedback`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    lead_id: "LEAD-001",
    outcome: "accepted",
    reason: "Engaged"
  })
});
```

### cURL Examples

```bash
# Score a single lead
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"L1","email":"test@example.com","first_name":"John","last_name":"Doe","title":"VP","company_name":"ACME"}'

# Score batch
curl -X POST http://localhost:8000/score-batch \
  -H "Content-Type: application/json" \
  -d '{"leads":[...],"job_name":"batch1"}'

# Check health
curl http://localhost:8000/health

# View API docs (Swagger)
curl http://localhost:8000/docs
```

---

## Versioning

Current API Version: `v1.0.0`

Future versions will use `/v2` prefix to maintain backward compatibility.

---

## Support

- **Documentation**: See README.md
- **Troubleshooting**: See TROUBLESHOOTING.md
- **Issues**: Check GitHub issues
- **Feature Requests**: Submit via GitHub discussions
