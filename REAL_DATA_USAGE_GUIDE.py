#!/usr/bin/env python3
"""
Quick Guide: Using Real-Data-Trained Models via API

This guide shows you how to use your newly trained models that were
trained on 613 real leads from your Lead Outreach Results CSV file.
"""

import requests
import json

# ============================================================================
# QUICK START: Test the API
# ============================================================================

BASE_URL = "http://localhost:8000"

# Example 1: Score a single lead
print("="*70)
print("EXAMPLE 1: Score a Single Lead")
print("="*70)

lead = {
    "lead_id": "ACME-001",
    "email": "john.doe@acmecorp.com",
    "first_name": "John",
    "last_name": "Doe",
    "title": "VP of Sales",
    "company_name": "ACME Corporation",
    "company_size": "Large (1000+ employees)",
    "job_function": "Sales",
    "engagement_score": 85
}

print("\nRequest:")
print(json.dumps(lead, indent=2))

try:
    response = requests.post(f"{BASE_URL}/score", json=lead)
    result = response.json()
    
    print("\nResponse:")
    print(json.dumps(result, indent=2))
    
    if "score" in result:
        print(f"\n✅ Lead Score: {result['score']:.1f}/100")
        if result['score'] > 85:
            print("   Status: 🔥 HOT LEAD - Ready for sales")
        elif result['score'] > 75:
            print("   Status: ⚡ WARM LEAD - Nurture")
        else:
            print("   Status: ❄️  COLD LEAD - Nurture/Marketing")
            
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("   Make sure API is running: python3 -m uvicorn src.lead_scoring.api.app:app --port 8000")

# ============================================================================
# EXAMPLE 2: Batch Score Multiple Leads
# ============================================================================

print("\n" + "="*70)
print("EXAMPLE 2: Batch Score Multiple Leads")
print("="*70)

leads = [
    {
        "lead_id": "LEAD-001",
        "email": "executive@company1.com",
        "first_name": "Sarah",
        "title": "CEO",
        "company_name": "Fortune 500 Corp",
        "company_size": "XXLarge (10000+ employees)",
        "job_function": "Executive Management"
    },
    {
        "lead_id": "LEAD-002",
        "email": "manager@company2.com",
        "first_name": "Mike",
        "title": "Marketing Manager",
        "company_name": "Mid-Market Inc",
        "company_size": "Medium (200-500 employees)",
        "job_function": "Marketing"
    },
    {
        "lead_id": "LEAD-003",
        "email": "analyst@company3.com",
        "first_name": "Lisa",
        "title": "Business Analyst",
        "company_name": "Startup LLC",
        "company_size": "Small (50-200 employees)",
        "job_function": "Operations"
    }
]

print(f"\nBatch scoring {len(leads)} leads...")

try:
    response = requests.post(f"{BASE_URL}/score-batch", json={"leads": leads})
    results = response.json()
    
    print("\nResults:")
    for lead_result in results.get("scored_leads", []):
        print(f"\n  {lead_result['lead_id']}: {lead_result.get('score', 'N/A'):.1f}/100")
        print(f"    • Title: {lead_result.get('title', 'N/A')}")
        print(f"    • Company: {lead_result.get('company_name', 'N/A')}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")

# ============================================================================
# MODEL INFO: What You Need to Know
# ============================================================================

print("\n" + "="*70)
print("ABOUT YOUR MODELS")
print("="*70)

models_info = """
✅ TRAINED ON REAL DATA
   • 613 actual leads from your Lead Outreach Results campaign
   • Lead scores: 68.7 - 100.0 average 82.6

🎯 BEST PERFORMER
   • ExtraTrees with R² = 0.5924 (59% accuracy)
   • Explains ~59% of variance in lead quality

📊 MODEL ENSEMBLE
   8 models voting:
   ├─ ExtraTrees (best tree)
   ├─ Bagging (most stable)
   ├─ Ensemble (most reliable for production)
   ├─ RandomForest
   ├─ NeuralNetwork
   ├─ XGBoost
   ├─ SVR
   └─ GradientBoosting

🔄 AUTO-RETRAINING
   Models can be retrained monthly with:
   python3 train_enhanced_from_csv.py

📈 SCORING INTERPRETATION
   90+  🔥 Hot Lead        → Sales contact today
   80-89 ⚡ Warm Lead      → Add to nurture campaign
   70-79 ❄️  Cool Lead      → Drip campaign
   <70  ❓ Unknown         → Research needed

💡 FEATURES USED
   • Job title seniority (CEO → Analyst)
   • Company size (XXLarge → Small)
   • Job function (Executive → Operations)  
   • Email engagement (Opens, Clicks)
   • Campaign activity signals
"""

print(models_info)

print("\n" + "="*70)
print("COMMON API CALLS")
print("="*70)

api_examples = """
# 1. Get API health
curl http://localhost:8000/health

# 2. Score single lead (JSON)
curl -X POST http://localhost:8000/score \\
  -H "Content-Type: application/json" \\
  -d '{
    "lead_id": "001",
    "email": "john@company.com",
    "title": "VP Sales",
    "company_size": "Large"
  }' | jq '.score'

# 3. Score multiple leads (batch)
curl -X POST http://localhost:8000/score-batch \\
  -H "Content-Type: application/json" \\
  -d '{
    "leads": [
      {"lead_id": "001", "email": "john@a.com", "title": "CEO"},
      {"lead_id": "002", "email": "jane@b.com", "title": "CFO"}
    ]
  }'

# 4. Get all model metrics
curl http://localhost:8000/models/metrics | jq '.models'

# 5. Get specific model performance  
curl http://localhost:8000/models/metrics | jq '.models.ExtraTrees'
"""

print(api_examples)

print("\n" + "="*70)
print("✅ YOU'RE READY!")
print("="*70)

ready_message = """
Your lead scoring system is now trained on REAL data:

Next Steps:
1. Start the API:
   pkill -f uvicorn
   sleep 2
   python3 -m uvicorn src.lead_scoring.api.app:app --port 8000 &

2. Test with one of the examples above

3. Integrate into your workflow:
   • Score leads in real-time as they arrive
   • Use scores to prioritize outreach
   • Track conversions to improve models

4. Monitor & improve:
   • Log predictions vs conversion outcomes
   • Retrain monthly with new data
   • Adjust scoring thresholds based on results

Questions?
- Check CSV_TRAINING_COMPLETE.md for full details
- Review model_comparison_results_csv_real.json for metrics
- Re-run: python3 verify_csv_training.py
"""

print(ready_message)
