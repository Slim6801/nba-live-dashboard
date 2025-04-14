# 🏀 NBA Live Betting Dashboard

A Streamlit-based real-time NBA dashboard for comparing live player performance against projections and FanDuel betting lines. Includes pace projections, betting signals, fuzzy matching, auto-refresh, and simulation mode.

---

## 🚀 Features

- Live player stats from NBA API
- FanDuel prop line comparison
- Pace-based projections (e.g., 36-minute extrapolation)
- Betting signal logic (Over/Under/No Edge/No Line)
- Color-coded dashboard
- Auto-refresh every 60 seconds
- Fuzzy name matching (for player name cleanup)
- Mobile-friendly layout
- Simulation mode (for no-game testing or training)

---

## 📁 File Structure

```
📦 nba-live-dashboard/
├── nba_web_dashboard.py              # Main Streamlit app
├── convert_projections.py           # Converts .xlsm projections into CSVs
├── points.csv                       # Projected points
├── assists.csv                      # Projected assists
├── rebounds.csv                     # Projected rebounds
├── simulated_boxscore.xlsx          # For testing dashboard in Simulation Mode
├── fanduel_player_props.xlsx        # FanDuel props: Player | StatType | Line
├── requirements.txt                 # Python packages needed for deployment
```

---

## ✅ How to Use Locally

1. Clone the repo
2. Install packages:
```bash
pip install -r requirements.txt
```
3. Run the dashboard:
```bash
streamlit run nba_web_dashboard.py
```
4. Enable ✅ Simulation Mode if no games are live.

---

## 🔁 Updating Projections

1. Make changes in your Excel file:
   - `NBA BasketBall 24-25 SportsBook-Slim6801.xlsm`

2. Run the helper script:
```bash
python convert_projections.py
```

3. This will generate:
   - `points.csv`
   - `assists.csv`
   - `rebounds.csv`

4. Replace the files in your GitHub repo before redeploying.

---

## 🌐 Deploying to Streamlit Cloud

1. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud)
2. Sign in with GitHub
3. Click **“New App”**
4. Connect to this repo and select `nba_web_dashboard.py`
5. Click **Deploy**

You’ll get a live URL like:
```
https://yourusername.streamlit.app/nba-live-dashboard
```

---

## 📬 Questions or Help
Open an issue or reach out — happy to help improve or customize your dashboard!
