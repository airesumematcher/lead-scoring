# LLM Lead Scoring Model - Strategic Plan

## 📊 Data Overview

### Source 1: Lead Engagement Data (CSV - 661 leads)
**File:** `Lead Score_Lead Outreach Results Pivots(Sheet1) (1).csv`

| Aspect | Details |
|--------|---------|
| **Records** | 661 leads |
| **Target Variable** | Lead Score (68.7-100, 613 non-null) |
| **Company Info** | 8 size categories (Micro to XXLarge) |
| **Role Info** | Job Title + Job Function (Finance, IT, Operations, etc.) |
| **Engagement Signals** | 2 email campaigns tracked |
| **Email Metrics** | Opens, Clicks, Unsubscribes per email |
| **Data Quality** | 92.7% complete |

**Key Columns for LLM:**
- `Lead Email` - Identifier
- `Job Title` - Role signal
- `Company Size` - Organization scale
- `Job Function` - Department/function
- `Email 1-2 Opens/Clicks/Unsubs` - Engagement intent

### Source 2: Campaign Analytics (Excel - 124,933 records)
**File:** `Lead_scoring_analysis.xlsx`

| Aspect | Details |
|--------|---------|
| **Records** | 124,933 records |
| **Key Fields** | Partner ID, Campaign ID, Audit Status, Approval Dates |
| **Use Case** | Historical lead delivery & campaign context |
| **Grain** | Weekly reporting |

---

## 🤖 LLM Model Architecture

### **Approach: Hybrid Intelligence Scoring**

```
Raw Lead Data
    ↓
[1] Feature Extraction → Company Size, Role Seniority, Function
    ↓
[2] Lead Narrative Generation → "Engineer at Fortune 500 company engaging with 2/2 emails"
    ↓
[3] LLM Analysis → OpenAI GPT-4 / Claude for semantic understanding
    ↓
[4] Combined Scoring → LLM reasoning + engagement metrics
    ↓
[5] Lead Score Prediction → 0-100 priority score
```

---

## 🎯 Three Implementation Options

### **Option A: Pure LLM Scoring (Simplest)**
**Use Case:** No historical training data needed

```python
# Pseudo-code
lead_narrative = f"""
Candidate: {job_title} at {company_size} company
Function: {job_function}
Engagement: {email_opens} email opens, {email_clicks} clicks
Company Scale: {company_size}
Recent Activity: {last_activity_date}
"""

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{
        "role": "system",
        "content": "You are a B2B lead scoring expert. Score leads 0-100 based on seniority, company size, engagement."
    }, {
        "role": "user",
        "content": f"Score this lead:\n{lead_narrative}"
    }]
)

score = extract_score_from_response(response)
```

**Pros:** Quick to implement, no training required
**Cons:** Costs per API call, less consistent than trained models

---

### **Option B: LLM Feature Extraction + Traditional ML (Recommended)**
**Use Case:** Combine best of both worlds

```python
# Step 1: LLM extracts features from unstructured data
llm_features = {
    "seniority_level": llm.extract("Is this person C-suite/manager/IC?"),
    "decision_maker_likelihood": llm.extract("Is this likely a buying decision maker?"),
    "engagement_intent": llm.extract("Does engagement pattern suggest genuine interest?"),
    "budget_authority": llm.extract("Role typically has budget authority?")
}

# Step 2: Combine with raw engagement metrics
features = {
    **llm_features,  # LLM-derived semantic features
    "email_open_rate": email_opens / email_attempts,
    "click_through_rate": email_clicks / email_opens,
    "days_since_engagement": (today - last_engagement).days,
    "company_size_score": size_mapping[company_size]
}

# Step 3: Use existing trained model or gradient boosting
score = trained_model.predict([features])
```

**Pros:** Leverages historical data, explainable, cost-efficient at scale
**Cons:** Requires initial training data

---

### **Option C: Fine-Tuned LLM (Most Accurate)**
**Use Case:** Maximum accuracy with your specific lead patterns

```python
# Fine-tune on 600+ leads with known scores
training_data = [
    {
        "prompt": lead_narrative_1,
        "completion": actual_lead_score_1
    },
    ...  # 600+ examples
]

fine_tuned_model = openai.FineTune.create(
    training_file=upload_jsonl(training_data),
    model="gpt-3.5-turbo"
)

# Score new leads
score = fine_tuned_model.predict(new_lead_narrative)
```

**Pros:** Custom-tuned to your data, highest accuracy
**Cons:** Requires 600+ labeled examples, higher cost

---

## 📋 Detailed Implementation Plan

