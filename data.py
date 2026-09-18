import pandas as pd
import nfl_data_py as nfl
import sqlite3
 
YEARS = [2025, 2026]
 
pbp = nfl.import_pbp_data(YEARS)
pbp = pbp.copy()
 
pbp['is_redzone'] = pbp['yardline_100'] <= 20
pbp['is_goalline'] = pbp['yardline_100'] <= 5
 
rush_tds = pbp[pbp['rush_touchdown'] == 1]
rz_rushes = pbp[(pbp['rush_attempt'] == 1) & (pbp['is_redzone'])]
gl_rushes = pbp[(pbp['rush_attempt'] == 1) & (pbp['is_goalline'])]
 
group_cols_rush = ['rusher_player_id', 'rusher_player_name', 'defteam']
rush_td_vs_team = rush_tds.groupby(group_cols_rush)['rush_touchdown'].sum()
rz_rush_vs_team = rz_rushes.groupby(group_cols_rush)['rush_attempt'].sum()
gl_rush_vs_team = gl_rushes.groupby(group_cols_rush)['rush_attempt'].sum()
 
rush_summary = pd.DataFrame({
    'rush_td': rush_td_vs_team,
    'rz_rush_att': rz_rush_vs_team,
    'goalline_rush_att': gl_rush_vs_team,
}).fillna(0).reset_index()
rush_summary = rush_summary.rename(columns={'rusher_player_id': 'player_id', 'rusher_player_name': 'player_name'})
rush_summary['rz_conversion_rate'] = (
    rush_summary['rush_td'] / rush_summary['rz_rush_att']
).replace([float('inf')], 0).fillna(0)
 
rush_td_overall = rush_tds.groupby(['rusher_player_id', 'rusher_player_name'])['rush_touchdown'].sum()
rz_rush_overall = rz_rushes.groupby(['rusher_player_id', 'rusher_player_name'])['rush_attempt'].sum()
 
rush_summary_overall = pd.DataFrame({
    'rush_td': rush_td_overall,
    'rz_rush_att': rz_rush_overall,
}).fillna(0).reset_index()
rush_summary_overall = rush_summary_overall.rename(columns={'rusher_player_id': 'player_id', 'rusher_player_name': 'player_name'})
rush_summary_overall['rz_conversion_rate'] = (
    rush_summary_overall['rush_td'] / rush_summary_overall['rz_rush_att']
).replace([float('inf')], 0).fillna(0)
 
rec_tds = pbp[(pbp['pass_touchdown'] == 1) & (pbp['complete_pass'] == 1)]
rz_targets = pbp[(pbp['pass_attempt'] == 1) & (pbp['is_redzone'])]
gl_targets = pbp[(pbp['pass_attempt'] == 1) & (pbp['is_goalline'])]
 
group_cols_rec = ['receiver_player_id', 'receiver_player_name', 'defteam']
rec_td_vs_team = rec_tds.groupby(group_cols_rec)['pass_touchdown'].sum()
rz_targets_vs_team = rz_targets.groupby(group_cols_rec)['pass_attempt'].sum()
gl_targets_vs_team = gl_targets.groupby(group_cols_rec)['pass_attempt'].sum()
 
rec_summary = pd.DataFrame({
    'rec_td': rec_td_vs_team,
    'rz_targets': rz_targets_vs_team,
    'goalline_targets': gl_targets_vs_team,
}).fillna(0).reset_index()
rec_summary = rec_summary.rename(columns={'receiver_player_id': 'player_id', 'receiver_player_name': 'player_name'})
rec_summary['rz_conversion_rate'] = (
    rec_summary['rec_td'] / rec_summary['rz_targets']
).replace([float('inf')], 0).fillna(0)
 
rec_td_overall = rec_tds.groupby(['receiver_player_id', 'receiver_player_name'])['pass_touchdown'].sum()
rz_targets_overall = rz_targets.groupby(['receiver_player_id', 'receiver_player_name'])['pass_attempt'].sum()
 
