# Phase 1 Complete ✅ - Next Steps

## 📊 What We Just Did

Phase 1 successfully processed your 661 leads:

```
✅ Loaded lead data
✅ Cleaned engagement metrics (Yes/No → Binary)
✅ Engineered 7 features for modeling
✅ Created lead narratives for LLM
✅ Saved 613 leads with actual scores for training
```

### Output Files
```
data_processed/
├── leads_with_narratives.parquet    # Full dataset with narratives
├── features.csv                     # 613 leads × 7 features
├── targets.csv                      # Actual lead scores
├── feature_names.json               # Feature column names
└── sample_narratives.json           # 10 sample narratives for review
```

---

## 🤖 Phase 2: LLM Feature Extraction (Next)

### 1️⃣ Add Your OpenAI API Key

Edit `.env` file:
```bash
# Option A: In VS Code
# Click .env file and replace sk-your-actual-api-key-here with your real key

# Option B: Command line
echo 'OPENAI_API_KEY=sk-your-key-here' > .env
```

**Get your API key:**
- Go to: https://platform.openai.com/account/api-keys
- Copy your key (starts with `sk-`)
- Paste into `.env` file

### 2️⃣ Choose Your Model

In `.env`, set `OPENAI_MODEL`:

**Option A: GPT-3.5-turbo (Recommended for testing)**
```
OPENAI_MODEL=gpt-3.5-turbo
```
- Cost: ~$0.05 for 50 sample leads
- Speed: Fast
- Quality: Good

**Option B: GPT-4 (Better accuracy)**
```
OPENAI_MODEL=gpt-4
```
- Cost: ~$0.50 for 50 sample leads
- Speed: Slower
- Quality: Excellent

---

### 3️⃣ Run Phase 2

Test LLM feature extraction on 50 sample leads:

```bash
cd /Users/schadha/Desktop/lead-scoring
python3 scripts/02_llm_feature_extraction.py
```

This will:
- Extract semantic features from lead narratives
- Validate JSON parsing quality
- Show cost estimate
- Save `llm_extracted_features.csv`

**Expected output:**
```
Phase 2: LLM Feature Extraction
  ✅ Processed 50 leads
  ✅ Success rate: 95%+
  💰 Cost: $0.05-0.50 depending on model
  📁 Features saved: llm_extracted_features.csv
```

---

## 📋 What Each Feature Means

LLM will extract these features from narratives:

```json
{
  "seniority_level": "C-Level|Manager|Individual Contributor",
  "decision_maker_score": 0-100,  // Likelihood of buying decision
  "engagement_intent": "High|Medium|Low",
  "engagement_score": 0-100,  // Based on email opens/clicks
  "company_tier": "Enterprise|Mid-Market|Small",
  "budget_authority": "High|Medium|Low",
  "fit_explanation": "Why this lead is scored X"
}
```

---

## 💰 Cost Calculator

**Phase 2 (50 samples):**
- gpt-3.5-turbo: ~$0.05
- gpt-4: ~$0.50

**Phase 3 (613 leads full training):**
- gpt-3.5-turbo: ~$0.60
- gpt-4: ~$6.00

**Total project budget:**
- Budget: $10-20  (safe margin)
- Typical spend: $1-5

---

## ❓ Troubleshooting

**"OPENAI_API_KEY not found"**
```bash
# Check .env exists
ls -la .env

# Check key is set correctly
grep OPENAI_API_KEY .env
```

**"Insufficient quota"**
- Check you have API credits at: https://platform.openai.com/account/billing/overview
- Add payment method if needed

**"Model not available"**
- If GPT-4 not available, use gpt-3.5-turbo
- Or request GPT-4 access: https://openai.com/waitlist/gpt-4-api

---

## 🚀 Ready? Let's Go!

### Quick Start:
```bash
# 1. Edit .env with your API key
nano .env  # or use VS Code

# 2. Run Phase 2
python3 scripts/02_llm_feature_extraction.py

# 3. Check results
cat data_processed/llm_extracted_features.csv | head -5
```

### Timeline:
- **Today:** Set up OpenAI API + run Phase 2 (30 min + $0.05-0.50)
- **Tomorrow:** Phase 3 - Train hybrid model (1 hour)
- **This week:** Deploy scoring endpoint to API (2 hours)

---

## Questions?

Check the files:
- [LLM_MODEL_STRATEGY.md](LLM_MODEL_STRATEGY.md) - Full architecture
- [scripts/02_llm_feature_extraction.py](scripts/02_llm_feature_extraction.py) - Code
- [data_processed/sample_narratives.json](data_processed/sample_narratives.json) - Example data

---

**Let me know when you've added your API key and I'll help you run Phase 2! 🚀**
