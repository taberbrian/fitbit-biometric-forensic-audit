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
from google.colab import drive
from functools import reduce

# =============================================================================
# FITBIT MASTER DATABASE BUILDER
# Run monthly after downloading a fresh Fitbit export.
# Outputs: fitbit_master_database.csv in your Fitbit_Data folder.
# =============================================================================

# 1. Environment Setup
drive.mount('/content/drive')
folder_path = '/content/drive/MyDrive/Fitbit_Data'
master_path = os.path.join(folder_path, 'fitbit_master_database.csv')
log_path    = os.path.join(folder_path, 'workout_log.csv')

# =============================================================================
# 2. Data Dictionary
# =============================================================================
data_dict = {
    'activity':          [],
    'altitude':          [],
    'body_response':     [],
    'calories':          [],
    'cardio':            [],
    'distance':          [],
    'steps':             [],
    'temperature':       [],   # daily — joined by date not minute
    'hr':                [],
    'spo2':              [],
    'active_mins':       [],
    'zone_mins':         [],
    'workload':          [],
    'observed_interval': []
}

all_csvs = glob.glob(
    os.path.join(folder_path, "**", "*.[cC][sS][vV]"), recursive=True
)
print(f"--- Found {len(all_csvs)} CSV files to process ---\n")

processed = 0
skipped   = 0
errors    = 0

for file in all_csvs:
    filename = os.path.basename(file).lower()

    # Skip the output files themselves
    if filename in ['fitbit_master_database.csv', 'workout_log.csv']:
        continue

    try:
        df = pd.read_csv(file)
        if df.empty:
            skipped += 1
            continue

        # ------------------------------------------------------------------
        # Standard timestamp processing — convert ZST → CST and floor to minute
        # ------------------------------------------------------------------
        if 'timestamp' in df.columns:
            df['timestamp'] = (
                pd.to_datetime(df['timestamp'], utc=True)
                .dt.tz_convert('America/Chicago')
                .dt.tz_localize(None)
            )
            df['minute'] = df['timestamp'].dt.floor('min')
        elif 'minute' not in df.columns:
            # No time column at all — skip
            skipped += 1
            continue

        # ------------------------------------------------------------------
        # METRICS — order matters: more specific checks before general ones
        # ------------------------------------------------------------------

        # 1) Oxygen Saturation (SpO2)
        if 'minute spo2' in filename:
            df_clean = (
                df.groupby('minute')['value']
                .mean().round(1).reset_index()
                .rename(columns={'value': 'spo2'})
            )
            data_dict['spo2'].append(df_clean)
            processed += 1

        # 2) Cardio Observed Interval — must come BEFORE cardio_load check
        elif 'cardio_load_observed_interval' in filename:
            ts_col = next(
                (c for c in df.columns
                 if 'timestamp' in c.lower() or 'date' in c.lower()), None
            )
            if ts_col:
                df['date'] = pd.to_datetime(df[ts_col]).dt.date
                min_col = next((c for c in df.columns if 'min' in c.lower() and 'load' in c.lower()), None)
                max_col = next((c for c in df.columns if 'max' in c.lower() and 'load' in c.lower()), None)
                if min_col and max_col:
                    df_clean = (
                        df.drop_duplicates(subset=['date'])
                        [['date', min_col, max_col]]
                        .rename(columns={min_col: 'min_capacity', max_col: 'max_capacity'})
                    )
                    data_dict['observed_interval'].append(df_clean)
                    processed += 1

        # 3) Cardio Acute/Chronic Workload Ratio — must come BEFORE cardio_load check
        elif 'cardio_acute_chronic_workload_ratio' in filename:
            ts_col = next(
                (c for c in df.columns
                 if 'timestamp' in c.lower() or 'date' in c.lower()), None
            )
            if ts_col and 'ratio' in df.columns:
                df['date'] = pd.to_datetime(df[ts_col]).dt.date
                df_clean = (
                    df.drop_duplicates(subset=['date'])
                    [['date', 'ratio', 'label']]
                    .rename(columns={
                        'ratio': 'workload_ratio',
                        'label': 'workload_status'
                    })
                )
                data_dict['workload'].append(df_clean)
                processed += 1

        # 4) Active Zone Minutes — must come BEFORE active_minutes check
        elif 'active_zone_minutes' in filename:
            if 'heart rate zone' in df.columns:
                df_clean = (
                    df.groupby('minute')['heart rate zone']
                    .first().reset_index()
                    .rename(columns={'heart rate zone': 'active_hr_zone'})
                )
                data_dict['zone_mins'].append(df_clean)
                processed += 1

        # 5) Active Minutes (light/moderate/very) — after zone_minutes check
        elif 'active_minutes' in filename:
            cols = [c for c in ['light', 'moderate', 'very'] if c in df.columns]
            if cols:
                df_clean = df.groupby('minute')[cols].sum().reset_index()
                data_dict['active_mins'].append(df_clean)
                processed += 1

        elif filename.startswith('heart_rate'):
            if 'beats per minute' in df.columns:
                df_clean = (
                    df.groupby('minute')['beats per minute']
                    .mean().round(0).reset_index()
                    .rename(columns={'beats per minute': 'heart_rate'})
                )
                data_dict['hr'].append(df_clean)
                processed += 1

        # 6) Body temperature — daily file, one reading per day
        #    Store by date for daily join later (same as workload)
        elif filename.startswith('body_temperature'):
            if 'temperature celsius' in df.columns:
                df['date'] = df['minute'].dt.date
                df_clean = (
                    df.groupby('date')['temperature celsius']
                    .mean().round(2).reset_index()
                    .rename(columns={'temperature celsius': 'temperature'})
                )
                data_dict['temperature'].append(df_clean)
                processed += 1

        elif filename.startswith('steps'):
            if 'steps' in df.columns:
                df_clean = df.groupby('minute')['steps'].sum().reset_index()
                data_dict['steps'].append(df_clean)
                processed += 1

        elif filename.startswith('calories_in_heart_rate_zone'):
            if 'kcal' in df.columns:
                df_clean = (
                    df.groupby('minute')['kcal']
                    .sum().round(4).reset_index()
                    .rename(columns={'kcal': 'calories'})
                )
                data_dict['calories'].append(df_clean)
                processed += 1

        elif filename.startswith('body_response'):
            cols_to_extract = [
                'ceda magnitude real micro siemens',
                'skin temperature magnitude celsius',
                'hr mean bpm',
                'hrv rmssd percentile 05 95',
                'hrv sdnn percentile 05 95'
            ]
            existing = [c for c in cols_to_extract if c in df.columns]
            if existing:
                df_clean = df.groupby('minute')[existing].mean().reset_index()
                df_clean.rename(columns={
                    'hrv rmssd percentile 05 95': 'rmssd',
                    'hrv sdnn percentile 05 95':  'sdnn'
                }, inplace=True)
                data_dict['body_response'].append(df_clean)
                processed += 1

        elif filename.startswith('altitude'):
            if 'gain' in df.columns:
                df_clean = (
                    df.groupby('minute')['gain']
                    .sum().reset_index()
                    .rename(columns={'gain': 'altitude_gain'})
                )
                data_dict['altitude'].append(df_clean)
                processed += 1

        elif filename.startswith('activity_level'):
            if 'level' in df.columns:
                df_clean = df.groupby('minute')['level'].first().reset_index()
                data_dict['activity'].append(df_clean)
                processed += 1

        elif filename.startswith('distance'):
            if 'distance' in df.columns:
                df_clean = df.groupby('minute')['distance'].sum().reset_index()
                data_dict['distance'].append(df_clean)
                processed += 1

        # 7) Cardio load — AFTER observed_interval and ratio checks
        elif filename.startswith('cardio_load'):
            cols = [c for c in ['workout', 'background', 'total'] if c in df.columns]
            if cols:
                df_clean = df.groupby('minute')[cols].mean().reset_index()
                data_dict['cardio'].append(df_clean)
                processed += 1

        else:
            skipped += 1

    except Exception as e:
        print(f"  ERROR — {filename}: {e}")
        errors += 1

