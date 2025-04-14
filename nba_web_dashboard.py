import streamlit as st
import pandas as pd
import numpy as np
from nba_api.live.nba.endpoints import scoreboard, boxscore
from difflib import get_close_matches
from datetime import datetime
import os

st.set_page_config(page_title="NBA Live Betting Dashboard", layout="centered", initial_sidebar_state="auto")
st.title("🏀 NBA Live Betting Dashboard")

# Auto-refresh
st.query_params["updated"] = str(datetime.now())
st.success("⏱ Auto-refresh enabled every 60 seconds.")

# Helper: Normalize names
def normalize_name(name):
    if isinstance(name, str):
        return name.lower().replace(".", "").replace("'", "").replace("-", " ").strip()
    return ""

# Helper: Convert PTxxMxx.xxS format to float minutes
def parse_minutes(time_str):
    if not time_str.startswith("PT"):
        return 0.0
    time_str = time_str[2:].replace("S", "")
    parts = time_str.split("M")
    minutes = int(parts[0]) if parts[0].isdigit() else 0
    seconds = float(parts[1]) if len(parts) > 1 else 0
    return round(minutes + seconds / 60, 2)

# Load FanDuel props
FANDUEL_FILE = "fanduel_player_props.xlsx"
fd_df = pd.read_excel(FANDUEL_FILE)
fd_df = fd_df[fd_df['StatType'].isin(['Points', 'Assists', 'Rebounds'])]
fd_df['NameKey'] = fd_df['Player'].apply(normalize_name)
fd_pivot = fd_df.pivot(index='NameKey', columns='StatType', values='Line').reset_index()

# Load projections from CSVs
pts_df = pd.read_csv("points.csv").rename(columns={'Points': 'Proj Points'})
ast_df = pd.read_csv("assists.csv").rename(columns={'Assists': 'Proj Assists'})
reb_df = pd.read_csv("rebounds.csv").rename(columns={'Rebounds': 'Proj Rebounds'})

# Merge projections
projections = pts_df.merge(ast_df, on="Name", how="outer").merge(reb_df, on="Name", how="outer")
projections['NameKey'] = projections['Name'].apply(normalize_name)

# Game mode: Live vs Sim
sim_mode = st.sidebar.checkbox("Simulation Mode", value=False)

if sim_mode:
    st.sidebar.markdown("📁 Using simulated_boxscore.xlsx")
    live_df = pd.read_excel("simulated_boxscore.xlsx")
    live_df['NameKey'] = live_df['Name'].apply(normalize_name)
    game_choice = "Simulated Game"
else:
    games = scoreboard.ScoreBoard().get_dict()['scoreboard']['games']
    if not games:
        st.warning("No live NBA games today. Enable Simulation Mode to test.")
        st.stop()
    game_options = {f"{g['awayTeam']['teamTricode']} @ {g['homeTeam']['teamTricode']}": g['gameId'] for g in games}
    game_choice = st.sidebar.selectbox("Select a live game:", list(game_options.keys()))
    game_id = game_options[game_choice]

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

# Fuzzy matching FanDuel -> Live data
if not fd_pivot.empty:
    unmatched = list(set(fd_pivot['NameKey']) - set(live_df['NameKey']))
    for name in unmatched:
        match = get_close_matches(name, live_df['NameKey'], n=1, cutoff=0.85)
        if match:
            fd_pivot.loc[fd_pivot['NameKey'] == name, 'NameKey'] = match[0]

# Merge live data + projections + FD lines
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

# Simulated Bet Tracker
if 'selected_bets' not in st.session_state:
    st.session_state.selected_bets = set()

st.markdown("## 📌 Simulated Bets")
with st.form("bet_form"):
    bet_cols = st.multiselect(
        "Select players you would bet on:",
        options=list(merged['Name']),
        default=list(st.session_state.selected_bets)
    )
    submitted = st.form_submit_button("💾 Save Bets")
    if submitted:
        st.session_state.selected_bets = set(bet_cols)

selected_df = merged[merged['Name'].isin(st.session_state.selected_bets)]
if not selected_df.empty:
    st.markdown("### 🎯 Your Simulated Bets")
    st.dataframe(selected_df[['Name', 'Team', 'FD Signal Points', 'FD Signal Assists', 'FD Signal Rebounds']], use_container_width=True)

# Display full dashboard
display_cols = [
    'Name', 'Team', 'Minutes',
    'Points', 'Proj Points', 'Paced Points', 'FD Points', 'FD Signal Points',
    'Assists', 'Proj Assists', 'Paced Assists', 'FD Assists', 'FD Signal Assists',
    'Rebounds', 'Proj Rebounds', 'Paced Rebounds', 'FD Rebounds', 'FD Signal Rebounds'
]

available_cols = [col for col in display_cols if col in merged.columns]
styled_df = merged[available_cols]

st.dataframe(styled_df.set_table_styles([
    {'selector': 'thead th', 'props': [('font-size', '14px')]},
    {'selector': 'td', 'props': [('font-size', '13px')]}
]), use_container_width=True)

# Debug name matches
with st.expander("🛠 Show all NameKeys for Debugging"):
    st.markdown("### 🎯 NameKey Match Check")
    st.markdown("**Live Data NameKeys:**")
    st.write(sorted(set(live_df['NameKey'])))

    if 'fd_df' in locals() and not fd_df.empty:
        st.markdown("**FanDuel Prop NameKeys:**")
        st.write(sorted(set(fd_df['NameKey'])))
        st.markdown("**Missing FanDuel players (no match in live stats):**")
        missing_players = list(set(fd_df['NameKey']) - set(live_df['NameKey']))
        st.write(missing_players)
    else:
        st.warning("No FanDuel prop data loaded.")

