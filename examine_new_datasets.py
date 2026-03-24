#!/usr/bin/env python3
"""Examine the new datasets structure and content"""

import pandas as pd

print("="*80)
print("📊 EXAMINING NEW DATASETS")
print("="*80)

# Check Latest_leads_data.csv
print("\n1️⃣  Latest_leads_data.csv")
print("-" * 80)
df_latest = pd.read_csv('sample_data/Latest_leads_data.csv')
print(f"Shape: {df_latest.shape}")
print(f"Columns: {list(df_latest.columns)}")
print(f"\nFirst 3 rows:")
print(df_latest.head(3).to_string())
print(f"\nData types:\n{df_latest.dtypes}")
print(f"\nMissing values:\n{df_latest.isnull().sum()}")

# Check Buying_stage.csv
print("\n" + "="*80)
print("2️⃣  Buying_stage.csv")
print("-" * 80)
df_buying = pd.read_csv('sample_data/Buying_stage.csv')
print(f"Shape: {df_buying.shape}")
print(f"Columns: {list(df_buying.columns)}")
print(f"\nFirst 3 rows:")
print(df_buying.head(3).to_string())
print(f"\nData types:\n{df_buying.dtypes}")
print(f"\nMissing values:\n{df_buying.isnull().sum()}")

# Summary
print("\n" + "="*80)
print("✅ SUMMARY")
print("="*80)
print(f"\nDatasets available:")
print(f"  • Latest_leads_data.csv: {df_latest.shape[0]} rows × {df_latest.shape[1]} columns")
print(f"  • Buying_stage.csv: {df_buying.shape[0]} rows × {df_buying.shape[1]} columns")
print(f"\nKey columns for training:")
print(f"  Latest: {', '.join(df_latest.columns[:5])}...")
print(f"  Buying: {', '.join(df_buying.columns[:5])}...")