rec_summary_overall = pd.DataFrame({
    'rec_td': rec_td_overall,
    'rz_targets': rz_targets_overall,
}).fillna(0).reset_index()
rec_summary_overall = rec_summary_overall.rename(columns={'receiver_player_id': 'player_id', 'receiver_player_name': 'player_name'})
rec_summary_overall['rz_conversion_rate'] = (
    rec_summary_overall['rec_td'] / rec_summary_overall['rz_targets']
).replace([float('inf')], 0).fillna(0)
 
pass_tds = pbp[pbp['pass_touchdown'] == 1]
rz_pass_attempts = pbp[(pbp['pass_attempt'] == 1) & (pbp['is_redzone'])]
 
group_cols_pass = ['passer_player_id', 'passer_player_name', 'defteam']
pass_td_vs_team = pass_tds.groupby(group_cols_pass)['pass_touchdown'].sum()
rz_pass_vs_team = rz_pass_attempts.groupby(group_cols_pass)['pass_attempt'].sum()
 
pass_summary = pd.DataFrame({
    'pass_td': pass_td_vs_team,
    'rz_pass_att': rz_pass_vs_team,
}).fillna(0).reset_index()
pass_summary = pass_summary.rename(columns={'passer_player_id': 'player_id', 'passer_player_name': 'player_name'})
 
rush_app = pbp[pbp['rusher_player_id'].notna()][['rusher_player_id', 'rusher_player_name', 'posteam', 'game_date']]
rush_app = rush_app.rename(columns={'rusher_player_id': 'player_id', 'rusher_player_name': 'player_name'})
 
rec_app = pbp[pbp['receiver_player_id'].notna()][['receiver_player_id', 'receiver_player_name', 'posteam', 'game_date']]
rec_app = rec_app.rename(columns={'receiver_player_id': 'player_id', 'receiver_player_name': 'player_name'})
 
pass_app = pbp[pbp['passer_player_id'].notna()][['passer_player_id', 'passer_player_name', 'posteam', 'game_date']]
pass_app = pass_app.rename(columns={'passer_player_id': 'player_id', 'passer_player_name': 'player_name'})
 
all_app = pd.concat([rush_app, rec_app, pass_app]).dropna(subset=['player_id', 'posteam'])
all_app['game_date'] = pd.to_datetime(all_app['game_date'])
 
player_current_team = (
    all_app.sort_values('game_date')
    .groupby('player_id')
    .tail(1)[['player_id', 'player_name', 'posteam']]
    .rename(columns={'posteam': 'current_team'})
    .reset_index(drop=True)
)
 
try:
    rosters = nfl.import_weekly_rosters(YEARS)
 
    id_candidates = ['gsis_id', 'player_id', 'pfr_id']
    id_col = next((c for c in id_candidates if c in rosters.columns), None)
 
    if id_col is None:
        raise KeyError(f"No known player ID column found. Available columns: {rosters.columns.tolist()}")
 
    status_col = 'status' if 'status' in rosters.columns else None
    name_col = 'full_name' if 'full_name' in rosters.columns else None
    keep_cols = [id_col, 'position', 'season', 'week'] + ([status_col] if status_col else []) + ([name_col] if name_col else [])
    rosters = rosters[keep_cols].dropna(subset=[id_col])
 
    latest_roster = (
        rosters.sort_values(['season', 'week'])
        .groupby(id_col)
        .tail(1)
        .rename(columns={id_col: 'player_id'})
    )
 
    if status_col:
        latest_roster = latest_roster.rename(columns={status_col: 'roster_status'})
    else:
        latest_roster['roster_status'] = 'UNKNOWN'
 
    if name_col:
        latest_roster = latest_roster.rename(columns={name_col: 'full_name'})
    else:
        latest_roster['full_name'] = None
 
    player_current_team = player_current_team.merge(
        latest_roster[['player_id', 'position', 'roster_status', 'full_name']], on='player_id', how='left'
    )
