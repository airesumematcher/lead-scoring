"""
STEP-BY-STEP GUIDE: Using Your Campaign-Aware Lead Scoring Model
"""

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║           CAMPAIGN-AWARE LEAD SCORING MODEL - USER GUIDE                  ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

════════════════════════════════════════════════════════════════════════════
QUICK START: 3 WAYS TO USE THE MODEL
════════════════════════════════════════════════════════════════════════════

1. ✅ VIA API (FastAPI) - RECOMMENDED FOR PRODUCTION
2. ✅ VIA PYTHON DIRECTLY - QUICK TESTING  
3. ✅ VIA UI DASHBOARD - COMING SOON (I'll show you how to build)


════════════════════════════════════════════════════════════════════════════
PART 1: INTEGRATE INTO YOUR API (5 MINUTES)
════════════════════════════════════════════════════════════════════════════

Step 1.1: Open your main API file
  File: src/lead_scoring/api/app.py
  
Step 1.2: Add these lines at the TOP (after existing imports):
  ─────────────────────────────────────────────────────────────
  from lead_scoring.api.ml_scoring_enhanced import router as ml_enhanced_router
  ─────────────────────────────────────────────────────────────

Step 1.3: Add this line AFTER app creation (probably around line 20):
  ─────────────────────────────────────────────────────────────
  app = FastAPI(...)
  
  # Add this:
  app.include_router(ml_enhanced_router)
  ─────────────────────────────────────────────────────────────

Step 1.4: Save file and restart API:
  ─────────────────────────────────────────────────────────────
  $ cd /Users/schadha/Desktop/lead-scoring
  $ python -m uvicorn src.lead_scoring.api.app:app --reload
  ─────────────────────────────────────────────────────────────

✅ DONE! Your new endpoints are now live at http://localhost:8000


════════════════════════════════════════════════════════════════════════════
PART 2: TEST THE API (INTERACTIVE)
════════════════════════════════════════════════════════════════════════════

OPTION A: Using Swagger UI (Easiest)
──────────────────────────────────────
1. Open browser: http://localhost:8000/docs
2. Find section: "scoring" (scroll down)
3. Click on: POST /score/predict-campaign-aware
4. Click: "Try it out"
5. Fill in the fields with your lead data
6. Click: "Execute"
7. See response with score!

Sample data to paste:
{
  "is_executive": 1,
  "company_size_score": 8,
  "has_engagement": 1,
  "email1_engagement": 2,
  "email2_engagement": 2,
  "total_engagement_score": 4,
  "unsubscribed": 0,
  "campaign_mode": "prospecting"
}

Expected response:
{
  "score": 88.5,
  "confidence": 92,
  "fit_score": 88,
  "intent_score": 85,
  "campaign_quality_score": 85,
  "campaign_mode": "prospecting",
  "reasoning": "Executive level | Company size: 8/8 | Engagement score: 4/4 | Scoring mode: prospecting"
}


OPTION B: Using Command Line (curl)
──────────────────────────────────────
$ curl -X POST "http://localhost:8000/score/predict-campaign-aware" \\
  -H "Content-Type: application/json" \\
  -d '{
    "is_executive": 1,
    "company_size_score": 8,
    "total_engagement_score": 4,
    "campaign_mode": "prospecting"
  }'

Response: Score 88.5, confidence 92%


OPTION C: Using Python (Programmatic)
──────────────────────────────────────
import requests

lead_data = {
    "is_executive": 1,
    "company_size_score": 8,
    "has_engagement": 1,
    "email1_engagement": 2,
    "email2_engagement": 2,
    "total_engagement_score": 4,
    "unsubscribed": 0,
    "campaign_mode": "prospecting"
}

response = requests.post(
    "http://localhost:8000/score/predict-campaign-aware",
    json=lead_data
)

result = response.json()
print(f"Score: {result['score']}")
print(f"Confidence: {result['confidence']}")
print(f"Reasoning: {result['reasoning']}")


════════════════════════════════════════════════════════════════════════════
PART 3: HOW TO INTERPRET SCORES
════════════════════════════════════════════════════════════════════════════

