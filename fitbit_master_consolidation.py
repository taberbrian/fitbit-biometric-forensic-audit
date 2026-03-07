"""
Fitbit Master Consolidation Script
Author: BT
Environment: Google Colab
Purpose: 
    This script serves as the ETL (Extract, Transform, Load) engine for the 
    Fitbit Biometric Audit. It traverses the Fitbit data export directory, 
    cleans sensor-specific timestamps, and merges 130+ CSV/JSON files into 
    a single 'fitbit_master_database.csv'.
Data Recognition: 
    Raw sensor data extracted from the Fitbit Personal Data Export archive.
"""

import pandas as pd
import glob
import os
import json
from google.colab import drive

# 1. Access Environment
drive.mount('/content/drive')
folder_path = '/content/drive/MyDrive/Fitbit_Data'
master_path = os.path.join(folder_path, 'fitbit_master_database.csv')
log_path = os.path.join(folder_path, 'workout_log.csv')

# 2. Setup Data Dictionary for standard CSVs
data_dict = {
    'activity': [], 'altitude': [], 'body_response': [], 
    'calories': [], 'cardio': [], 'distance': [], 
    'steps': [], 'temperature': [], 'hr': [], 'hrv': []
}

# 3. Handle Standard CSV Files
all_csvs = glob.glob(os.path.join(folder_path, "**", "*.[cC][sS][vV]"), recursive=True)
print(f"--- Processing {len(all_csvs)} CSV files ---")

for file in all_csvs:
    filename = os.path.basename(file).lower()
    if filename in ['fitbit_master_database.csv', 'workout_log.csv']: continue
    
    try:
        df = pd.read_csv(file)
        if df.empty: continue
            
        # Standardize Time - Handle potential UTC conversion
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert('America/Chicago').dt.tz_localize(None)
        df['minute'] = df['timestamp'].dt.floor('min')
        
        if filename.startswith('heart_rate'):
            df_clean = df.groupby('minute')['beats per minute'].mean().round(0).astype(int).reset_index()
            df_clean.rename(columns={'beats per minute': 'heart_rate'}, inplace=True)
            data_dict['hr'].append(df_clean)
            
        elif filename.startswith('body_temperature'):
            df_clean = df.groupby('minute')['temperature celsius'].mean().round(2).reset_index()
            df_clean.rename(columns={'temperature celsius': 'temperature'}, inplace=True)
            data_dict['temperature'].append(df_clean)
            
        elif filename.startswith('steps'):
            df_clean = df.groupby('minute')['steps'].sum().reset_index()
            data_dict['steps'].append(df_clean)
            
        elif filename.startswith('calories_in_heart_rate_zone'):
            df_clean = df.groupby('minute')['kcal'].sum().round(4).reset_index()
            df_clean.rename(columns={'kcal': 'calories'}, inplace=True)
            data_dict['calories'].append(df_clean)

        elif filename.startswith('body_response'):
            # UPDATED: More robust column matching for technical metrics
            cols_to_extract = [
                'ceda magnitude real micro siemens', 
                'skin temperature magnitude celsius', 
                'hr mean bpm',
                'hrv rmssd percentile 05 95', 
                'hrv sdnn percentile 05 95'
            ]
            
            # Find which of our target columns actually exist in this file
            existing = [c for c in cols_to_extract if c in df.columns] 
            
            if existing:
                df_clean = df.groupby('minute')[existing].mean().reset_index()
                
                # Rename for cleaner use in R (Fitbit_Details.Rmd)
                rename_map = {
                    'hrv rmssd percentile 05 95': 'rmssd',
                    'hrv sdnn percentile 05 95': 'sdnn'
                }
                df_clean.rename(columns=rename_map, inplace=True)
                data_dict['body_response'].append(df_clean)
            
        elif filename.startswith('altitude'):
            df_clean = df.groupby('minute')['gain'].sum().reset_index()
            df_clean.rename(columns={'gain': 'altitude_gain'}, inplace=True)
            data_dict['altitude'].append(df_clean)

        elif filename.startswith('activity_level'):
            df_clean = df.groupby('minute')['level'].first().reset_index()
            data_dict['activity'].append(df_clean)

        elif filename.startswith('distance'):
            df_clean = df.groupby('minute')['distance'].sum().reset_index()
            data_dict['distance'].append(df_clean)

        elif filename.startswith('cardio_load'):
            df_clean = df.groupby('minute')[['workout', 'background', 'total']].mean().reset_index()
            data_dict['cardio'].append(df_clean)

    except Exception as e:
        print(f"Error processing {filename}: {e}")

# 4. Handle HRV JSON Files (Fallback)
json_files = glob.glob(os.path.join(folder_path, "**", "*.json"), recursive=True)
if json_files:
    print(f"--- Checking {len(json_files)} JSON files for additional HRV data ---")
    for file in json_files:
        if 'heart_rate_variability' in file.lower():
            try:
                with open(file, 'r') as f:
                    hrv_json = json.load(f)
                    temp_hrv = []
                    for entry in hrv_json:
                        ts = pd.to_datetime(entry['timestamp']).tz_convert('America/Chicago').tz_localize(None)
                        temp_hrv.append({
                            'minute': ts.floor('min'),
                            'rmssd': entry['value']['rmssd'],
                            'sdnn': entry['value']['sdnn']
                        })
                    if temp_hrv:
                        data_dict['hrv'].append(pd.DataFrame(temp_hrv))
            except Exception as e:
                print(f"Error processing JSON {file}: {e}")

# 5. Build Master Table
master_components = {}
for key, list_of_dfs in data_dict.items():
    if list_of_dfs:
        stacked_df = pd.concat(list_of_dfs, ignore_index=True)
        # Drop duplicates to ensure a clean merge
        master_components[key] = stacked_df.drop_duplicates(subset=['minute'])

# Aggregate all unique minute timestamps across all source dictionaries
all_minutes = pd.Series(dtype='datetime64[ns]')
for df in master_components.values():
    all_minutes = pd.concat([all_minutes, df['minute']])

if not all_minutes.empty:
    master_df = pd.DataFrame({'minute': all_minutes.unique()}).sort_values('minute').reset_index(drop=True)
    
    # Left merge all components onto the timeline
    for key, df in master_components.items():
        master_df = pd.merge(master_df, df, on='minute', how='left')

    # 6. Apply Workout Tags
    if os.path.exists(log_path):
        log_df = pd.read_csv(log_path)
        log_df['Start_DT'] = pd.to_datetime(log_df['Date'] + ' ' + log_df['Start_Time'])
        log_df['End_DT'] = pd.to_datetime(log_df['Date'] + ' ' + log_df['End_Time'])
        
        master_df['Workout_Type'] = 'None'
        for _, row in log_df.iterrows():
            mask = (master_df['minute'] >= row['Start_DT']) & (master_df['minute'] <= row['End_DT'])
            master_df.loc[mask, 'Workout_Type'] = row['Workout_Type']

    # Final Output and Success Message
    master_df.to_csv(master_path, index=False)
    print(f"SUCCESS: Master DB saved with {master_df.shape[0]} rows and {master_df.shape[1]} columns.")
else:
    print("CRITICAL: No data found to merge.")