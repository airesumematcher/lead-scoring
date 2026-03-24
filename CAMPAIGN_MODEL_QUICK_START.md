# 🚀 CAMPAIGN-AWARE MODEL: 3-Step Quick Start

## ✅ STEP 1: Start Your API (2 minutes)

```bash
cd /Users/schadha/Desktop/lead-scoring
python -m uvicorn src.lead_scoring.api.app:app --reload
```

**You'll see:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

✅ Done! API is now live with campaign-aware scoring!

---

## ✅ STEP 2: Open Dashboard (Pick One)

### OPTION A: 🎨 Beautiful Dashboard (RECOMMENDED)
Open file: **`dashboard.html`** in your browser
- Double-click the file in Finder/Explorer
- Or right-click → Open With → Browser

### OPTION B: 🔧 API Swagger UI
Open: **http://localhost:8000/docs**
- Scroll to "scoring" section  
- Click "POST /score/predict-campaign-aware"
- Click "Try it out"

### OPTION C: 💻 Command Line
```bash
curl -X POST "http://localhost:8000/score/predict-campaign-aware" \
  -H "Content-Type: application/json" \
  -d '{
    "is_executive": 1,
    "company_size_score": 8,
    "total_engagement_score": 4,
    "campaign_mode": "prospecting"
  }'
```

---

## ✅ STEP 3: Understand Your Score

### You'll get back:
```json
{
  "score": 88,
  "confidence": 92,
  "fit_score": 88,
  "intent_score": 85,
  "campaign_quality_score": 85,
  "reasoning": "Executive level | Company size: 8/8 | Engagement: 4/4"
}
```

### Score Meaning:
- **0-40** = 🔴 Poor fit
- **40-60** = 🟡 Medium
- **60-80** = 🟠 Good
- **80-100** = 🟢 Excellent (contact!)

### What Each Score Means:
| Score | What It Measures | Example |
|-------|-----------------|---------|
| **score (88)** | FINAL lead score | "Worth reaching out to" |
| **confidence (92)** | How sure we are | "92% confident in this score" |
| **fit_score (88)** | Company + role match | "Fortune 500 + VP = great fit" |
| **intent_score (85)** | Email engagement | "Opened & clicked emails" |
| **campaign_quality (85)** | Asset quality | "Good case study" |

---

## 🎯 Campaign Mode Cheat Sheet

Pick the right mode for YOUR situation:

### MODE 1: PROSPECTING (Cold Calling)
```
Use when: "I'm calling someone I found on LinkedIn"

Weighting: Fit (70%) > Intent (20%)

Sample lead:
  is_executive: 1 (VP)
  company_size: 8 (Fortune 500)
  total_engagement: 0 (never opened email)
  mode: "prospecting"

Result: Score 66 ✓ (Worth calling! Fit is good)
```

### MODE 2: ENGAGEMENT (Nurture Existing)
```
Use when: "They opened/clicked our emails, let's nurture"

Weighting: Intent (50%) > Fit (40%)

Sample lead:
  is_executive: 0 (Analyst)
  company_size: 5 (Mid-market)
  total_engagement: 4 (opened + clicked both)
  mode: "engagement"

Result: Score 75 ✓ (High! Engagement matters here)
```

### MODE 3: NURTURE (Premium Events)
```
Use when: "Inviting to executive summit/webinar"

Weighting: Campaign Quality (40%) is primary

Sample lead:
  campaign_quality_score: 95 (premium summit)
  mode: "nurture"

Result: Score 78+ ✓ (Premium event justifies inclusion)
```

### MODE 4: DEFAULT (Not Sure)
```
Use when: "I don't know which mode to pick"

Weighting: Fit (60%) + Intent (30%) + Campaign (10%)

Result: Safe middle ground
```

---

## 🧪 Test with These Examples

Copy/paste into dashboard to test:

### Example 1: Cold VP (best for prospecting)
```
Role: Executive
Company Size: 8
Email 1: Not opened (0)
Email 2: Not opened (0)
Campaign Mode: prospecting

Expected: ~66 (good despite no engagement)
```

### Example 2: Engaged Analyst (best for engagement)
```
Role: IC
Company Size: 5
Email 1: 2 (opened + clicked)
Email 2: 2 (opened + clicked)
Campaign Mode: engagement

Expected: ~75 (high due to engagement)
```

### Example 3: Premium Event (any lead)
```
Any role, any company
Campaign Mode: nurture

Expected: 75+ if campaign quality is premium
```

---

## 📚 Full Guides (Read These Next)

| File | Read This For |
|------|---------------|
| `CAMPAIGN_AWARE_MODEL_GUIDE.md` | Complete technical reference |
| `CAMPAIGN_MODE_DECISION_FRAMEWORK.py` | Detailed decision tree |
| `STEP_BY_STEP_GUIDE.py` | In-depth interpretation guide |
| `README_CAMPAIGN_AWARE_MODEL.md` | Executive summary |

---

## ❓ FAQ

**Q: "My score is 45, is that bad?"**
A: Depends on context! In PROSPECTING mode, 45 = lower priority. In ENGAGEMENT mode with bad fit but good intent, it's expected. Check the fit_score and intent_score separately.

**Q: "How do I score 100 leads at once?"**
A: Use batch endpoint in Swagger: `POST /score/batch-predict-campaign-aware`

**Q: "Can I use this in Salesforce?"**
A: Yes! Call the API from Salesforce Flow or Zapier.
Endpoint: `http://YOUR_SERVER:8000/score/predict-campaign-aware`

**Q: "How do I improve my scores?"**
A: Rerun data prep with more training data:
```bash
python3 scripts/01_data_prep_enhanced.py
python3 scripts/02_train_ml_model_enhanced.py
```

---

## 🎉 You're Ready!

1. Terminal: `python -m uvicorn src.lead_scoring.api.app:app --reload`
2. Browser: Open `dashboard.html`
3. Form: Fill in a lead
4. Click: "Score Lead"
5. See: Score + Interpretation!

**Congrats! Your campaign-aware model is live! 🚀**
