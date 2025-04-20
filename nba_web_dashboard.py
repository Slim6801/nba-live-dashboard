import streamlit as st
import pandas as pd
from nba_api.live.nba.endpoints import boxscore, playbyplay
from nba_api.stats.endpoints import ScoreboardV2
from nba_api.stats.static import teams
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh
import os
import subprocess
from fuzzywuzzy import process
import requests
import numpy as np

# --- Page setup ---
st.set_page_config(page_title="NBA Live Betting Dashboard", page_icon="🏀", layout="wide")

# --- Constants ---
PROJ_PATH = "nba_model_projections_advanced.xlsx"
FD_PATH = "fanduel_player_props.xlsx"
ACCURACY_LOG = "model_accuracy_log.csv"
GAME_LOG_PATH = "game_logs.csv"
SNAPSHOT_DIR = "snapshots"
ODDS_API_KEY = "your_oddsapi_key_here"  # Replace with your key
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# Load NBA teams data for abbreviation lookup
nba_teams = {team['id']: team['abbreviation'] for team in teams.get_teams()}

# --- Title ---
st.title("🏀 NBA Live Betting Dashboard")
st.markdown("Real-time player stats, model projections, FanDuel lines, and betting signals.")

# --- Sidebar ---
with st.sidebar:
    st.header("🔄 Auto Refresh Settings")
    auto_refresh = st.toggle("Enable Auto Refresh", True)
    refresh_interval = st.slider("Refresh Interval (seconds)", 15, 300, 60, step=15)
    if auto_refresh:
        st_autorefresh(interval=refresh_interval * 1000)
    if st.button("🔃 Manual Refresh"):
        st.rerun()

    st.header("🧠 Model Training")
    if st.button("🔁 Retrain Model Now", key="sidebar_train"):
        with st.spinner("Training model in background. This may take up to 2 minutes..."):
            try:
                script_path = os.path.join(os.getcwd(), "train_nba_model.py")
                subprocess.Popen(["python", script_path])
                st.success("✅ Training started in the background. Refresh after 2–3 minutes to see updated projections.")
                st.info(f"🕒 Started at: {datetime.now().strftime('%I:%M %p')}. Check for updates around: {(datetime.now() + timedelta(minutes=2)).strftime('%I:%M %p')}")
            except Exception as e:
                st.error(f"❌ Failed to retrain model: {e}")

# --- Fetch today's schedule ---
date_selected = datetime.now(pytz.timezone("US/Eastern")).date()
games_today = {}
try:
    date_str = date_selected.strftime('%m/%d/%Y')
    scoreboard = ScoreboardV2(game_date=date_str)
    data_frames = scoreboard.get_data_frames()
    sched = data_frames[0]
    st.sidebar.write(f"🔍 Loaded {len(sched)} games for {date_str}")
    for _, row in sched.iterrows():
        home_id = row.get('HOME_TEAM_ID')
        visitor_id = row.get('VISITOR_TEAM_ID')
        home = nba_teams.get(home_id, 'HOME')
        visitor = nba_teams.get(visitor_id, 'AWAY')
        matchup = f"{visitor} @ {home}"
        status = row.get('GAME_STATUS_TEXT', 'Unknown')
        game_id = row.get('GAME_ID', None)
        if game_id:
            try:
                box = boxscore.BoxScore(game_id=game_id).get_dict()
                away_score = box['game']['awayTeam']['score']
                home_score = box['game']['homeTeam']['score']
                score = f"{away_score} - {home_score}"
            except:
                score = "0 - 0"
            label = f"{matchup} | {status}"
            games_today[label] = {
                'id': game_id,
                'matchup': matchup,
                'status': status,
                'score': score
            }
except Exception as e:
    st.sidebar.error(f"❌ Could not fetch schedule: {e}")

