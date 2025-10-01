import pandas as pd
import glob
import os
import sys

def analyze_site(site_name):
    output_dir = "output"
    file_pattern = os.path.join(output_dir, f'{site_name}_job_listings_*.csv')
    files = glob.glob(file_pattern)

    if not files:
        print(f"[{site_name}] No old timestamped CSV files found. Nothing to do.")
        return

    print(f"[{site_name}] Found {len(files)} files to analyze.")
    
    df_list = []
    for f in files:
        try:
            df_list.append(pd.read_csv(f, encoding='utf-8-sig'))
        except Exception as e:
            print(f"Could not read {f}: {e}", file=sys.stderr)
    
    if not df_list:
        print(f"[{site_name}] No data could be read from CSV files.", file=sys.stderr)
        return

    merged_df = pd.concat(df_list, ignore_index=True)

    if '求人URL' not in merged_df.columns:
        print(f"[{site_name}] '求人URL' column not found. Cannot check for duplicates.")
        return
        
    cleaned_df = merged_df.dropna(subset=['求人URL'])
    
    num_duplicates = cleaned_df.duplicated(subset=['求人URL']).sum()

    if num_duplicates == 0:
        print(f"[{site_name}] SUCCESS: No duplicates found. Merging is safe.")
    else:
        print(f"[{site_name}] WARNING: Found {num_duplicates} duplicate rows based on '求人URL'.")

if __name__ == "__main__":
    print("--- Starting CSV analysis ---")
    analyze_site('01intern')
    print("-" * 20)
    analyze_site('kyujinbox')
    print("--- Analysis complete ---")
