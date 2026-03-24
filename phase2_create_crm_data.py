#!/usr/bin/env python3
"""
Phase 2 Step 1: Create Synthetic Historical CRM Data
Simulates real lead→opportunity→customer conversion data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

print("=" * 80)
print("PHASE 2 STEP 1: Creating Synthetic Historical CRM Data")
print("=" * 80)

# Create synthetic CRM data
np.random.seed(42)
n_leads = 500

# Generate leads with realistic distributions
now = datetime.now()

leads_data = {
    'lead_id': [f'CRM-{i:05d}' for i in range(n_leads)],
    'email': [f'contact{i}@company{i%50}.com' for i in range(n_leads)],
    'company_name': [f'Company {i%100}' for i in range(n_leads)],
    'created_date': [now - timedelta(days=np.random.randint(30, 730)) for _ in range(n_leads)],
}

# Create DataFrame
df_crm = pd.DataFrame(leads_data)

# Generate conversion outcomes
# Higher scores should correlate with conversion
conversion_prob = np.random.uniform(0.15, 0.45, n_leads)  # 15-45% baseline conversion

conversions = []
deal_sizes = []
close_dates = []

for i in range(n_leads):
    # Conversion probability (realistic 20-35% for B2B)
    converted = np.random.random() < 0.275
    conversions.append(1 if converted else 0)
    
    if converted:
        # Deal size distribution (log-normal, realistic for B2B)
        deal_size = np.exp(np.random.normal(10.5, 1.2))  # $30K-$400K range
        deal_sizes.append(round(deal_size * 1000, 2))
        
        # Sales cycle: 30-180 days
        cycle_days = np.random.randint(30, 180)
        close_date = df_crm.loc[i, 'created_date'] + timedelta(days=cycle_days)
        close_dates.append(close_date)
    else:
        deal_sizes.append(0)
        close_dates.append(None)

df_crm['converted'] = conversions
df_crm['deal_size'] = deal_sizes
df_crm['close_date'] = close_dates
df_crm['sales_cycle_days'] = [
    (close_dates[i] - df_crm.loc[i, 'created_date']).days if close_dates[i] else None
    for i in range(n_leads)
]

print(f"\n✅ Generated {n_leads} historical leads")
print(f"\nConversion Statistics:")
print(f"  Total leads: {len(df_crm)}")
print(f"  Converted: {df_crm['converted'].sum()} ({df_crm['converted'].mean():.1%})")
print(f"  Not converted: {(1-df_crm['converted']).sum()}")
print(f"\nDeal Size Statistics (converted deals only):")
converted_df = df_crm[df_crm['converted'] == 1]
if len(converted_df) > 0:
    print(f"  Min: ${converted_df['deal_size'].min():,.0f}")
    print(f"  Mean: ${converted_df['deal_size'].mean():,.0f}")
    print(f"  Max: ${converted_df['deal_size'].max():,.0f}")
    print(f"\nSales Cycle (converted deals only):")
    print(f"  Min: {converted_df['sales_cycle_days'].min()} days")
    print(f"  Mean: {converted_df['sales_cycle_days'].mean():.0f} days")
    print(f"  Max: {converted_df['sales_cycle_days'].max()} days")

# Save CRM data
df_crm.to_csv('data_processed/crm_historical_leads.csv', index=False)
print(f"\n✅ Saved to data_processed/crm_historical_leads.csv")

# Show sample
print(f"\nSample CRM Data (first 5 rows):")
print(df_crm[['lead_id', 'email', 'converted', 'deal_size', 'sales_cycle_days']].head())

print("\n" + "=" * 80)
print("✅ PHASE 2 STEP 1: COMPLETE")
print("=" * 80)
print("\nNext: Merge with Lead Scoring Features (Step 2)")
print("=" * 80)
