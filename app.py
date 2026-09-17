from flask import Flask, render_template, abort
import sqlite3
import pandas as pd
from datetime import date
 
app = Flask(__name__)
DB_PATH = "nfl_data.db"
 
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
    """
    Blended projection: uses matchup-specific (vs this exact opponent) history
    when there's a real sample of red-zone opportunities against them.
    Falls back to (or blends toward) the player's overall red-zone profile
    across ALL opponents when matchup-specific data is thin or empty —
    this is what keeps a real workhorse from showing a flat 0 just because
    they haven't happened to face this particular team yet in our data window.
    """
    rush_matchup = pd.read_sql(
        "SELECT * FROM rush_summary WHERE player_id = ? AND defteam = ?",
        conn, params=(player_id, opponent)
    )
    rec_matchup = pd.read_sql(
        "SELECT * FROM rec_summary WHERE player_id = ? AND defteam = ?",
        conn, params=(player_id, opponent)
    )
    rush_overall = pd.read_sql(
        "SELECT * FROM rush_summary_overall WHERE player_id = ?",
        conn, params=(player_id,)
    )
    rec_overall = pd.read_sql(
        "SELECT * FROM rec_summary_overall WHERE player_id = ?",
        conn, params=(player_id,)
    )
 
    def blended_proj(matchup_df, overall_df, opp_col, td_col):
        """opp_col = 'rz_rush_att' or 'rz_targets'; td_col = 'rush_td' or 'rec_td'."""
        m_att = matchup_df.iloc[0][opp_col] if not matchup_df.empty else 0
        o_att = overall_df.iloc[0][opp_col] if not overall_df.empty else 0
        o_rate = overall_df.iloc[0]['rz_conversion_rate'] if not overall_df.empty else 0
 
        if m_att >= 3:
            # Enough matchup-specific sample — trust it directly
            m_rate = matchup_df.iloc[0]['rz_conversion_rate']
            return m_att * m_rate, m_att
        else:
            # Thin/no matchup data — use overall opportunity + overall rate instead,
            # scaled down slightly per game (overall is a season total, not one game)
            games_played_estimate = max(1, o_att / 4)  # rough: ~4 RZ touches/game is a lot; used only to scale
            per_game_att = o_att / games_played_estimate if games_played_estimate else 0
            return per_game_att * o_rate, o_att
 
    rush_proj, rush_opp_sample = blended_proj(rush_matchup, rush_overall, 'rz_rush_att', 'rush_td')
    rec_proj, rec_opp_sample = blended_proj(rec_matchup, rec_overall, 'rz_targets', 'rec_td')
 
    total_proj = round(rush_proj + rec_proj, 2)
 
    rush_td_total = int(rush_overall.iloc[0]['rush_td']) if not rush_overall.empty else 0
    rec_td_total = int(rec_overall.iloc[0]['rec_td']) if not rec_overall.empty else 0
 
    return {
        "player": player_name,
        "position": position,
        "rush_td": rush_td_total,
        "rec_td": rec_td_total,
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
        "SELECT * FROM injuries ORDER BY report_status ASC, team ASC", conn
    )
    conn.close()
    injuries_list = injuries.to_dict("records")
    for row in injuries_list:
        row["color"] = TEAM_COLORS.get(row["team"], "#333")
    return render_template("injuries.html", injuries=injuries_list)
 
 
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
        rush_overall[['player_id', 'player_name', 'rush_td', 'rush_proj']],
        rec_overall[['player_id', 'player_name', 'rec_td', 'rec_proj']],
        on='player_id', how='outer', suffixes=('_rush', '_rec')
    )
    merged['player_name'] = merged['player_name_rush'].combine_first(merged['player_name_rec'])
    merged = merged.fillna(0)
    merged['total_proj'] = round(merged['rush_proj'] + merged['rec_proj'], 2)
 
    merged = merged.merge(players_meta[['player_id', 'current_team', 'position']], on='player_id', how='left')
    merged['current_team'] = merged['current_team'].fillna('FA')
    merged['position'] = merged['position'].fillna('N/A')
 
    merged = merged.sort_values('total_proj', ascending=False).head(75)
 
    rows = merged.to_dict("records")
    for r in rows:
        r["color"] = TEAM_COLORS.get(r["current_team"], "#333")
 
    return render_template("all_matchups.html", players=rows)
 
 
if __name__ == "__main__":
    app.run(debug=True)
 
