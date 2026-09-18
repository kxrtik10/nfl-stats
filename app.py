from flask import Flask, render_template, abort
import sqlite3
import pandas as pd
from datetime import date
import os
import time
import requests
from dotenv import load_dotenv
 
load_dotenv()
 
app = Flask(__name__)
DB_PATH = "nfl_data.db"
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
ODDS_BASE_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
ODDS_CACHE_SECONDS = 6 * 60 * 60
 
_odds_cache = {"timestamp": 0, "data": {}}
 
TEAM_COLORS = {
    "ARI": "#97233F", "ATL": "#A71930", "BAL": "#241773", "BUF": "#00338D",
    "CAR": "#0085CA", "CHI": "#0B162A", "CIN": "#FB4F14", "CLE": "#311D00",
    "DAL": "#041E42", "DEN": "#FB4F14", "DET": "#0076B6", "GB": "#203731",
    "HOU": "#03202F", "IND": "#002C5F", "JAX": "#101820", "KC": "#E31837",
    "LA": "#003594", "LAC": "#0080C6", "LV": "#000000", "MIA": "#008E97",
    "MIN": "#4F2683", "NE": "#002244", "NO": "#D3BC8D", "NYG": "#0B2265",
    "NYJ": "#125740", "PHI": "#004C54", "PIT": "#FFB612", "SEA": "#002244",
    "SF": "#AA0000", "TB": "#D50A0A", "TEN": "#4B92DB", "WAS": "#5A1414",
}
 
TEAM_NAMES = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}
 
 
def get_connection():
    return sqlite3.connect(DB_PATH)
 
 
def get_upcoming_games(limit=20):
    conn = get_connection()
    games = pd.read_sql(
        """
        SELECT * FROM schedule
        WHERE home_score IS NULL
        AND date(gameday) >= date('now')
        ORDER BY gameday ASC, gametime ASC
        LIMIT ?
        """,
        conn, params=(limit,)
    )
    conn.close()
    return games
 
 
def get_team_roster(team, conn):
    roster = pd.read_sql(
        "SELECT player_id, player_name, position FROM player_current_team WHERE current_team = ?",
        conn, params=(team,)
    )
    return roster.to_dict("records")
 
 
def get_player_projection(player_id, player_name, position, opponent, conn):
    rush_row = pd.read_sql(
        "SELECT * FROM rush_summary WHERE player_id = ? AND defteam = ?",
        conn, params=(player_id, opponent)
    )
    rec_row = pd.read_sql(
        "SELECT * FROM rec_summary WHERE player_id = ? AND defteam = ?",
        conn, params=(player_id, opponent)
    )
 
    rush_stats = rush_row.iloc[0].to_dict() if not rush_row.empty else None
    rec_stats = rec_row.iloc[0].to_dict() if not rec_row.empty else None
 
    rush_proj = (rush_stats["rz_rush_att"] * rush_stats["rz_conversion_rate"]) if rush_stats else 0
    rec_proj = (rec_stats["rz_targets"] * rec_stats["rz_conversion_rate"]) if rec_stats else 0
    total_proj = round(rush_proj + rec_proj, 2)
 
    return {
        "player": player_name,
        "position": position,
        "rush_td": int(rush_stats["rush_td"]) if rush_stats else 0,
        "rz_rush_att": int(rush_stats["rz_rush_att"]) if rush_stats else 0,
        "rec_td": int(rec_stats["rec_td"]) if rec_stats else 0,
        "rz_targets": int(rec_stats["rz_targets"]) if rec_stats else 0,
        "total_proj": total_proj,
    }
 
 
@app.route("/")
def dashboard():
    games = get_upcoming_games()
    games_list = games.to_dict("records")
    for g in games_list:
        g["home_color"] = TEAM_COLORS.get(g["home_team"], "#333")
        g["away_color"] = TEAM_COLORS.get(g["away_team"], "#333")
        g["home_name"] = TEAM_NAMES.get(g["home_team"], g["home_team"])
        g["away_name"] = TEAM_NAMES.get(g["away_team"], g["away_team"])
    return render_template("dashboard.html", games=games_list, today=date.today().isoformat())
 
 
@app.route("/game/<game_id>")
def game_detail(game_id):
    conn = get_connection()
    game_row = pd.read_sql("SELECT * FROM schedule WHERE game_id = ?", conn, params=(game_id,))
 
    if game_row.empty:
        conn.close()
        abort(404)
 
    game = game_row.iloc[0].to_dict()
    home_team = game["home_team"]
    away_team = game["away_team"]
 
    home_roster = get_team_roster(home_team, conn)
    away_roster = get_team_roster(away_team, conn)
 
    players = []
    for p in home_roster:
        players.append(get_player_projection(p["player_id"], p["player_name"], p["position"], away_team, conn))
    for p in away_roster:
        players.append(get_player_projection(p["player_id"], p["player_name"], p["position"], home_team, conn))
 
    conn.close()
    players.sort(key=lambda x: x["total_proj"], reverse=True)
 
    return render_template(
        "game.html",
        game=game,
        players=players,
        home_color=TEAM_COLORS.get(home_team, "#333"),
        away_color=TEAM_COLORS.get(away_team, "#333"),
    )
 
 
