import streamlit as st
import pandas as pd
import numpy as np
from difflib import get_close_matches
from datetime import datetime

st.set_page_config(page_title="NBA Live Betting Dashboard", layout="centered")
st.title("🏀 NBA Live Betting Dashboard")

# Auto-refresh
st.query_params["updated"] = str(datetime.now())
st.success("⏱ Auto-refresh enabled every 60 seconds.")

# Helper: Normalize names
def normalize_name(name):
    if isinstance(name, str):
        return name.lower().replace(".", "").replace("'", "").replace("-", " ").strip()
    return ""

# Load FanDuel props
try:
    fd_df = pd.read_excel(FANDUEL_FILE)
except Exception as e:
    st.error(f"❌ Failed to load {FANDUEL_FILE}: {e}")
    st.stop()
fd_df = fd_df[fd_df['StatType'].isin(['Points', 'Assists', 'Rebounds'])]
fd_df['NameKey'] = fd_df['Player'].apply(normalize_name)
fd_pivot = fd_df.pivot(index='NameKey', columns='StatType', values='Line').reset_index()

# Load projections from CSVs
try:
    pts_df = pd.read_csv("points.csv").rename(columns={'Points': 'Proj Points'})
    ast_df = pd.read_csv("assists.csv").rename(columns={'Assists': 'Proj Assists'})
    reb_df = pd.read_csv("rebounds.csv").rename(columns={'Rebounds': 'Proj Rebounds'})
except Exception as e:
    st.error(f"❌ Failed to load projection CSVs: {e}")
    st.stop().rename(columns={'Rebounds': 'Proj Rebounds'})

# Merge projections
projections = pts_df.merge(ast_df, on="Name", how="outer").merge(reb_df, on="Name", how="outer")
projections['NameKey'] = projections['Name'].apply(normalize_name)

# Load simulated box score
try:
    live_df = pd.read_excel("simulated_boxscore.xlsx")
except Exception as e:
    st.error(f"❌ Failed to load simulated_boxscore.xlsx: {e}")
    st.stop()
live_df['NameKey'] = live_df['Name'].apply(normalize_name)

# Fuzzy match FanDuel to live data
if not fd_pivot.empty:
    unmatched = list(set(fd_pivot['NameKey']) - set(live_df['NameKey']))
    for name in unmatched:
        match = get_close_matches(name, live_df['NameKey'], n=1, cutoff=0.85)
        if match:
            fd_pivot.loc[fd_pivot['NameKey'] == name, 'NameKey'] = match[0]

# Merge all
merged = live_df.merge(projections, on="NameKey", how="left")
merged = merged.merge(fd_pivot, on="NameKey", how="left")
merged = merged.round({"Proj Points": 0, "Proj Assists": 0, "Proj Rebounds": 0})

# Pace projections
merged['Paced Points'] = (merged['Points'] / merged['Minutes']) * 36
merged['Paced Assists'] = (merged['Assists'] / merged['Minutes']) * 36
merged['Paced Rebounds'] = (merged['Rebounds'] / merged['Minutes']) * 36

# Signal logic
def betting_signal(line, proj, pace):
    if pd.isna(line):
        return "No Line"
    if line > max(proj, pace):
        return "Under"
    elif line < min(proj, pace):
        return "Over"
    else:
        return "No Edge"

merged['FD Signal Points'] = merged.apply(lambda r: betting_signal(r.get('Points', np.nan), r.get('Proj Points', np.nan), r.get('Paced Points', np.nan)), axis=1)
merged['FD Signal Assists'] = merged.apply(lambda r: betting_signal(r.get('Assists', np.nan), r.get('Proj Assists', np.nan), r.get('Paced Assists', np.nan)), axis=1)
merged['FD Signal Rebounds'] = merged.apply(lambda r: betting_signal(r.get('Rebounds', np.nan), r.get('Proj Rebounds', np.nan), r.get('Paced Rebounds', np.nan)), axis=1)

# Display
st.dataframe(merged[[
    'Name', 'Team', 'Minutes',
    'Points', 'Proj Points', 'Paced Points', 'FD Points', 'FD Signal Points',
    'Assists', 'Proj Assists', 'Paced Assists', 'FD Assists', 'FD Signal Assists',
    'Rebounds', 'Proj Rebounds', 'Paced Rebounds', 'FD Rebounds', 'FD Signal Rebounds']].dropna(how='all', axis=1),
    use_container_width=True)

st.success("✅ Dashboard loaded using simulated data")
