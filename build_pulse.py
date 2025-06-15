"""
Daily Pulse Builder for Casting Platform Data

Generates an aggregated summary of casting breakdowns with trend analysis
to help industry analysts track key metrics over time.
"""

import pandas as pd
import numpy as np
import argparse
from textblob import TextBlob
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REGION_MAPPING = {
    'NA': ['us', 'united states', 'canada', 'mexico', 'los angeles', 'atlanta', 'chicago', 'toronto', 'vancouver'],
    'EU': ['uk', 'united kingdom', 'germany', 'france', 'italy', 'spain', 'netherlands', 'london', 'paris', 'berlin'],
    'AP': ['india', 'china', 'japan', 'korea', 'australia', 'singapore', 'hong kong', 'new zealand', 'thailand'],
    'LA': ['brazil', 'argentina', 'chile', 'colombia', 'peru', 'venezuela', 'mexico city']
}

PROJECT_TYPE_MAPPING = {
    'F': ['film', 'movie', 'feature'],
    'T': ['tv', 'series', 'streaming', 'show', 'episode'],
    'C': ['commercial', 'advertisement', 'ad'],
    'V': []  # default
}

def map_region(location):
    if pd.isna(location):
        return 'NA'
    loc = str(location).lower()
    for code, keywords in REGION_MAPPING.items():
        if any(k in loc for k in keywords):
            return code
    return 'NA'

def map_project_type(project_type):
    if pd.isna(project_type):
        return 'V'
    pt = str(project_type).lower()
    for code, keywords in PROJECT_TYPE_MAPPING.items():
        if any(k in pt for k in keywords):
            return code
    return 'V'

def extract_rate(text):
    if pd.isna(text):
        return np.nan
    nums = re.findall(r'\d+\.?\d*', str(text))
    return float(nums[0]) if nums else np.nan

def is_lead(role_type):
    if pd.isna(role_type):
        return False
    return any(term in str(role_type).lower() for term in ['lead', 'principal', 'main', 'starring'])

def is_union(union_status):
    if pd.isna(union_status):
        return False
    status = str(union_status).lower()
    return 'non-union' not in status and any(k in status for k in ['sag', 'aftra', 'equity', 'union'])

def calc_sentiment(text):
    if pd.isna(text):
        return 0.0
    try:
        polarity = TextBlob(str(text)).sentiment.polarity
        return round(polarity * 20) / 20  # rounds to nearest 0.05
    except:
        return 0.0

def has_ai_keywords(text):
    if pd.isna(text):
        return False
    return any(term in str(text).lower() for term in ['ai', 'robot', 'android', 'artificial intelligence', 'cyborg', 'machine learning'])

def clamp(value, min_val=0.0, max_val=1.0):
    return max(min_val, min(max_val, value))

def bucket_and_aggregate(df):
    results = []
    grouped = df.groupby(['date_utc', 'region_code', 'proj_type_code'])

    for (date, region, proj), group in grouped:
        if len(group) < 5:
            continue

        total = len(group)
        lead_pct = clamp(group['is_lead'].sum() / total)
        union_pct = clamp(group['is_union'].sum() / total)
        ai_pct = clamp(group['has_ai'].sum() / total)

        valid_rates = group['rate_val'].dropna()
        median_rate = int(round(valid_rates.median() / 250)) * 250 if not valid_rates.empty else None

        avg_sentiment = clamp(group['sentiment'].mean(), -1.0, 1.0)

        results.append({
            'date_utc': date,
            'region_code': region,
            'proj_type_code': proj,
            'role_count_day': total,
            'lead_share_pct_day': round(lead_pct, 1),
            'union_share_pct_day': round(union_pct, 1),
            'median_rate_day_usd': median_rate,
            'sentiment_avg_day': round(avg_sentiment, 2),
            'theme_ai_share_pct_day': round(ai_pct, 1)
        })

    return pd.DataFrame(results)

def process(input_file, output_file):
    logging.info(f"Reading input from {input_file}...")
    df = pd.read_csv(input_file)
    df['posted_date'] = pd.to_datetime(df['posted_date'], errors='coerce')
    df['date_utc'] = df['posted_date'].dt.date

    df['region_code'] = df['work_location'].apply(map_region)
    df['proj_type_code'] = df['project_type'].apply(map_project_type)
    df['is_lead'] = df['role_type'].apply(is_lead)
    df['is_union'] = df['union'].apply(is_union)
    df['rate_val'] = df['rate'].apply(extract_rate)
    df['sentiment'] = df['role_description'].apply(calc_sentiment)
    df['has_ai'] = df['role_description'].apply(has_ai_keywords)

    pulse = bucket_and_aggregate(df)
    pulse = pulse.sort_values(['date_utc', 'region_code', 'proj_type_code'])

    logging.info(f"Writing output to {output_file}...")
    pulse.to_csv(output_file, index=False)
    logging.info("Done. Summary:")
    logging.info(f"Dates: {pulse['date_utc'].min()} to {pulse['date_utc'].max()}")
    logging.info(f"Regions: {sorted(pulse['region_code'].unique())}")
    logging.info(f"Project Types: {sorted(pulse['proj_type_code'].unique())}")

def main():
    parser = argparse.ArgumentParser(description="Build Daily Casting Pulse")
    parser.add_argument('--input', required=True, help='Input breakdown CSV file')
    parser.add_argument('--output', required=True, help='Output summary CSV file')
    args = parser.parse_args()
    process(args.input, args.output)

if __name__ == "__main__":
    main()
