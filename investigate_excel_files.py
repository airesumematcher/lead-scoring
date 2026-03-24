#!/usr/bin/env python3
"""
Investigate unknown Excel files in sample_data folder
"""
import pandas as pd
import os

data_dir = '/Users/schadha/Desktop/lead-scoring/sample_data'

print("\n" + "="*80)
print("INVESTIGATING EXCEL FILES IN SAMPLE_DATA")
print("="*80 + "\n")

files_to_check = [
    'Lead_scoring_analysis.xlsx',
    'cleaned_data.xlsx'
]

for filename in files_to_check:
    filepath = os.path.join(data_dir, filename)
    
    if os.path.exists(filepath):
        print(f"📄 {filename}")
        print(f"   Size: {os.path.getsize(filepath) / 1024:.1f} KB")
        
        try:
            # Check sheets
            xl_file = pd.ExcelFile(filepath)
            print(f"   Sheets: {xl_file.sheet_names}")
            
            # Check first sheet structure
            if len(xl_file.sheet_names) > 0:
                df = pd.read_excel(filepath, sheet_name=0)
                print(f"   First sheet: '{xl_file.sheet_names[0]}'")
                print(f"   Rows: {len(df)}, Columns: {len(df.columns)}")
                print(f"   Columns: {list(df.columns)}")
                
                # Check for lead score target
                score_cols = [col for col in df.columns if 'score' in col.lower() or 'lead' in col.lower()]
                if score_cols:
                    print(f"   ✅ Score columns: {score_cols}")
                
                # Show dtypes
                print(f"\n   Data types:")
                for col in df.columns[:5]:
                    print(f"     {col}: {df[col].dtype}")
                    
        except Exception as e:
            print(f"   ❌ Error reading: {str(e)[:100]}")
        
        print("\n" + "-"*80 + "\n")
    else:
        print(f"❌ {filename} NOT FOUND\n")

print("="*80)
print("Done")
print("="*80)