print(f"File processing complete: {processed} processed | {skipped} skipped | {errors} errors\n")

# =============================================================================
# 3. Build Master Table — merge all minute-level sources
# =============================================================================
minute_keys = [
    'hr', 'body_response', 'spo2', 'active_mins', 'zone_mins',
    'activity', 'altitude', 'calories', 'cardio', 'distance', 'steps'
    # Note: 'temperature' is daily-level, merged in section 4 by date
]

master_components = []
for key in minute_keys:
    if data_dict[key]:
        stacked = (
            pd.concat(data_dict[key], ignore_index=True)
            .drop_duplicates(subset=['minute'])
        )
        master_components.append(stacked)
        print(f"  Merged '{key}': {len(stacked):,} rows")

if not master_components:
    print("CRITICAL: No data found to merge.")
    raise SystemExit

master_df = reduce(
    lambda left, right: pd.merge(left, right, on='minute', how='outer'),
    master_components
)
master_df = master_df.sort_values('minute').reset_index(drop=True)
master_df['date'] = master_df['minute'].dt.date
print(f"\nBase master table: {master_df.shape[0]:,} rows × {master_df.shape[1]} columns")

# =============================================================================
# 4. Merge Daily Metrics — workload, observed interval, body temperature
#    All joined by date since they have one value per day, not per minute
# =============================================================================

# Workload ratio
if data_dict['workload']:
    workload_df = (
        pd.concat(data_dict['workload'])
        .drop_duplicates(subset=['date'])
    )
    master_df = pd.merge(master_df, workload_df, on='date', how='left')
    print(f"Workload ratio merged: {workload_df.shape[0]} daily records")