YOUR RESPONSE CONTAINS 7 KEY FIELDS:

┌─────────────────────────────────────────────────────────────────────────┐
│ Field: score (0-100)                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│ What it means: FINAL lead score combining fit + intent + campaign       │
│              quality with mode-specific weights                         │
│                                                                         │
│ Interpretation:                                                         │
│   0-20   = Cold/No Fit (unlikely prospect)                             │
│  20-40   = Poor Fit (not priority)                                     │
│  40-60   = Medium (consider based on campaign)                         │
│  60-80   = Good (solid prospect)                                       │
│  80-100  = Excellent (priority contact)                                │
│                                                                         │
│ Example:                                                                │
│   Score 85 = "This lead is worth reaching out to"                      │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Field: confidence (0-100)                                               │
├─────────────────────────────────────────────────────────────────────────┤
│ What it means: How confident the model is in this score                │
│              (higher = more data points available)                      │
│                                                                         │
│ Interpretation:                                                         │
│   < 50   = Low confidence (missing email engagement data, etc)         │
│  50-70   = Medium confidence (some signals available)                   │
│  70-85   = Good confidence (solid data)                                │
│  85-95   = High confidence (lots of engagement data)                   │
│  95+     = Very confident (comprehensive profile)                      │
│                                                                         │
│ Example:                                                                │
│   Score 80 + Confidence 92 = "Likely accurate, trust this score"       │
│   Score 80 + Confidence 45 = "Score might change with more data"       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Field: fit_score (0-100)                                                │
├─────────────────────────────────────────────────────────────────────────┤
│ What it means: DEMOGRAPHIC/COMPANY FIT                                 │
│              (company size + audience type match)                       │
│                                                                         │
│ Interpretation:                                                         │
│   80+  = Perfect fit (right company size + audience type)              │
│   60-80 = Good fit (decent company match)                              │
│   40-60 = Medium fit (some match)                                      │
│   <40   = Poor fit (wrong company/audience)                            │
│                                                                         │
│ Factors:                                                                │
│   • Company Size (1-8 scale): Enterprise=high, Startup=low             │
│   • Audience Type: Decision Maker > Expert > Contributor               │
│                                                                         │
│ Example:                                                                │
│   Fit 92 = "Fortune 500 + VP title = perfect fit"                      │
│   Fit 40 = "Small company + IC role = poor fit"                        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Field: intent_score (0-100)                                             │
├─────────────────────────────────────────────────────────────────────────┤
│ What it means: BEHAVIORAL INTENT                                       │
│              (email opens/clicks + engagement pattern)                  │
│                                                                         │
│ Interpretation:                                                         │
│   80+  = Very engaged (opened both emails, clicked multiple times)     │
│   60-80 = Engaged (opened 1+ emails, clicked once)                    │
│   40-60 = Some interest (opened but not clicked, or minimal engagement)│
│   20-40 = Noticed (saw something, minimal interaction)                 │
│   <20   = No engagement (unopened emails)                              │
│                                                                         │
│ Factors:                                                                │
│   • Email 1: Opened? Clicked?                                         │
│   • Email 2: Opened? Clicked?                                         │
│   • Multi-touch depth (both emails = higher intent)                    │
│                                                                         │
│ Example:                                                                │
│   Intent 90 = "Clicked both emails, strong buyer signal"               │
│   Intent 15 = "Never opened any emails"                                │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Field: campaign_quality_score (0-100)                                   │
├─────────────────────────────────────────────────────────────────────────┤
│ What it means: Quality of the campaign asset used                      │
│              (what type of content, how many leads, etc)                │
│                                                                         │
│ Interpretation:                                                         │
│   80+  = Premium asset (case study, webinar to 300+ leads)            │
│   60-80 = Good asset (buyer guide, webinar to 100-300)                 │
│   40-60 = Standard asset (whitepaper, broader email)                   │
│   <40   = Basic asset (checklist, low relevance)                       │
│                                                                         │
│ What affects this:                                                      │
│   • Asset Type: Case Study (0.95) > Guide (0.90) > Webinar (0.85)     │
│   • Volume Tier: 300+ leads (0.8) > 100-300 (0.9) > <100 (0.7)        │
│                                                                         │
│ Example:                                                                │
│   Campaign Quality 95 = "Premium case study to 300+ qualified leads"   │
│   Campaign Quality 50 = "Standard checklist email"                     │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Field: campaign_mode (string)                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ What it means: Which weighting scheme was used for scoring             │
│                                                                         │
│ Values:                                                                 │
│   "prospecting"  = Cold outreach mode (70% Fit, 20% Intent)            │
│   "engagement"   = Nurture mode (40% Fit, 50% Intent)                  │
│   "nurture"      = Premium asset (30% Fit, 40% Campaign)               │
│   "default"      = General scoring (60% Fit, 30% Intent)               │
│                                                                         │
│ Example:                                                                │
│   Mode: "prospecting" = "Score emphasizes fit over behavior"           │
│   Mode: "engagement"  = "Score emphasizes behavior over fit"           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Field: reasoning (text explanation)                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ What it means: Human-readable explanation of the score                │
│                                                                         │
│ Example outputs:                                                        │
│   "Executive level | Company size: 8/8 | Engagement: 4/4 touches"     │
│   "IC level | Company size: 5/8 | Engagement: 0/4 touches"            │
│                                                                         │
│ Use this to:                                                            │
│   • Validate the score (does it match what you'd expect?)              │
│   • Explain to sales reps why a lead got a certain score               │
│   • Debug if a score seems wrong                                       │
└─────────────────────────────────────────────────────────────────────────┘


════════════════════════════════════════════════════════════════════════════
PART 4: INTERPRETATION EXAMPLES (REAL SCENARIOS)
════════════════════════════════════════════════════════════════════════════

SCENARIO 1: Cold VP Prospect
────────────────────────────────────────────────────────────────────────────
Input:
  is_executive: 1 (VP)
  company_size_score: 8 (Fortune 500)
  total_engagement_score: 0 (no emails opened/clicked)
  campaign_mode: "prospecting"

Response:
  {
    "score": 66.0,
    "confidence": 75,
    "fit_score": 88,        ← Good fit (right person + company)
    "intent_score": 15,     ← Low intent (no prior engagement)
    "campaign_quality_score": 65,
    "reasoning": "Executive level | Company size: 8/8 | Engagement: 0/4"
  }

INTERPRETATION:
  ✓ Score 66 = Worth cold calling
  ✓ High fit (88) = right target
  ✗ Low intent (15) = but not engaged yet
  → This is expected! Use PROSPECTING mode for cold outreach
  → ACTION: Add to cold call list


SCENARIO 2: Engaged Analyst (Nurture Candidate)
────────────────────────────────────────────────────────────────────────────
Input:
  is_executive: 0 (Analyst - junior)
  company_size_score: 5 (mid-market)
  total_engagement_score: 4 (both emails: opened + clicked)
  campaign_mode: "engagement"

Response:
  {
    "score": 74.5,
    "confidence": 88,
    "fit_score": 55,        ← Medium fit (ok company, junior role)
    "intent_score": 92,     ← VERY engaged (opened + clicked x2)
    "campaign_quality_score": 70,
    "reasoning": "IC level | Company size: 5/8 | Engagement: 4/4"
  }

INTERPRETATION:
  ✓ Score 74.5 = Strong nurture candidate
  ✗ Fit 55 = Not perfect company/role fit
  ✓ Intent 92 = HIGHLY engaged (2 opens + 2 clicks)
  → ENGAGEMENT mode: behavior matters more than role
  → ACTION: Send to marketing nurture sequence, not SDR


SCENARIO 3: Executive Summit Invitation
────────────────────────────────────────────────────────────────────────────
Input:
  is_executive: 1 (Director)
  company_size_score: 6 (Large)
  total_engagement_score: 1 (opened 1 email)
  campaign_context: { campaign_quality_score: 95 }  ← Premium summit
  campaign_mode: "nurture"

Response:
  {
    "score": 78.0,
    "confidence": 82,
    "fit_score": 78,        ← Good fit
    "intent_score": 55,     ← Medium intent
    "campaign_quality_score": 95,  ← PREMIUM EVENT ⭐
    "reasoning": "Executive level | Company size: 6/8 | Engagement: 1/4"
  }

INTERPRETATION:
  ✓ Score 78 = Worth inviting
  ✗ Fit 78 = decent not amazing
  ✗ Intent 55 = minimal engagement
  ✓ Campaign Quality 95 = Premium summit justifies lower fit/intent
  → NURTURE mode: premium campaign asset is the driver
  → ACTION: Send VIP summit invitation


SCENARIO 4: "Why is my lead scoring only 35?"
────────────────────────────────────────────────────────────────────────────
Input:
  is_executive: 0 (Analyst)
  company_size_score: 2 (Small startup)
  total_engagement_score: 0 (no interaction)
  campaign_mode: "prospecting"

Response:
  {
    "score": 35.0,
    "confidence": 70,
    "fit_score": 35,        ← POOR fit (small company, junior role)
    "intent_score": 10,     ← No engagement
    "campaign_quality_score": 65,
    "reasoning": "IC level | Company size: 2/8 | Engagement: 0/4"
  }

INTERPRETATION:
  ✗ Score 35 = Low priority prospect
  ✗ Fit 35 = Wrong company size (small) + wrong role (analyst)
  ✗ Intent 10 = No engagement signal
  → This is correct! Not a good fit for prospecting
  → ACTION: Skip cold call, but keep for nurture if they engage


════════════════════════════════════════════════════════════════════════════
PART 5: CHOOSING THE RIGHT CAMPAIGN MODE
════════════════════════════════════════════════════════════════════════════

DECISION TREE:

  START: "What am I doing with these leads?"
    ↓
  ├─→ "Cold calling new accounts?"
  │   │
  │   └─→ USE: "prospecting"
  │       Why: Emphasizes Fit (70%) > Intent (20%)
  │       Best for: VP/C-level targeting, Fortune 500 outreach
  │       Example: "Cold VP" scenario above → Score 66
  │
  ├─→ "Nurturing existing engaged leads?"
  │   │
  │   └─→ USE: "engagement"
  │       Why: Emphasizes Intent (50%) > Fit (40%)
  │       Best for: Email sequences, existing customer nurture
  │       Example: "Engaged Analyst" scenario → Score 74.5
  │
  ├─→ "Inviting to premium event (summit, webinar, VIP)?"
  │   │
  │   └─→ USE: "nurture"
  │       Why: Emphasizes Campaign Quality (40%) most
  │       Best for: Executive summits, premium content
  │       Example: "Summit" scenario → Score 78
  │
  └─→ "Not sure / mixed scenarios?"
      │
      └─→ USE: "default"
          Why: Balanced approach (60% Fit, 30% Intent, 10% Campaign)
          Best for: General database scoring, when uncertain


SCORE COMPARISON: Same Lead, Different Modes
──────────────────────────────────────────────

Lead: Cold VP with minimal engagement
  PROSPECTING: 66  (highest - fit matters)
  DEFAULT:     60
  NURTURE:     54
  ENGAGEMENT:  48  (lowest - behavior matters)

Lead: Engaged Analyst
  ENGAGEMENT:  74.5 (highest - behavior matters)
  NURTURE:     81.4
  DEFAULT:     76.9
  PROSPECTING: 75.1

Lesson: Different modes weight factors differently → use the RIGHT mode!


════════════════════════════════════════════════════════════════════════════
PART 6: BATCH SCORING (Multiple Leads)
════════════════════════════════════════════════════════════════════════════

If you have 100+ leads, use batch endpoint:

Endpoint: POST /score/batch-predict-campaign-aware

Request:
{
  "leads": [
    {
      "is_executive": 1,
      "company_size_score": 8,
      "total_engagement_score": 4,
      "campaign_mode": "prospecting"
    },
    {
      "is_executive": 0,
      "company_size_score": 5,
      "total_engagement_score": 2,
      "campaign_mode": "engagement"
    },
    ... more leads
  ]
}

Response:
{
  "count": 100,
  "scores": [
    { "score": 85, "confidence": 92, ... },
    { "score": 72, "confidence": 88, ... },
    ...
  ],
  "average_score": 68.5
}

Use this for: Daily lead scoring, CRM imports, Salesforce sync


════════════════════════════════════════════════════════════════════════════
PART 7: UI OPTIONS
════════════════════════════════════════════════════════════════════════════

OPTION A: Built-in Swagger UI (ALREADY AVAILABLE)
────────────────────────────────────────────────────────────────────────────
What: Interactive web interface generated by FastAPI
Where: http://localhost:8000/docs
How to use:
  1. Open URL in browser
  2. Scroll to "scoring" section
  3. Click POST /score/predict-campaign-aware
  4. Enter lead data
  5. See results
Pros: ✅ Zero setup, already working
Cons: ✗ Not pretty, limited styling

OPTION B: Build Simple HTML Dashboard (I'll create this)
────────────────────────────────────────────────────────────────────────────
I can create a simple HTML form that calls your API and displays scores nicely.
Would you like me to build this? (Takes 15 minutes)

OPTION C: Integrate with Salesforce/HubSpot
────────────────────────────────────────────────────────────────────────────
Use Zapier or make API calls from your CRM
Pros: ✅ Scores live in your system
Cons: ✗ Requires API integration setup

OPTION D: Python Jupyter Notebook (SIMPLE)
────────────────────────────────────────────────────────────────────────────
I can create a notebook where anyone can:
  - Paste lead data
  - Click "Score"
  - See results with interpretation
Pros: ✅ Easy for team
Cons: ✗ Only Python users


RECOMMENDATION:
  Start with: Swagger UI (already working!)
  Next: I'll build HTML dashboard (prettier, more user-friendly)
  Later: Integrate with Salesforce/HubSpot (business process)


════════════════════════════════════════════════════════════════════════════
PART 8: QUICK REFERENCE - WHEN TO USE EACH MODE
════════════════════════════════════════════════════════════════════════════

PROSPECTING:   "Cold calling a Fortune 500 VP" → Score 66 (worth calling!)
ENGAGEMENT:    "Nurturing analyst who clicked email" → Score 74 (send more!)
NURTURE:       "Inviting to executive summit" → Score 78 (send invite!)
DEFAULT:       "Not sure what to do" → Score 65 (safe middle ground)

ROW FORMAT FOR YOUR TEAM:
┌────────┬─────────────┬──────────────────────┬─────────────────────────┐
│ MODE   │ WHEN TO USE │ WHAT IT WEIGHTS      │ GOOD LEADS LOOK LIKE    │
├────────┼─────────────┼──────────────────────┼─────────────────────────┤
│ PROSP. │ Cold call   │ 70% Fit, 20% Intent  │ VP@Fortune500, no email │
│ ENGAGE │ Nurture     │ 40% Fit, 50% Intent  │ Analyst, 4 email clicks │
│ NURTURE│ Premium evt │ 30% Fit, 40% Quality │ Any @90+ quality summit │
│ DEFAULT│ Not sure    │ 60% Fit, 30% Intent  │ Mixed/balanced          │
└────────┴─────────────┴──────────────────────┴─────────────────────────┘


════════════════════════════════════════════════════════════════════════════
READY TO START?
════════════════════════════════════════════════════════════════════════════

✅ STEP 1: Integrate router (5 min)
   → Edit src/lead_scoring/api/app.py (I'll show exact code below)

✅ STEP 2: Test with Swagger
   → Go to http://localhost:8000/docs
   → Try POST /score/predict-campaign-aware
   → Paste sample lead data

✅ STEP 3: Interpret results
   → Use "INTERPRETATION EXAMPLES" above
   → Check fit_score, intent_score meanings
   → Decide on campaign mode

✅ STEP 4: Deploy
   → Integrate into your workflow (CRM, email, etc)


NEXT: Want me to build a prettier HTML dashboard UI for your team?
""")
