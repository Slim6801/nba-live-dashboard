# nba_web_dashboard.py
import streamlit as st
import pandas as pd
from nba_api.live.nba.endpoints import scoreboard, boxscore
import re
import unicodedata
from datetime import datetime

st.set_page_config(page_title="NBA Live Betting Dashboard", layout="centered", initial_sidebar_state="auto")

# Auto-refresh every 60 seconds
st.query_params["updated"] = str(datetime.now())
st.experimental_rerun_delay = 60

# ----------- HELPERS -----------
def normalize_name(name):
    if pd.isna(name): return ''
    return ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn').lower().strip()

def parse_minutes(minutes):
    if isinstance(minutes, (int, float)): return float(minutes)
    if isinstance(minutes, str):
        match = re.match(r'PT(\d+)M([\d.]+)S', minutes)
        if match:
            mins = int(match.group(1))
            secs = float(match.group(2))
            return round(mins + secs / 60, 2)
    return 0.0

def pace_project(stat, minutes):
    return round(stat / minutes * 36, 0) if minutes > 0 else 0

def betting_signal(fd_line, proj, pace):
    if pd.isna(fd_line) or pd.isna(proj) or pd.isna(pace): return "No Line"
    if fd_line > max(proj, pace): return "Under"
    if fd_line < min(proj, pace): return "Over"
    return "No Edge"

# ----------- LOAD DATA -----------
PROJECTION_FILE = "NBA BasketBall 24-25 SportsBook-Slim6801.xlsm"
FANDUEL_FILE = "fanduel_player_props.xlsx"

# Game mode toggle
sim_mode = st.sidebar.checkbox("Simulation Mode", value=not scoreboard.ScoreBoard().get_dict()['scoreboard']['games'])

if sim_mode:
    st.sidebar.markdown("📁 Using simulated box score")
    SIMULATED_FILE = "simulated_boxscore.xlsx"
    live_df = pd.read_excel(SIMULATED_FILE)
    live_df['NameKey'] = live_df['Name'].apply(normalize_name)
    game_choice = "Simulated Game"
else:
    # Game selection
    games = scoreboard.ScoreBoard().get_dict()['scoreboard']['games']
    if not games:
        st.warning("No live NBA games today. The dashboard will activate when games are in progress.")
        st.stop()

    

    # Live stats
    box = boxscore.BoxScore(game_id=game_id)
    data = box.get_dict()['game']
    players = []
    for team in ['awayTeam', 'homeTeam']:
        for p in data[team]['players']:
            stats = p['statistics']
            players.append({
                'Name': f"{p['firstName']} {p['familyName']}",
                'Team': data[team]['teamTricode'],
                'Points': stats['points'],
                'Assists': stats['assists'],
                'Rebounds': stats['reboundsTotal'],
                'Minutes': parse_minutes(stats['minutes'])
            })
    live_df = pd.DataFrame(players)
    live_df['NameKey'] = live_df['Name'].apply(normalize_name)


# Initialize fallback for missing_players in case FanDuel block hasn't run yet
missing_players = []

if missing_players:
    st.sidebar.markdown("---")
    st.sidebar.warning("⚠️ Players not matched to live stats:")
    for name in missing_players:
        st.sidebar.text(f"- {name}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Live NameKeys:**")
    for name in sorted(set(live_df['NameKey'])):
        st.sidebar.text(name)

    st.sidebar.markdown("**FanDuel NameKeys:**")
    for name in sorted(set(fd_df['NameKey'])):
        st.sidebar.text(name)

# Projections
proj = pd.read_excel(PROJECTION_FILE, sheet_name=None)
pts_df = proj['POINTS'].rename(columns={'Points': 'Proj Points'})
reb_df = proj['REBOUNDS'].rename(columns={'Rebounds': 'Proj Rebounds'})
ast_df = proj['ASSISTS'].rename(columns={'Assists': 'Proj Assists'})

for df in [pts_df, reb_df, ast_df]:
    df['NameKey'] = df['Name'].apply(normalize_name)


# Force a test match so signals appear
live_df.loc[live_df['Name'].str.contains('Jokic', case=False), 'Name'] = 'Nikola Jokic'
live_df['NameKey'] = live_df['Name'].apply(normalize_name)

# FanDuel lines
try:
    fd_df = pd.read_excel(FANDUEL_FILE)
    # Force Jokic match
    fd_df.loc[fd_df['Player'].str.contains('Jokic', case=False), 'Player'] = 'Nikola Jokic'
    fd_df['NameKey'] = fd_df['Player'].apply(normalize_name)
    fd_df['StatType'] = fd_df['StatType'].str.title()
    fd_df['FD_Line'] = fd_df['Line'].apply(lambda x: float(str(x).split()[0]) if isinstance(x, str) else None)
    fd_df = fd_df[fd_df['StatType'].isin(['Points', 'Assists', 'Rebounds'])]

    all_namekeys = set(fd_df['NameKey'])
    matched_keys = set(live_df['NameKey'])
    missing_players = list(all_namekeys - matched_keys)

    fd_pivot = fd_df.pivot(index='NameKey', columns='StatType', values='FD_Line').reset_index()
    fd_pivot.columns.name = None
    fd_pivot.rename(columns={'Points': 'FD Points', 'Rebounds': 'FD Rebounds', 'Assists': 'FD Assists'}, inplace=True)
