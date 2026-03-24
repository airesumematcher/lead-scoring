#!/usr/bin/env python3
"""
Phase 2: LLM Feature Extraction

This script:
1. Loads narratives from Phase 1
2. Calls OpenAI API to extract semantic features
3. Validates feature quality
4. Saves extracted features for model training
"""

import pandas as pd
import json
from pathlib import Path
import os
from dotenv import load_dotenv
import sys

# Load environment
load_dotenv()

# ============================================================================
# CONFIG
# ============================================================================

DATA_DIR = Path("data_processed")
OUTPUT_DIR = Path("data_processed")
OUTPUT_DIR.mkdir(exist_ok=True)

SAMPLE_SIZE = 50  # Test on 50 leads first
BATCH_SIZE = 10

# ============================================================================
# LLM FEATURE EXTRACTION
# ============================================================================

class LLMFeatureExtractor:
    """Extract semantic features using OpenAI API"""
    
    def __init__(self, api_key=None, model="gpt-3.5-turbo"):
        """Initialize with OpenAI API"""
        from openai import OpenAI
        
        api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. Add to .env file or environment.")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}
        
        print(f"\n✅ OpenAI API initialized")
        print(f"   Model: {model}")
    
    def extract_features(self, narrative):
        """
        Extract semantic features from lead narrative
        
        Returns JSON with:
        - seniority_level: C-level, Manager, or IC
        - decision_maker_score: 0-100
        - engagement_intent: high, medium, low
        - engagement_score: 0-100
        - company_tier: enterprise, mid-market, small
        - fit_explanation: Brief reasoning
        """
        
        prompt = f"""You are a B2B SaaS lead scoring expert. Analyze this lead profile and extract features.

LEAD NARRATIVE:
{narrative}

Respond ONLY with valid JSON (no markdown, no explanation):
{{
    "seniority_level": "C-Level" or "Manager" or "Individual Contributor",
    "decision_maker_score": number 0-100,
    "engagement_intent": "High" or "Medium" or "Low",
    "engagement_score": number 0-100,
    "company_tier": "Enterprise" or "Mid-Market" or "Small",
    "budget_authority": "High" or "Medium" or "Low",
    "fit_explanation": "1-2 sentence reason for scoring"
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a lead scoring expert. Extract features from lead narratives. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=300,
            )
            
            # Track usage
            if hasattr(response, 'usage'):
                self.usage["prompt_tokens"] += response.usage.prompt_tokens
                self.usage["completion_tokens"] += response.usage.completion_tokens
            
            # Parse response
            result_text = response.choices[0].message.content.strip()
            
            # Handle markdown code blocks
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            
            features = json.loads(result_text)
            return {
                "status": "success",
                "features": features,
                "error": None
            }
            
        except json.JSONDecodeError as e:
            return {
                "status": "parse_error",
                "features": None,
                "error": f"JSON parse error: {str(e)[:100]}"
            }
        except Exception as e:
            return {
                "status": "api_error",
                "features": None,
                "error": str(e)[:200]
            }
    
    def batch_extract(self, narratives_list, batch_size=10):
        """Extract features for multiple leads"""
        
        results = []
        errors = []
        
        print(f"\n📊 Extracting features from {len(narratives_list)} narratives...")
        print(f"   Batch size: {batch_size}")
        
        for i, narrative in enumerate(narratives_list, 1):
            
            # Show progress
            if i % batch_size == 0:
                print(f"   Progress: {i}/{len(narratives_list)} ({i/len(narratives_list)*100:.0f}%)")
            
            # Extract
            result = self.extract_features(narrative)
            results.append(result)
            
            if result["status"] != "success":
                errors.append({
                    "index": i-1,
                    "error": result["error"]
                })
        
        return results, errors
    
    def get_cost_estimate(self, num_leads):
        """Estimate API cost"""
        # Rough estimates for single lead analysis
        prompt_tokens = 150  # narrative + instructions
        completion_tokens = 120  # response
        
        if self.model == "gpt-4":
            cost = (
                (prompt_tokens * num_leads * 0.00003) +  # input
                (completion_tokens * num_leads * 0.00006)  # output
            )
        else:  # gpt-3.5-turbo
            cost = (
                (prompt_tokens * num_leads * 0.0005) +  # input
                (completion_tokens * num_leads * 0.0015)  # output
            )
        
        return cost
    
    def get_usage_cost(self):
        """Calculate actual cost from usage"""
        if self.model == "gpt-4":
            prompt_cost = self.usage["prompt_tokens"] * 0.00003
            completion_cost = self.usage["completion_tokens"] * 0.00006
        else:  # gpt-3.5-turbo
            prompt_cost = self.usage["prompt_tokens"] * 0.0005
            completion_cost = self.usage["completion_tokens"] * 0.0015
        
        total = prompt_cost + completion_cost
        return {
            "prompt_tokens": self.usage["prompt_tokens"],
            "completion_tokens": self.usage["completion_tokens"],
            "estimated_cost": round(total, 4)
        }

def load_narratives(sample_size=None):
    """Load narratives from Phase 1 output"""
    
    print("\n" + "="*80)
    print("📥 LOADING NARRATIVES")
    print("="*80)
    
    parquet_path = DATA_DIR / "leads_with_narratives.parquet"
    
    if not parquet_path.exists():
        print(f"\n❌ File not found: {parquet_path}")
        print(f"\nPlease run Phase 1 first:")
        print(f"   python scripts/01_data_prep.py")
        sys.exit(1)
    
    df = pd.read_parquet(parquet_path)
    print(f"   ✅ Loaded {len(df)} leads")
    
    # Get narratives with valid scores
    df_with_scores = df[df['target_score'].notna()].copy()
    narratives = df_with_scores['narrative'].tolist()
    leads_data = df_with_scores[['Lead Email', 'target_score']].reset_index(drop=True)
    
    if sample_size:
        narratives = narratives[:sample_size]
        leads_data = leads_data[:sample_size]
        print(f"   📌 Using sample: {len(narratives)} leads")
    
    return narratives, leads_data

def save_extracted_features(results, leads_data, output_dir=OUTPUT_DIR):
    """Save extracted features as structured data"""
    
    print("\n" + "="*80)
    print("💾 SAVING EXTRACTED FEATURES")
    print("="*80)
    
    # Convert to dataframe
    features_list = []
    for i, (result, lead_info) in enumerate(zip(results, leads_data.to_dict('records'))):
        
        if result["status"] == "success":
            features = result["features"]
            features['email'] = lead_info['Lead Email']
            features['actual_score'] = lead_info['target_score']
            features_list.append(features)
    
    features_df = pd.DataFrame(features_list)
    
    # Save
    output_path = output_dir / "llm_extracted_features.csv"
    features_df.to_csv(output_path, index=False)
    
    print(f"   ✅ Saved {len(features_df)} leads to {output_path}")
    
    # Summary stats
    print(f"\n   Feature Statistics:")
    for col in ['decision_maker_score', 'engagement_score']:
        if col in features_df.columns:
            print(f"   • {col}: {features_df[col].mean():.1f} (mean)")
    
    return features_df

def validate_results(results, leads_data):
    """Validate extraction quality"""
    
    print("\n" + "="*80)
    print("✅ VALIDATION REPORT")
    print("="*80)
    
    successful = sum(1 for r in results if r["status"] == "success")
    parse_errors = sum(1 for r in results if r["status"] == "parse_error")
    api_errors = sum(1 for r in results if r["status"] == "api_error")
    
    success_rate = (successful / len(results)) * 100
    
    print(f"\n   Total leads processed: {len(results)}")
    print(f"   ✅ Successful: {successful} ({success_rate:.1f}%)")
    print(f"   ⚠️  Parse errors: {parse_errors}")
    print(f"   ❌ API errors: {api_errors}")
    
    if success_rate < 80:
        print(f"\n   ⚠️  Success rate below 80%. Consider:")
        print(f"      - Adjusting extraction prompt")
        print(f"      - Using gpt-4 for better JSON compliance")
        print(f"      - Checking narrative format")
    
    return success_rate

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run Phase 2 pipeline"""
    
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "PHASE 2: LLM FEATURE EXTRACTION".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        # 1. Load narratives
        narratives, leads_data = load_narratives(sample_size=SAMPLE_SIZE)
        
        # 2. Initialize extractor
        api_key = os.getenv('OPENAI_API_KEY')
        model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
        
        extractor = LLMFeatureExtractor(api_key=api_key, model=model)
        
        # 3. Show cost estimate
        print(f"\n💰 Cost Estimate:")
        cost = extractor.get_cost_estimate(len(narratives))
        print(f"   Estimated cost: ${cost:.2f} for {len(narratives)} leads")
        
        # 4. Run extraction
        results, errors = extractor.batch_extract(narratives, batch_size=BATCH_SIZE)
        
        # 5. Validate
        success_rate = validate_results(results, leads_data)
        
        # 6. Save if successful
        if success_rate >= 80:
            features_df = save_extracted_features(results, leads_data)
            
            print(f"\n   📊 Sample extracted features:")
            print(features_df.head(3).to_string())
        
        # 7. Show actual usage cost
        usage = extractor.get_usage_cost()
        print(f"\n💵 Actual Usage:")
        print(f"   Prompt tokens: {usage['prompt_tokens']:,}")
        print(f"   Completion tokens: {usage['completion_tokens']:,}")
        print(f"   Estimated cost: ${usage['estimated_cost']:.4f}")
        
        # Summary
        print("\n" + "="*80)
        print("✅ PHASE 2 COMPLETE")
        print("="*80)
        print(f"""
Phase 2 Results:
  ✅ Processed {len(narratives)} leads
  ✅ Success rate: {success_rate:.1f}%
  ✅ Saved features: {OUTPUT_DIR / 'llm_extracted_features.csv'}
  💰 Cost: ${usage['estimated_cost']:.4f}

Next Steps:
  1. Review extracted features: llm_extracted_features.csv
  2. Compare with actual scores
  3. Run Phase 3: Train hybrid model
     python scripts/03_train_hybrid_model.py
        """)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