### **Phase 1: Data Preparation (Week 1)**
```
✅ Load CSV from sample_data/
✅ Clean engagement columns (convert Yes/No to binary)
✅ Engineer features:
   - seniority_score: Extract from job title
   - company_size_score: Ordinal encode
   - engagement_rate: (opens + clicks) / 2
   - recency: Days since last activity
✅ Create lead narratives for LLM
```

### **Phase 2: LLM Integration (Week 1-2)**

**Choose: Start with Option B (recommended)**

```python
# New module: src/lead_scoring/llm/feature_extractor.py

from openai import OpenAI

class LLMFeatureExtractor:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
    
    def extract_features(self, lead_profile):
        """
        Input: Lead metadata
        Output: LLM-derived features
        """
        prompt = f"""
Analyze this B2B lead and provide structured assessment:

Lead Profile:
- Job Title: {lead_profile['job_title']}
- Company Size: {lead_profile['company_size']}
- Job Function: {lead_profile['job_function']}
- Email Opens: {lead_profile['email_opens']}
- Email Clicks: {lead_profile['email_clicks']}

Respond as JSON:
{{
    "seniority_level": "C-level|Manager|Individual Contributor",
    "decision_maker_score": 0-100,  # likelihood of buying decision
    "engagement_intent": "high|medium|low",
    "engagement_score": 0-100,  # based on email behavior
    "company_tier": "enterprise|mid-market|small",
    "fit_explanation": "brief reason for scoring"
}}
"""
        response = self.client.chat.completions.create(
            model="gpt-4",
            response_format={ "type": "json_object" },
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.choices[0].message.content)
    
    def batch_score(self, leads_df, sample_size=100):
        """Score sample of leads to validate approach"""
        results = []
        for idx, lead in leads_df.head(sample_size).iterrows():
            features = self.extract_features({
                'job_title': lead['Job Title'],
                'company_size': lead['Company Size'],
                'job_function': lead['Job Function'],
                'email_opens': sum([
                    1 for col in ['Email 1 - Opened', 'Email 2 - Open']
                    if lead[col] == 'Yes'
                ]),
                'email_clicks': sum([
                    1 for col in ['Email 1 - Clicked', 'Email 2 - Clicked']
                    if lead[col] == 'Yes'
                ])
            })
            results.append(features)
        return pd.DataFrame(results)
```

### **Phase 3: Model Training (Week 2-3)**

```python
# src/lead_scoring/llm/hybrid_scorer.py

from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

class HybridLeadScorer:
    def __init__(self):
        self.llm_extractor = LLMFeatureExtractor()
        self.gb_model = GradientBoostingRegressor()
        self.scaler = StandardScaler()
    
    def prepare_training_data(self, leads_df):
        """Prepare features for model training"""
        
        # Get LLM features for all leads
        llm_features = self.llm_extractor.batch_score(leads_df)
        
        # Engineer traditional features
        traditional_features = pd.DataFrame({
            'company_size_num': leads_df['Company Size'].map(self.size_to_num),
            'email_open_rate': leads_df.apply(
                lambda x: sum([x['Email 1 - Opened'], x['Email 2 - Open']]) / 2 
                if pd.notna(x['Email 1 - Opened']) else 0, axis=1
            ),
            'click_rate': leads_df.apply(
                lambda x: sum([x['Email 1 - Clicked'], x['Email 2 - Clicked']]) / 2
                if pd.notna(x['Email 1 - Clicked']) else 0, axis=1
            ),
        })
        
        # Combine
        combined_features = pd.concat([llm_features, traditional_features], axis=1)
        combined_features = combined_features.fillna(combined_features.mean())
        
        return combined_features
    
    def train(self, leads_df):
        """Train model on historical leads"""
        features = self.prepare_training_data(leads_df)
        target = leads_df['Lead Score'].dropna()
        
        # Align features with non-null targets
        features = features.loc[target.index]
        
        # Normalize
        features_scaled = self.scaler.fit_transform(features)
        
        # Train
        self.gb_model.fit(features_scaled, target)
        
        return self  # For chaining
    
    def score_lead(self, lead_dict):
        """Predict score for single lead"""
        llm_feat = self.llm_extractor.extract_features(lead_dict)
        trad_feat = self.engineer_features(lead_dict)
        
        combined = {**llm_feat, **trad_feat}
        features_scaled = self.scaler.transform([combined])
        
        return self.gb_model.predict(features_scaled)[0]
    
    def size_to_num(self, size_str):
        mapping = {
            'Micro (1 - 9 Employees)': 1,
            'Small (10 - 49 Employees)': 2,
            'Medium-Small (50 - 199 Employees)': 3,
            'Medium (200 - 499 Employees)': 4,
            'Medium-Large (500 - 999 Employees)': 5,
            'Large (1,000 - 4,999 Employees)': 6,
            'XLarge (5,000 - 10,000 Employees)': 7,
            'XXLarge (10,000+ Employees)': 8,
        }
        return mapping.get(size_str, 4)
```