with st.sidebar:
    if games_today:
        st.session_state['selected_game_label'] = st.selectbox("Select One Game", list(games_today.keys()), key="select_game")
    else:
        st.info("No games found for today.")

    st.header("🚑 Inactive Players")
    inactive_input = st.text_area("Enter inactive players (one per line):", "")
    inactive_players = [p.strip().lower() for p in inactive_input.split("\n") if p.strip()]

    st.header("📊 Signal Thresholds")
    signal_margin = st.slider("Pace Margin for Signal (e.g. +3 means pace must exceed projection by 3)", 1, 10, 3)

# --- Load Projections and FanDuel Lines ---
def load_projections():
    try:
        proj_df = pd.read_excel(PROJ_PATH, engine='openpyxl')
        proj_df.columns = proj_df.columns.str.upper()
        proj_df = proj_df[proj_df['PLAYER'].notna()].copy()
        proj_df['PLAYER_CLEAN'] = proj_df['PLAYER'].astype(str).str.lower().str.replace(r"[.\'-]", "", regex=True).str.strip()
        proj_df['PRA'] = proj_df['PREDICTED PTS'] + proj_df['PREDICTED AST'] + proj_df['PREDICTED REB']

        # Add confidence from accuracy log
        if os.path.exists(ACCURACY_LOG):
            acc_log = pd.read_csv(ACCURACY_LOG, on_bad_lines='skip')
            recent = acc_log.groupby('PLAYER')[['Error PTS', 'Error AST', 'Error REB']].mean().reset_index()
            recent['PLAYER_CLEAN'] = recent['PLAYER'].astype(str).str.lower().str.replace(r"[.\'-]", "", regex=True).str.strip()
            recent['CONFIDENCE'] = 1 - recent[['Error PTS', 'Error AST', 'Error REB']].mean(axis=1)
            proj_df = proj_df.merge(recent[['PLAYER_CLEAN', 'CONFIDENCE']], on='PLAYER_CLEAN', how='left')
        else:
            proj_df['CONFIDENCE'] = 0.5

        # Add PRA trend engine from game logs
        if os.path.exists(GAME_LOG_PATH):
            logs = pd.read_csv(GAME_LOG_PATH)
            logs['PLAYER_CLEAN'] = logs['PLAYER'].astype(str).str.lower().str.replace(r"[.\'-]", "", regex=True).str.strip()
            last5 = logs.sort_values('GAME_DATE', ascending=False).groupby('PLAYER_CLEAN').head(5)
            trend = last5.groupby('PLAYER_CLEAN')[['PTS', 'AST', 'REB']].mean().reset_index()
            trend['TREND_PRA'] = trend['PTS'] + trend['AST'] + trend['REB']
            proj_df = proj_df.merge(trend[['PLAYER_CLEAN', 'TREND_PRA']], on='PLAYER_CLEAN', how='left')

        # Add FD lines from OddsAPI (example for demo purpose)
        if os.path.exists(FD_PATH):
            fd = pd.read_excel(FD_PATH, engine='openpyxl')
            fd.columns = fd.columns.str.upper()
            fd['PLAYER_CLEAN'] = fd['PLAYER'].astype(str).str.lower().str.replace(r"[.\'-]", "", regex=True).str.strip()
            for col in ['PTS LINE', 'REB LINE', 'AST LINE']:
                if col not in fd.columns:
                    fd[col] = None
            proj_df = proj_df.merge(fd[['PLAYER_CLEAN', 'PTS LINE', 'REB LINE', 'AST LINE']], on='PLAYER_CLEAN', how='left')

        return proj_df
    except Exception as e:
        st.warning(f"⚠️ Could not load projections: {e}")
        return pd.DataFrame()

projections = load_projections()

# --- Live Game Stats Viewer ---
st.markdown("---")
selected_game_label = st.session_state.get("selected_game_label", None)
if selected_game_label:
    game_meta = games_today[selected_game_label]
    game_id = game_meta['id']
    matchup = game_meta['matchup']
    score = game_meta['score']
    st.subheader(f"📹 Live Game Stats — {matchup} ({score})")
