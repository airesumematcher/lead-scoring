#!/usr/bin/env python3
import pandas as pd
import sys

print("\n" + "="*80)
print("🔍 LEAD DATA ANALYSIS")
print("="*80)

# Load CSV
csv_path = "sample_data/Lead Score_Lead Outreach Results Pivots(Sheet1) (1).csv"
df_csv = pd.read_csv(csv_path)

print(f"\n📄 CSV FILE: Lead Score_Lead Outreach Results Pivots")
print(f"   Shape: {len(df_csv)} rows × {len(df_csv.columns)} columns")
print(f"\n   Columns ({len(df_csv.columns)}):")
for i, col in enumerate(df_csv.columns, 1):
    dtype = str(df_csv[col].dtype)
    missing = df_csv[col].isnull().sum()
    missing_pct = (missing / len(df_csv)) * 100
    print(f"   {i:2d}. {col:35s} | {dtype:10s} | Missing: {missing:3d} ({missing_pct:5.1f}%)")

print(f"\n   Data Summary:")
print(f"   • Lead Score range: {df_csv['Lead Score'].min():.1f} - {df_csv['Lead Score'].max():.1f}")
print(f"   • Non-null Lead Scores: {df_csv['Lead Score'].notna().sum()}")
print(f"   • Company Sizes: {df_csv['Company Size'].unique().tolist()}")
print(f"   • Job Functions (sample): {df_csv['Job Function'].unique()[:5].tolist()}")

print("\n\n" + "-"*80)

# Excel files
for excel_file in ["sample_data/Lead_scoring_analysis.xlsx", "sample_data/cleaned_data.xlsx"]:
    try:
        xl = pd.ExcelFile(excel_file)
        fname = excel_file.split('/')[-1]
        print(f"\n📊 EXCEL FILE: {fname}")
        
        for sheet in xl.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet)
            print(f"\n   Sheet: {sheet}")
            print(f"   Shape: {len(df)} rows × {len(df.columns)} columns")
            print(f"   Columns: {list(df.columns)[:12]}")
            if len(df.columns) > 12:
                print(f"   ... and {len(df.columns) - 12} more")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "="*80)
print("✅ Analysis complete!")
print("="*80)