### **Phase 4: API Integration (Week 3)**

```python
# src/lead_scoring/api/llm_endpoints.py

@router.post("/score-with-llm")
async def score_with_llm(lead: LeadInput):
    """
    Score a lead using hybrid LLM + ML approach
    
    Response includes:
    - score: 0-100 lead priority
    - llm_reasoning: Why LLM chose this score
    - confidence: 0-1 model confidence
    - factors: Top 3 factors driving score
    """
    
    lead_dict = lead.dict()
    
    # Get LLM featuresand reasoning
    llm_features = llm_extractor.extract_features(lead_dict)
    
    # Get model score
    model_score = hybrid_scorer.score_lead(lead_dict)
    
    # Explain prediction
    feature_importance = hybrid_scorer.gb_model.feature_importances_
    top_factors = sorted(
        zip(feature_names, feature_importance),
        key=lambda x: x[1],
        reverse=True
    )[:3]
    
    return {
        "lead_email": lead.email,
        "score": float(model_score),
        "confidence": float(hybrid_scorer.gb_model.score(features_test)),
        "llm_reasoning": llm_features.get('fit_explanation', ''),
        "top_factors": [
            {"factor": f, "importance": float(i)} 
            for f, i in top_factors
        ],
        "timestamp": datetime.now().isoformat()
    }
```

---

## 💼 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Accuracy** | R² > 0.75 | Compare predicted vs actual scores |
| **Precision (Top 20%)** | > 80% | Of leads scored 80+, how many convert? |
| **Latency** | < 2 sec/lead | API response time |
| **Cost** | < $0.01/lead | LLM API calls at scale |
| **Explainability** | 100% | Every score has reasoning |

---

## 🚀 Quick Start (Next Steps)

1. **Today:** Load data and create lead narratives
   ```python
   # scripts/01_data_prep.py
   leads_df = pd.read_csv("sample_data/Lead Score_Lead Outreach Results Pivots(Sheet1) (1).csv")
   leads_df['narrative'] = leads_df.apply(create_narrative, axis=1)
   ```

2. **This Week:** Test LLM extraction on sample
   ```python
   # scripts/02_test_llm.py
   extractor = LLMFeatureExtractor(api_key)
   sample_features = extractor.batch_score(leads_df, sample_size=50)
   ```

3. **Next Week:** Train hybrid model
   ```python
   # scripts/03_train_model.py
   scorer = HybridLeadScorer()
   scorer.train(leads_df)
   scorer.gb_model.save("models/lead_scorer.pkl")
   ```

4. **Deploy:** Add to existing API
   ```python
   # Integrate into /score endpoint in src/lead_scoring/api/app.py
   ```

---

## 📝 Questions to Clarify

1. **OpenAI API Access?** Do you have GPT-4 access or should we use GPT-3.5-turbo?
2. **Budget:** Cost per API call acceptable? (GPT-4: $0.03/call, GPT-3.5: $0.001/call)
3. **Target Variable:** Is "Lead Score" (68.7-100) the actual conversion score, or should we engineer a binary target?
4. **Real-time or Batch:** Should scoring be API endpoint or batch daily job?
5. **Explainability:** How important is it to show why a lead got scored X vs Y?

---

## 🎯 Estimated Timeline

| Phase | Duration | Effort | Deliverable |
|-------|----------|--------|------------|
| **1. Data Prep** | 2-3 days | Medium | Clean data + narratives |
| **2. LLM Testing** | 3-5 days | Low | Proof of concept |
| **3. Model Train** | 5-7 days | High | Trained hybrid model |
| **4. API Deploy** | 3-5 days | Medium | Production endpoint |
| **Total** | **2-3 weeks** | **High** | **Full LLM Scoring System** |

---

## Would You Like Me To...

- [ ] **Start Phase 1:** Data prep and narrative generation
- [ ] **Start Phase 2:** Build LLM feature extractor
- [ ] **Analyze Option A vs B vs C:** Compare approaches for your data
- [ ] **Set up OpenAI access:** Configuration and cost estimation
- [ ] **Create Jupyter notebook:** Interactive exploration of data

What would you like to tackle first?