else:
    st.subheader("📹 Live Game Stats")

try:
    if selected_game_label:
        game_id = games_today[selected_game_label]['id']
        response = boxscore.BoxScore(game_id=game_id)
        raw = response.get_dict()
        if not raw or 'game' not in raw:
            st.info(f"⏳ Waiting for stats for Game ID: {game_id}")
        else:
            players = []
            for side in ['homeTeam', 'awayTeam']:
                team = raw['game'][side]
                for p in team['players']:
                    stats = p.get('statistics', {})
                    minutes_raw = stats.get('minutesCalculated', 'PT0M')
                    try:
                        minutes = int(minutes_raw.replace('PT', '').replace('M', ''))
                    except:
                        minutes = 0
                    if minutes == 0:
                        continue
                    name = f"{p['firstName']} {p['familyName']}"
                    match_row = None
                    pace_pts = pace_ast = pace_reb = pace_pra = None
                    if not projections.empty:
                        match = process.extractOne(name.lower().replace(".", "").replace("'", "").replace("-", "").strip(), projections['PLAYER_CLEAN'], score_cutoff=90)
                        if match:
                            match_row = projections[projections['PLAYER_CLEAN'] == match[0]].iloc[0]
                    signal_pts = signal_ast = signal_reb = signal_pra = confidence_emoji = trend_pra = ""
                    if match_row is not None:
                        pace_pts = round((stats.get('points', 0) / minutes * 36), 1)
                        pace_ast = round((stats.get('assists', 0) / minutes * 36), 1)
                        pace_reb = round((stats.get('reboundsTotal', 0) / minutes * 36), 1)
                        pace_pra = pace_pts + pace_ast + pace_reb
                        proj_pts = match_row['PREDICTED PTS']
                        proj_ast = match_row['PREDICTED AST']
                        proj_reb = match_row['PREDICTED REB']
                        proj_pra = proj_pts + proj_ast + proj_reb
                        trend_pra = match_row.get('TREND_PRA', None)
                        confidence = match_row.get('CONFIDENCE', 0.5)
                        confidence_emoji = "🔥" if confidence > 0.8 else "✅" if confidence > 0.5 else "⚠️"

                        def signal(paced, proj):
                            if paced > proj + signal_margin:
                                return f"🟢 Over {confidence_emoji}"
                            elif paced < proj - signal_margin:
                                return f"🔴 Under {confidence_emoji}"
                            else:
                                return f"🔹 Close {confidence_emoji}"

                        signal_pts = signal(pace_pts, proj_pts)
                        signal_ast = signal(pace_ast, proj_ast)
                        signal_reb = signal(pace_reb, proj_reb)
                        signal_pra = signal(pace_pra, proj_pra)

                    players.append({
                        'Name': name,
                        'Team': team['teamTricode'],
                        'Minutes': minutes,
                        'Points': stats.get('points', 0),
                        'Assists': stats.get('assists', 0),
                        'Rebounds': stats.get('reboundsTotal', 0),
                        'Proj Points': match_row['PREDICTED PTS'] if match_row is not None else None,
                        'Proj Assists': match_row['PREDICTED AST'] if match_row is not None else None,
                        'Proj Rebounds': match_row['PREDICTED REB'] if match_row is not None else None,
                        'Trend PRA': trend_pra,
                        'Paced Points': pace_pts,
                        'Paced Assists': pace_ast,
                        'Paced Rebounds': pace_reb,
                        'Signal PTS': signal_pts,
                        'Signal AST': signal_ast,
                        'Signal REB': signal_reb,
                        'Signal PRA': signal_pra,
                        'Inactive': '✅' if name.lower().strip() in inactive_players else ''
                    })
            df = pd.DataFrame(players)
            if not df.empty:
                st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error(f"⚠️ Failed to fetch live stats: {e}")