@app.route("/injuries")
def injuries_page():
    conn = get_connection()
    injuries = pd.read_sql(
        "SELECT * FROM injuries ORDER BY team ASC, full_name ASC", conn
    )
    conn.close()
    injuries_list = injuries.to_dict("records")
    for row in injuries_list:
        row["color"] = TEAM_COLORS.get(row["team"], "#333")
    return render_template("injuries.html", injuries=injuries_list)
 
 
def format_american_odds(price):
    price = int(round(price))
    return f"+{price}" if price > 0 else str(price)
 
 
def fetch_upcoming_event_ids():
    resp = requests.get(
        f"{ODDS_BASE_URL}/events",
        params={"apiKey": ODDS_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    events = resp.json()
    return [e["id"] for e in events]
 
 
def fetch_event_td_odds(event_id):
    resp = requests.get(
        f"{ODDS_BASE_URL}/events/{event_id}/odds",
        params={
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "player_anytime_td",
            "bookmakers": "fanduel",
            "oddsFormat": "american",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
 
    results = {}
    for bookmaker in data.get("bookmakers", []):
        if bookmaker.get("key") != "fanduel":
            continue
        for market in bookmaker.get("markets", []):
            if market.get("key") != "player_anytime_td":
                continue
            for outcome in market.get("outcomes", []):
                player_name = outcome.get("description") or outcome.get("name")
                price = outcome.get("price")
                if player_name and price is not None:
                    results[player_name.strip().lower()] = format_american_odds(price)
    return results
 
 
def refresh_odds_cache():
    if not ODDS_API_KEY:
        return
    try:
        event_ids = fetch_upcoming_event_ids()
        combined = {}
        for event_id in event_ids:
            try:
                combined.update(fetch_event_td_odds(event_id))
            except requests.exceptions.RequestException as e:
                print(f"Odds fetch failed for event {event_id}: {e}")
        _odds_cache["data"] = combined
        _odds_cache["timestamp"] = time.time()
        print(f"Odds cache refreshed: {len(combined)} players across {len(event_ids)} events")
    except requests.exceptions.RequestException as e:
        print(f"Odds event list fetch failed: {e}")
 
 
def get_fanduel_td_odds(full_name):
    if not ODDS_API_KEY:
        return None
    if time.time() - _odds_cache["timestamp"] > ODDS_CACHE_SECONDS:
        refresh_odds_cache()
    if not full_name:
        return None
    return _odds_cache["data"].get(full_name.strip().lower())
 
 
@app.route("/all-matchups")
def all_matchups():
    conn = get_connection()
 
    rush_overall = pd.read_sql("SELECT * FROM rush_summary_overall", conn)
    rec_overall = pd.read_sql("SELECT * FROM rec_summary_overall", conn)
    players_meta = pd.read_sql("SELECT * FROM player_current_team", conn)
    conn.close()
 
    rush_overall['rush_proj'] = rush_overall['rz_rush_att'] * rush_overall['rz_conversion_rate']
    rec_overall['rec_proj'] = rec_overall['rz_targets'] * rec_overall['rz_conversion_rate']
 
    merged = pd.merge(
        rush_overall[['player_id', 'player_name', 'rush_td', 'rz_rush_att', 'rush_proj']],
        rec_overall[['player_id', 'player_name', 'rec_td', 'rz_targets', 'rec_proj']],
        on='player_id', how='outer', suffixes=('_rush', '_rec')
    )
    merged['player_name'] = merged['player_name_rush'].combine_first(merged['player_name_rec'])
    merged = merged.fillna(0)
 
    merged = merged.merge(
        players_meta[['player_id', 'current_team', 'position', 'full_name', 'games_played']], on='player_id', how='left'
    )
    merged['current_team'] = merged['current_team'].fillna('FA')
    merged['position'] = merged['position'].fillna('N/A')
    merged['full_name'] = merged['full_name'].fillna(merged['player_name'])
    merged['games_played'] = merged['games_played'].fillna(1).clip(lower=1)
 
    merged['total_proj'] = round((merged['rush_proj'] + merged['rec_proj']) / merged['games_played'], 2)
 
    top10 = merged.sort_values('total_proj', ascending=False).head(10)
 
    rows = top10.to_dict("records")
    for r in rows:
        r["color"] = TEAM_COLORS.get(r["current_team"], "#333")
        r["odds"] = get_fanduel_td_odds(r["full_name"])
 
    return render_template("all_matchups.html", players=rows, odds_enabled=bool(ODDS_API_KEY))
 
 
if __name__ == "__main__":
    app.run(debug=True)
 