except Exception as e:
    print(f"Roster pull failed ({e}) — positions will show as N/A")
    player_current_team['position'] = None
    player_current_team['roster_status'] = 'UNKNOWN'
    player_current_team['full_name'] = None
    latest_roster = pd.DataFrame(columns=['player_id', 'position', 'roster_status', 'full_name'])
 
player_current_team['position'] = player_current_team['position'].fillna('N/A')
player_current_team['roster_status'] = player_current_team['roster_status'].fillna('UNKNOWN')
player_current_team['full_name'] = player_current_team['full_name'].fillna(player_current_team['player_name'])
matched = (player_current_team['position'] != 'N/A').sum()
print(f"Position lookup matched {matched} of {len(player_current_team)} players")
 
try:
    injuries_raw = nfl.import_injuries(YEARS)
    injuries_raw = injuries_raw.dropna(subset=['gsis_id'])
 
    latest_season = injuries_raw['season'].max()
    latest_week = injuries_raw[injuries_raw['season'] == latest_season]['week'].max()
 
    current_out = injuries_raw[
        (injuries_raw['season'] == latest_season) &
        (injuries_raw['week'] == latest_week) &
        (injuries_raw['report_status'] == 'Out')
    ]
 
    cols_wanted = [
        'gsis_id', 'full_name', 'team', 'position', 'week', 'season',
        'report_status', 'report_primary_injury', 'date_modified'
    ]
    available_cols = [c for c in cols_wanted if c in current_out.columns]
    injuries = current_out[available_cols].rename(columns={'gsis_id': 'player_id'})
 
    if 'date_modified' not in injuries.columns:
        injuries['date_modified'] = None
 
    active_roster_ids = latest_roster[latest_roster['roster_status'] != 'RET']['player_id'].unique()
    injuries = injuries[injuries['player_id'].isin(active_roster_ids)]
 
    def classify_reason(text):
        if not isinstance(text, str) or text.strip() == '':
            return 'Injured'
        lowered = text.lower()
        non_injury_markers = ['not injury related', 'personal', 'suspen', 'illness']
        if any(marker in lowered for marker in non_injury_markers):
            return 'Other'
        return 'Injured'
 
    injuries['reason_category'] = injuries['report_primary_injury'].apply(classify_reason)
    injuries = injuries.sort_values('team')
except Exception as e:
    print(f"Injury pull failed ({e}) — injuries tab will be empty")
    injuries = pd.DataFrame(columns=[
        'player_id', 'full_name', 'team', 'position', 'week', 'season',
        'report_status', 'report_primary_injury', 'date_modified', 'reason_category'
    ])
 
schedule = nfl.import_schedules(YEARS)
schedule = schedule[[
    'game_id', 'season', 'week', 'game_type', 'gameday', 'weekday',
    'gametime', 'away_team', 'home_team', 'away_score', 'home_score'
]].copy()
 
connection = sqlite3.connect('nfl_data.db')
 
rush_summary.to_sql('rush_summary', connection, if_exists='replace', index=False)
rec_summary.to_sql('rec_summary', connection, if_exists='replace', index=False)
pass_summary.to_sql('pass_summary', connection, if_exists='replace', index=False)
rush_summary_overall.to_sql('rush_summary_overall', connection, if_exists='replace', index=False)
rec_summary_overall.to_sql('rec_summary_overall', connection, if_exists='replace', index=False)
player_current_team.to_sql('player_current_team', connection, if_exists='replace', index=False)
injuries.to_sql('injuries', connection, if_exists='replace', index=False)
schedule.to_sql('schedule', connection, if_exists='replace', index=False)
 
connection.close()
 
print(f"Done. Pulled seasons: {YEARS}")
print(f"Players tracked: {len(player_current_team)}")
print(f"Injury records: {len(injuries)}")
print(f"Games in schedule: {len(schedule)}")
 