# Observed interval (min/max capacity)
if data_dict['observed_interval']:
    obs_df = (
        pd.concat(data_dict['observed_interval'])
        .drop_duplicates(subset=['date'])
    )
    master_df = pd.merge(master_df, obs_df, on='date', how='left')
    print(f"Observed interval merged: {obs_df.shape[0]} daily records")

# Body temperature — one reading per day, broadcast to all minutes of that day
if data_dict['temperature']:
    temp_df = (
        pd.concat(data_dict['temperature'], ignore_index=True)
        .drop_duplicates(subset=['date'])
    )
    master_df = pd.merge(master_df, temp_df, on='date', how='left')
    print(f"Body temperature merged: {temp_df.shape[0]} daily records")

master_df.drop(columns=['date'], inplace=True)

# =============================================================================
# 5. Apply Workout Tags from manual log
# =============================================================================
if os.path.exists(log_path):
    log_df = pd.read_csv(log_path)
    log_df['Start_DT'] = pd.to_datetime(log_df['Date'] + ' ' + log_df['Start_Time'])
    log_df['End_DT']   = pd.to_datetime(log_df['Date'] + ' ' + log_df['End_Time'])

    master_df['Workout_Type'] = 'None'
    for _, row in log_df.iterrows():
        mask = (
            (master_df['minute'] >= row['Start_DT']) &
            (master_df['minute'] <= row['End_DT'])
        )
        master_df.loc[mask, 'Workout_Type'] = row['Workout_Type']

    tagged = (master_df['Workout_Type'] != 'None').sum()
    print(f"Workout tags applied: {tagged:,} minutes tagged across {len(log_df)} sessions")
else:
    master_df['Workout_Type'] = 'None'
    print("WARNING: workout_log.csv not found — all rows tagged as 'None'")

# =============================================================================
# 6. Data Quality Cleanup
# Replace known sensor dropout / artifact values with NaN before saving.
# This prevents bad readings from polluting charts and KPI calculations.
# =============================================================================
print("\n--- Data quality cleanup ---")

# SpO2: Fitbit records ~50 as a sentinel when the watch has no skin contact.
# Anything below 90% is physiologically implausible while wearing the watch.
if 'spo2' in master_df.columns:
    n = (master_df['spo2'] < 90).sum()
    master_df.loc[master_df['spo2'] < 90, 'spo2'] = float('nan')
    print(f"  SpO2:       replaced {n:,} dropout readings (<90%) with NaN")

# Heart rate: 0 bpm and values below 20 bpm are sensor loss artifacts.
if 'heart_rate' in master_df.columns:
    n = (master_df['heart_rate'] <= 20).sum()
    master_df.loc[master_df['heart_rate'] <= 20, 'heart_rate'] = float('nan')
    print(f"  Heart rate: replaced {n:,} implausible readings (<=20 bpm) with NaN")

# CEDA: All-zero readings indicate no skin contact, not zero sympathetic arousal.
ceda_col = 'ceda magnitude real micro siemens'
if ceda_col in master_df.columns:
    n = (master_df[ceda_col] == 0).sum()
    master_df.loc[master_df[ceda_col] == 0, ceda_col] = float('nan')
    print(f"  CEDA:       replaced {n:,} zero readings with NaN")

# Skin temperature: values outside 25–42°C are sensor artifacts.
skin_col = 'skin temperature magnitude celsius'
if skin_col in master_df.columns:
    mask = (master_df[skin_col] < 25) | (master_df[skin_col] > 42)
    n = mask.sum()
    master_df.loc[mask, skin_col] = float('nan')
    print(f"  Skin temp:  replaced {n:,} out-of-range readings with NaN")

# Calories: negative calorie values are calculation artifacts.
if 'calories' in master_df.columns:
    n = (master_df['calories'] < 0).sum()
    master_df.loc[master_df['calories'] < 0, 'calories'] = float('nan')
    print(f"  Calories:   replaced {n:,} negative values with NaN")

# Steps: negative step counts are impossible.
if 'steps' in master_df.columns:
    n = (master_df['steps'] < 0).sum()
    master_df.loc[master_df['steps'] < 0, 'steps'] = float('nan')
    print(f"  Steps:      replaced {n:,} negative values with NaN")

# =============================================================================
# 7. Save
# =============================================================================
master_df.to_csv(master_path, index=False)

print(f"\nSUCCESS: Master DB saved to {master_path}")
print(f"  {master_df.shape[0]:,} rows  ×  {master_df.shape[1]} columns")
print(f"  Date range: {master_df['minute'].min()} → {master_df['minute'].max()}")
print(f"\nColumn summary:")
for col in master_df.columns:
    non_null = master_df[col].notna().sum()
    pct = round(non_null / len(master_df) * 100, 1)
    print(f"  {col:<45} {non_null:>8,} non-null ({pct}%)")