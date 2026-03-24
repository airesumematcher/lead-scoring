#!/usr/bin/env python3
"""
Setup OpenAI API Configuration

This script:
1. Validates OpenAI API key
2. Tests API connection
3. Sets up environment
4. Estimates costs for Phase 2-3
"""

import os
from pathlib import Path
import sys

def setup_openai_config():
    """Configure OpenAI API"""
    
    print("\n" + "="*80)
    print("🔧 OPENAI API SETUP")
    print("="*80)
    
    # Check for .env file
    env_file = Path(".env")
    
    if env_file.exists():
        print(f"\n✅ Found .env file")
        with open(env_file) as f:
            for line in f:
                if "OPENAI_API_KEY" in line:
                    print(f"   ✓ OPENAI_API_KEY configured")
                    break
    else:
        print(f"\n⚠️  No .env file found")
        print(f"\nFollow these steps:\n")
        print(f"1. Create .env file in project root:")
        print(f"   touch .env")
        print(f"\n2. Add your OpenAI API key:")
        print(f"   echo 'OPENAI_API_KEY=sk-...' >> .env")
        print(f"\n3. Import in your scripts:")
        print(f"   from dotenv import load_dotenv")
        print(f"   load_dotenv()")
        print(f"   api_key = os.getenv('OPENAI_API_KEY')")

def test_api_connection(api_key):
    """Test OpenAI API is working"""
    print("\n" + "="*80)
    print("🧪 TESTING API CONNECTION")
    print("="*80)
    
    try:
        from openai import OpenAI
        
        if not api_key:
            print("\n❌ API key not found in environment")
            print("   Set OPENAI_API_KEY environment variable")
            return False
        
        client = OpenAI(api_key=api_key)
        
        # Simple test
        print(f"\n   Testing with gpt-4...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Say 'API working' in one sentence."}],
            max_tokens=10
        )
        
        print(f"   ✅ GPT-4 API: Working")
        print(f"   Response: {response.choices[0].message.content.strip()}")
        return True
        
    except Exception as e:
        if "gpt-4" in str(e).lower():
            print(f"   ⚠️  GPT-4 not available")
            print(f"   Trying gpt-3.5-turbo...")
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Say 'API working' in one sentence."}],
                    max_tokens=10
                )
                print(f"   ✅ GPT-3.5-turbo API: Working")
                return True
            except Exception as e2:
                print(f"   ❌ Error: {e2}")
                return False
        else:
            print(f"   ❌ Error: {e}")
            return False

def estimate_costs():
    """Estimate costs for different phases"""
    
    print("\n" + "="*80)
    print("💰 COST ESTIMATION")
    print("="*80)
    
    estimates = {
        "gpt-4": {
            "input": 0.03,  # per 1K tokens
            "output": 0.06,
            "per_lead": 0.01,  # rough estimate
        },
        "gpt-3.5-turbo": {
            "input": 0.0005,
            "output": 0.0015,
            "per_lead": 0.0001,  # rough estimate
        }
    }
    
    leads = 613
    
    print(f"\nEstimates for {leads} leads:\n")
    
    for model, pricing in estimates.items():
        total = leads * pricing['per_lead']
        print(f"  {model}:")
        print(f"    Per lead: ${pricing['per_lead']:.4f}")
        print(f"    Total: ${total:.2f}")
        print()
    
    print(f"Recommendations:")
    print(f"  • Phase 2 (Testing): Use gpt-3.5-turbo (~$0.06 total)")
    print(f"  • Phase 3 (Full run): Use gpt-4 if available (~$6.00 total)")
    print(f"  • Fine-tuning: Budget $500-1000 for optimal accuracy")

def create_example_env():
    """Create example .env file"""
    
    env_example = Path(".env.example")
    if not env_example.exists():
        with open(env_example, 'w') as f:
            f.write("""# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here

# Model Selection (gpt-4 or gpt-3.5-turbo)
OPENAI_MODEL=gpt-3.5-turbo

# Optional: Organization ID
# OPENAI_ORG_ID=org-xxx
""")
        print(f"✅ Created .env.example")

def main():
    """Run setup wizard"""
    
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "OPENAI API SETUP WIZARD".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    # 1. Setup config
    setup_openai_config()
    
    # 2. Create example
    create_example_env()
    
    # 3. Try to test API
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        test_api_connection(api_key)
    else:
        print("\n⚠️  Skipping API test - key not in environment")
    
    # 4. Show costs
    estimate_costs()
    
    print("\n" + "="*80)
    print("✅ SETUP COMPLETE")
    print("="*80)
    print(f"""
Next Steps:

1️⃣  Ensure .env has your OPENAI_API_KEY
    Check: echo $OPENAI_API_KEY

2️⃣  Validate Phase 1 data:
    python scripts/01_data_prep.py

3️⃣  Run Phase 2: LLM Feature Extraction
    python scripts/02_llm_feature_extraction.py

Questions:
  ❓ Which model to use?
    → Start with gpt-3.5-turbo (cheaper for testing)
    → Switch to gpt-4 for better accuracy (if you have access)
  
  ❓ Feature extraction or training first?
    → Feature extraction (Phase 2) is next
    → Tests LLM quality on sample leads
    """)

if __name__ == "__main__":
    main()