except:
    fd_pivot = pd.DataFrame()
    missing_players = []

from difflib import get_close_matches

# Fuzzy match unmatched players
if fd_pivot.empty is False:
    unmatched = list(set(fd_df['NameKey']) - set(live_df['NameKey']))
    for name in unmatched:
        match = get_close_matches(name, live_df['NameKey'], n=1, cutoff=0.85)
        if match:
            fd_df.loc[fd_df['NameKey'] == name, 'NameKey'] = match[0]

# Merge data
merged = live_df.merge(pts_df[['NameKey', 'Proj Points']], on='NameKey', how='left') \
                 .merge(ast_df[['NameKey', 'Proj Assists']], on='NameKey', how='left') \
                 .merge(reb_df[['NameKey', 'Proj Rebounds']], on='NameKey', how='left')
if not fd_pivot.empty:
    merged = merged.merge(fd_pivot, on='NameKey', how='left')

merged['Paced Points'] = merged.apply(lambda r: pace_project(r['Points'], r['Minutes']), axis=1)
merged['Paced Assists'] = merged.apply(lambda r: pace_project(r['Assists'], r['Minutes']), axis=1)
merged['Paced Rebounds'] = merged.apply(lambda r: pace_project(r['Rebounds'], r['Minutes']), axis=1)

merged['FD Signal Points'] = merged.apply(lambda r: betting_signal(r.get('FD Points'), r['Proj Points'], r['Paced Points']), axis=1)
merged['FD Signal Assists'] = merged.apply(lambda r: betting_signal(r.get('FD Assists'), r['Proj Assists'], r['Paced Assists']), axis=1)
merged['FD Signal Rebounds'] = merged.apply(lambda r: betting_signal(r.get('FD Rebounds'), r['Proj Rebounds'], r['Paced Rebounds']), axis=1)

# Round numbers
numeric_cols = ['Points', 'Assists', 'Rebounds', 'Proj Points', 'Proj Assists', 'Proj Rebounds', 'Paced Points', 'Paced Assists', 'Paced Rebounds']
for col in numeric_cols:
    if col in merged.columns:
        merged[col] = merged[col].round(0).astype('Int64')

# Display
st.title("🏀 NBA Live Betting Dashboard")
st.caption(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown("### Game: " + game_choice)

# Columns to display
cols = ['Name', 'Team', 'Minutes', 'Points', 'Proj Points', 'Paced Points']
if 'FD Points' in merged.columns:
    cols += ['FD Points', 'FD Signal Points']
cols += ['Assists', 'Proj Assists', 'Paced Assists']
if 'FD Assists' in merged.columns:
    cols += ['FD Assists', 'FD Signal Assists']
cols += ['Rebounds', 'Proj Rebounds', 'Paced Rebounds']
if 'FD Rebounds' in merged.columns:
    cols += ['FD Rebounds', 'FD Signal Rebounds']

# Color highlighting
import numpy as np

def highlight_signal(val):
    color_map = {
        "Over": "#C6EFCE",
        "Under": "#FFC7CE",
        "No Edge": "#D9D9D9",
        "No Line": "#FFEB9C"
    }
    return f"background-color: {color_map.get(val, '')}" if isinstance(val, str) else ""

styled_df = merged[cols].sort_values(by='Minutes', ascending=False).style
for col in styled_df.data.columns:
    if 'Signal' in col:
        styled_df = styled_df.applymap(highlight_signal, subset=[col])

st.dataframe(styled_df.set_table_styles([
    {'selector': 'thead th', 'props': [('font-size', '14px')]},
    {'selector': 'td', 'props': [('font-size', '13px')]}
]), use_container_width=True)

st.markdown("---")
st.success("⏱ Auto-refresh enabled every 60 seconds.")

# Debugging: compare NameKeys between sources
with st.expander("🛠 Show all NameKeys for Debugging"):
    st.markdown("### 🎯 NameKey Match Check")
    st.markdown("**Live Data NameKeys:**")
    st.write(sorted(set(live_df['NameKey'])))

    if 'fd_df' in locals() and not fd_df.empty:
        st.markdown("**FanDuel Prop NameKeys:**")
        st.write(sorted(set(fd_df['NameKey'])))
        st.markdown("**Missing FanDuel players (no match in live stats):**")
        st.write(missing_players)
    else:
        st.warning("No FanDuel prop data loaded.")
    # initialize cleanly
missing_players = []


