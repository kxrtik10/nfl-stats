import pandas as pd
import nfl_data_py as nfl
 
# PULL DATA
pbp = nfl.import_pbp_data([2026])
pbp = pbp.copy() 
 
# FLAG RED ZONE / GOAL LINE PLAYS
pbp['is_redzone'] = pbp['yardline_100'] <= 20
pbp['is_goalline'] = pbp['yardline_100'] <= 5
 
# RUSHING — TDs and Red Zone Opportunity
rush_tds = pbp[pbp['rush_touchdown'] == 1]
rz_rushes = pbp[(pbp['rush_attempt'] == 1) & (pbp['is_redzone'])]
gl_rushes = pbp[(pbp['rush_attempt'] == 1) & (pbp['is_goalline'])]
 
rush_td_vs_team = rush_tds.groupby(['rusher_player_name', 'defteam'])['rush_touchdown'].sum()
rz_rush_vs_team = rz_rushes.groupby(['rusher_player_name', 'defteam'])['rush_attempt'].sum()
gl_rush_vs_team = gl_rushes.groupby(['rusher_player_name', 'defteam'])['rush_attempt'].sum()
 
# RECEIVING — TDs and Red Zone Opportunity
rec_tds = pbp[(pbp['pass_touchdown'] == 1) & (pbp['complete_pass'] == 1)]
rz_targets = pbp[(pbp['pass_attempt'] == 1) & (pbp['is_redzone'])]
gl_targets = pbp[(pbp['pass_attempt'] == 1) & (pbp['is_goalline'])]
 
rec_td_vs_team = rec_tds.groupby(['receiver_player_name', 'defteam'])['pass_touchdown'].sum()
rz_targets_vs_team = rz_targets.groupby(['receiver_player_name', 'defteam'])['pass_attempt'].sum()
gl_targets_vs_team = gl_targets.groupby(['receiver_player_name', 'defteam'])['pass_attempt'].sum()
 
# PASSING — TDs and Red Zone Attempts
pass_tds = pbp[pbp['pass_touchdown'] == 1]
rz_pass_attempts = pbp[(pbp['pass_attempt'] == 1) & (pbp['is_redzone'])]
 
pass_td_vs_team = pass_tds.groupby(['passer_player_name', 'defteam'])['pass_touchdown'].sum()
rz_pass_vs_team = rz_pass_attempts.groupby(['passer_player_name', 'defteam'])['pass_attempt'].sum()
 
# COMBINE RUSHING INTO ONE TABLE 
rush_summary = pd.DataFrame({
    'rush_td': rush_td_vs_team,
    'rz_rush_att': rz_rush_vs_team,
    'goalline_rush_att': gl_rush_vs_team,
}).fillna(0)
 
rush_summary['rz_conversion_rate'] = (
    rush_summary['rush_td'] / rush_summary['rz_rush_att']
).replace([float('inf')], 0).fillna(0)
 
# COMBINE RECEIVING INTO ONE TABLE
rec_summary = pd.DataFrame({
    'rec_td': rec_td_vs_team,
    'rz_targets': rz_targets_vs_team,
    'goalline_targets': gl_targets_vs_team,
}).fillna(0)
 
rec_summary['rz_conversion_rate'] = (
    rec_summary['rec_td'] / rec_summary['rz_targets']
).replace([float('inf')], 0).fillna(0)
 
# COMBINE PASSING INTO ONE TABLE
pass_summary = pd.DataFrame({
    'pass_td': pass_td_vs_team,
    'rz_pass_att': rz_pass_vs_team,
}).fillna(0)
 
print("=== RUSHING SUMMARY (sorted by red zone attempts) ===")
print(rush_summary.sort_values('rz_rush_att', ascending=False).head(15))
 
print("\n=== RECEIVING SUMMARY (sorted by red zone targets) ===")
print(rec_summary.sort_values('rz_targets', ascending=False).head(15))
 
print("\n=== PASSING SUMMARY (sorted by red zone attempts) ===")
print(pass_summary.sort_values('rz_pass_att', ascending=False).head(15))
 
# SAVE TO CSV 
rush_summary.to_csv('rush_summary_vs_team.csv')
rec_summary.to_csv('rec_summary_vs_team.csv')
pass_summary.to_csv('pass_summary_vs_team.csv')
 
print("\nSaved: rush_summary_vs_team.csv, rec_summary_vs_team.csv, pass_summary_vs_team.csv")

import sqlite3

connection = sqlite3.connect('nfl_data.db')
rush_summary.to_sql('rush_summary', connection, if_exists = 'replace')
rec_summary.to_sql('rec_summary', connection, if_exists = 'replace')
pass_summary.to_sql('pass_summary', connection, if_exists = 'replace')

connection.close()
 

