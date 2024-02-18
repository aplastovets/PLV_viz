import streamlit as st
import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import scipy as sp
import urllib

from matplotlib import ticker
from matplotlib import colors
from PIL import Image
from scipy import stats

logo_loc = 'https://github.com/Blandalytics/PLV_viz/blob/main/data/PL-text-wht.png?raw=true'
logo = Image.open(urllib.request.urlopen(logo_loc))
st.image(logo, width=200)

## Set Styling
# Plot Style
pl_white = '#FEFEFE'
pl_background = '#162B50'
pl_text = '#72a3f7'
pl_line_color = '#293a6b'

sns.set_theme(
    style={
        'axes.edgecolor': pl_white,
        'axes.facecolor': pl_background,
        'axes.labelcolor': pl_white,
        'xtick.color': pl_white,
        'ytick.color': pl_white,
        'figure.facecolor':pl_background,
        'grid.color': pl_background,
        'grid.linestyle': '-',
        'legend.facecolor':pl_background,
        'text.color': pl_white
     }
    )

line_color = sns.color_palette('vlag', n_colors=100)[0]

st.title("Scott Chu's Personal PLV Htter Test App")
st.write('Metrics are shown on the + scale (100 is league average, and 15 points is 1 StDev')

seasonal_constants = pd.read_csv('https://github.com/Blandalytics/PLV_viz/blob/main/data/plv_seasonal_constants.csv?raw=true').set_index('year')

## Selectors
# Year
year = st.radio('Choose a year:', [2023,2022,2021,2020])

def z_score_scaler(series):
    return (series - series.mean()) / series.std()

season_names = {
    'swing_agg':'Swing Agg (%)',
    'strike_zone_judgement':'SZ Judge',
    'decision_value':'Dec Value',
    'contact_over_expected':'Contact',
    'adj_power':'Power',
    'batter_wOBA':'HP'
}

# Load Data
@st.cache_data(ttl=2*3600,show_spinner=f"Loading {year} data")
def load_season_data(year):
    df = pd.DataFrame()
    for month in range(3,11):
        file_name = f'https://github.com/Blandalytics/PLV_viz/blob/main/data/{year}_PLV_App_Data-{month}.parquet?raw=true'
        df = pd.concat([df,
                        pd.read_parquet(file_name)[['hittername','p_hand','b_hand','pitch_id','balls','strikes','swing_agg',
                                                    'strike_zone_judgement','decision_value','contact_over_expected',
                                                    'adj_power','batter_wOBA','pitchtype','pitch_type_bucket',
                                                    'in_play_input','p_x','p_z','sz_z','strike_zone_top','strike_zone_bottom'
                                                   ]]
                       ])
    
    df = df.reset_index(drop=True)

    df.loc[df['p_x'].notna(),'kde_x'] = np.clip(df.loc[df['p_x'].notna(),'p_x'].astype('float').mul(12).round(0).astype('int').div(12),
                                                -20/12,
                                                20/12)
    df.loc[df['sz_z'].notna(),'kde_z'] = np.clip(df.loc[df['sz_z'].notna(),'sz_z'].astype('float').mul(24).round(0).astype('int').div(24),
                                                 -1.5,
                                                 1.25)
    
    df['base_decision_value'] = df['decision_value'].groupby([df['p_hand'],
                                                              df['b_hand'],
                                                              df['pitchtype'],
                                                              df['kde_x'],
                                                              df['kde_z'],
                                                              df['balls'],
                                                              df['strikes']]).transform('mean')
    df['base_power'] = df['adj_power'].groupby([df['p_hand'],
                                                df['b_hand'],
                                                df['pitchtype'],
                                                df['kde_x'],
                                                df['kde_z'],
                                                df['balls'],
                                                df['strikes']]).transform('mean')

    df['sa_oa'] = df['swing_agg'].copy()
    df['dv_oa'] = df['decision_value'].sub(df['base_decision_value'])
    df['ca_oa'] = df['contact_over_expected'].copy()
    df['pow_oa'] = df['adj_power'].sub(df['base_power'])

    
    df.loc[df['sz_z'].notna(),'kde_z'] = np.clip(df.loc[df['sz_z'].notna(),'p_z'].astype('float').mul(12).round(0).astype('int').div(12),
                                                 0,
                                                 4.5)

    for stat in ['swing_agg','strike_zone_judgement','contact_over_expected','in_play_input']:
        df[stat] = df[stat].astype('float').mul(100)
    
    # Convert to runs added
    df['decision_value'] = df['decision_value'].div(seasonal_constants.loc[year]['run_constant']).mul(100)
    df['batter_wOBA'] = df['batter_wOBA'].div(seasonal_constants.loc[year]['run_constant']).mul(100)
    
    df['zone'] = 1
    df.loc[(df['p_x'].abs()>10/12) | 
            (df['sz_z'].abs()>0.5),'zone'] = 0

    df['decision_value_z'] = np.where(df['zone']==1,df['decision_value'],None)
    df['decision_value_o'] = np.where(df['zone']==0,df['decision_value'],None)
    
    df['count'] = df['balls'].astype('str')+'-'+df['strikes'].astype('str')
    
    df['game_date'] = df['pitch_id'].map(pd.read_parquet('https://github.com/Blandalytics/PLV_viz/blob/main/data/date_pitch_map.parquet?raw=true').set_index('pitch_id').to_dict()['game_played'])
    
    return df

plv_df = load_season_data(year)

max_pitches = plv_df.groupby('hittername')['pitch_id'].count().max()
start_val = int(plv_df.groupby('hittername')['pitch_id'].count().quantile(0.4)/50)*50

# Num Pitches threshold
pitch_thresh = st.number_input(f'Min # of Pitches faced:',
                               min_value=min(100,start_val), 
                               max_value=2000,
                               step=50, 
                               value=500)

season_df = (plv_df
             .rename(columns=season_names)
             .rename(columns={'hittername':'Name',
                              'pitch_id':'Pitches',
                              'decision_value_z':'zDV',
                              'decision_value_o':'oDV'})
             .astype({'Name':'str'})
             .groupby('Name')
             [['Pitches','zDV','oDV']+list(season_names.values())]
             .agg({
                 'Pitches':'count',
                 'Swing Agg (%)':'mean',
                 'SZ Judge':'mean',
                 'Dec Value':'mean',
                 'zDV':np.nanmean,
                 'oDV':np.nanmean,
                 'Contact':'mean',
                 'Power':'mean',
                 'HP':'mean'
             })
             .query(f'Pitches >= {pitch_thresh}')
             .sort_values('HP', ascending=False)
            )

for stat in ['SZ Judge','Contact','Dec Value','zDV','oDV','Power','HP']:
    season_df[stat] = round(z_score_scaler(season_df[stat])*15+100,0)
    season_df[stat] = season_df[stat].astype('int').fillna(100)

st.write(f'Metrics on the "Plus" scale. Table is sortable.')

st.dataframe(season_df[['Pitches','Swing Agg (%)','SZ Judge','Dec Value','zDV','oDV','Contact','Power','HP']]
             .style
             .format(precision=1, thousands=',')
             .background_gradient(axis=None, vmin=70, vmax=130, cmap="vlag",
                                  subset=['SZ Judge','Dec Value','zDV','oDV',
                                          'Contact','Power','HP']
                                 ) 
            )

### Rolling Charts
stat_names = {
    'swing_agg':'Swing Aggression',
    'strike_zone_judgement':'Strikezone Judgement',
    'decision_value':'Decision Value',
    'in_play_input':'Pitch Hittability',
    'contact_over_expected':'Contact Ability',
    'adj_power':'Power',
    'batter_wOBA':'Hitter Performance'
}

stat_values = {
    'swing_agg':'Swing Frequency, Above Expected',
    'strike_zone_judgement':'SZ Judgment+',
    'decision_value':'Decision Value+',
    'in_play_input':'Batted Ball Likelihood of Pitches',
    'contact_over_expected':'Contact+',
    'adj_power':'Power+',
    'batter_wOBA':'Performance+'
}

plv_df = plv_df.rename(columns=stat_names)
st.title("Rolling Ability Charts")

# Player
players = list(plv_df.groupby('hittername', as_index=False)[['pitch_id','Hitter Performance']].agg({
    'pitch_id':'count',
    'Hitter Performance':'mean'}).query(f'pitch_id >={pitch_thresh}').sort_values('Hitter Performance', ascending=False)['hittername'])
default_player = players.index('Juan Soto')
player = st.selectbox('Choose a hitter:', players, index=default_player)

col1, col2 = st.columns([0.5,0.5])

with col1:
    # Metric Selection
    metrics = list(stat_names.values())
    default_stat = metrics.index('Decision Value')
    metric = st.selectbox('Choose a metric:', metrics, index=default_stat)

with col2:
    # Pitchtype Selection
    pitchtype_help = '''
    **Fastballs**: 4-Seam, Sinkers, some Cutters\n
    **Breaking Balls**: Sliders, Sweepers, Curveballs, most Cutters\n
    **Offspeed**: Changeups, Splitters
    '''
    pitchtype_base = st.selectbox('Vs Pitchtype', 
                                  ['All','Fastballs', 'Breaking Balls', 'Offspeed'],
                                  index=0,
                                  help=pitchtype_help
                                    )
    if pitchtype_base == 'All':
        pitchtype_select = ['Fastball', 'Breaking Ball', 'Offspeed', 'Other']
    else:
        pitchtype_select = [pitchtype_base] if pitchtype_base=='Offspeed' else [pitchtype_base[:-1]] # remove the 's'

rolling_denom = {
    'Swing Aggression':'Pitches',
    'Strikezone Judgement':'Pitches',
    'Decision Value':'Pitches',
    'Pitch Hittability':'Pitches',
    'Contact Ability':'Swings',
    'Power': 'BBE',
    'Hitter Performance':'Pitches'
}

rolling_threshold = {
    'Swing Aggression':400,
    'Strikezone Judgement':400,
    'Decision Value':400,
    'Pitch Hittability':400,
    'Contact Ability':200,
    'Power': 75,
    'Hitter Performance':800
}

count_select = st.radio('Count Group', 
                        ['All','Hitter-Friendly','Pitcher-Friendly','Even','2-Strike','3-Ball','Custom'],
                        index=0,
                        horizontal=True
                       )
 
if count_select=='All':
    selected_options = ['0-0', '1-0', '2-0', '3-0', '0-1', '1-1', '2-1', '3-1', '0-2', '1-2', '2-2', '3-2']
elif count_select=='Hitter-Friendly':
    selected_options = ['1-0', '2-0', '3-0', '2-1', '3-1']
elif count_select=='Pitcher-Friendly':
    selected_options = ['0-1','0-2','1-2']
elif count_select=='Even':
    selected_options = ['0-0','1-1','2-2']
elif count_select=='2-Strike':
    selected_options = ['0-2','1-2','2-2','3-2']
elif count_select=='3-Ball':
    selected_options = ['3-0','3-1','3-2']
else:
    selected_options = st.multiselect('Select the count(s):',
                                       ['0-0', '1-0', '2-0', '3-0', '0-1', '1-1', '2-1', '3-1', '0-2', '1-2', '2-2', '3-2'],
                                       ['0-0', '1-0', '2-0', '3-0', '0-1', '1-1', '2-1', '3-1', '0-2', '1-2', '2-2', '3-2'])
    
updated_threshold = int(round(rolling_threshold[metric]*len(selected_options)/12/5)*5 / (3 if year == 2023 else 1))

# Hitter Handedness
handedness = st.select_slider(
    'Pitcher Handedness',
    options=['Left', 'All', 'Right'],
    value='All')
# Pitcher Handedness
if handedness=='All':
    hitter_hand = ['L','R']
else:
    hitter_hand = list(plv_df.loc[(plv_df['hittername']==player),'b_hand'].unique())

hand_map = {
    'Left':['L'],
    'All':['L','R'],
    'Right':['R']
}

big_three = ['Decision Value','Contact Ability','Power']
if metric not in big_three:
    stat_list = big_three+[metric]
else:
    stat_list = big_three
agg_dict = {x:'mean' for x in stat_list}
agg_dict.update({'pitch_id':'count'})
chart_thresh_list = (plv_df
                     .loc[plv_df['count'].astype('str').isin(selected_options) &
                          plv_df['pitch_type_bucket'].isin(pitchtype_select) &
                          plv_df['b_hand'].isin(hitter_hand) &
                          plv_df['p_hand'].isin(hand_map[handedness])
                         ]
                     .groupby('hittername')
                     [['pitch_id']+stat_list]
                     .agg(agg_dict)
                     .query(f'pitch_id >= {updated_threshold}')
                     .copy()
                    )

chart_mean = plv_df[metric].mean()
stat_vals = {}
for stat in stat_list:
    stat_vals.update({stat:[chart_thresh_list[stat].mean(),
                            chart_thresh_list[stat].std(),
                            (rolling_df[metric].mean()-chart_thresh_list[stat].mean())/chart_thresh_list[stat].std()*15+100,
                            (chart_thresh_list[metric].quantile(0.1)-chart_thresh_list[stat].mean())/chart_thresh_list[stat].std()*15+100,
                            (chart_thresh_list[metric].quantile(0.9)-chart_thresh_list[stat].mean())/chart_thresh_list[stat].std()*15+100]})

plv_df[metric] = plv_df[metric].replace([np.inf, -np.inf], np.nan)

rolling_df = (plv_df
              .sort_values('pitch_id')
              .loc[(plv_df['hittername']==player) &
                   plv_df['p_hand'].isin(hand_map[handedness]) &
                   plv_df['count'].isin(selected_options) &
                   plv_df['pitch_type_bucket'].isin(pitchtype_select),
                   ['hittername','game_date']+stat_list]
              .dropna()
              .reset_index(drop=True)
              .reset_index()
              .rename(columns={'index':'pitches_faced'})
             )

season_sample = rolling_df.shape[0]

window_max = max(rolling_threshold[metric],int(round(rolling_df.shape[0]/10)*7))

# Rolling Window
window = st.number_input(f'Choose a {rolling_denom[metric]} threshold:', 
                         min_value=25, 
                         max_value=window_max,
                         step=5, 
                         value=rolling_threshold[metric])

rolling_df['Rolling_Stat'] = rolling_df[metric].rolling(window).mean()
fixed_window = window if (rolling_df[metric].mean() < rolling_df['Rolling_Stat'].max()) and (rolling_df[metric].mean() > rolling_df['Rolling_Stat'].min()) else int(window*2/3)
rolling_df['Rolling_Stat'] = rolling_df[metric].rolling(window, min_periods=fixed_window).mean()
rolling_df['Rolling_Stat+'] = rolling_df['Rolling_Stat'].sub(chart_avg).div(chart_stdev).mul(15).add(100)

for stat in big_three:
    rolling_df['Rolling_'+stat] = rolling_df[stat].rolling(rolling_threshold[stat]).mean()
    rolling_df[f'Rolling_{stat}+'] = rolling_df['Rolling_'+stat].sub(chart_avg).div(chart_stdev).mul(15).add(100)

if metric in ['Strikezone Judgement','Decision Value','Contact Ability','Power','Hitter Performance']:
    season_avg = (rolling_df[metric].mean()-stat_vals[metric][0])/stat_vals[metric][1]*15+100
    chart_90 = (chart_thresh_list[metric].quantile(0.9)-stat_vals[metric][0])/stat_vals[metric][1]*15+100
    chart_75 = (chart_thresh_list[metric].quantile(0.75)-stat_vals[metric][0])/stat_vals[metric][1]*15+100
    chart_25 = (chart_thresh_list[metric].quantile(0.25)-stat_vals[metric][0])/stat_vals[metric][1]*15+100
    chart_10 = (chart_thresh_list[metric].quantile(0.1)-stat_vals[metric][0])/stat_vals[metric][1]*15+100
else: 
    season_avg = rolling_df[metric].mean()
    chart_90 = chart_thresh_list[metric].quantile(0.9)
    chart_75 = chart_thresh_list[metric].quantile(0.75)
    chart_25 = chart_thresh_list[metric].quantile(0.25)
    chart_10 = chart_thresh_list[metric].quantile(0.1)

rolling_df = rolling_df.loc[rolling_df['pitches_faced']==rolling_df['pitches_faced'].groupby(rolling_df['game_date']).transform('max')].copy()

color_norm = colors.TwoSlopeNorm(vmin=chart_10, 
                                 vcenter=chart_mean if (metric in ['Swing Aggression','Pitch Hittability']) else 100,
                                 vmax=chart_90)

def rolling_chart():    
    fig, ax = plt.subplots(figsize=(6,6))
    sns.lineplot(data=rolling_df,
                 x='game_date',
                 y='Rolling_Stat' if (metric in ['Swing Aggression','Pitch Hittability']) else 'Rolling_Stat+',
                 color='w'
                   )
    
    line_text_loc = rolling_df['game_date'].min() + pd.Timedelta(days=(rolling_df['game_date'].max() - rolling_df['game_date'].min()).days * 1.05)
    
    ax.axhline(season_avg, 
               color='w',
               linestyle='--')
    ax.text(line_text_loc,
            season_avg,
            'Szn Avg',
            va='center',
            color='w')

    # Threshold Lines
    ax.axhline(chart_90,
               color=sns.color_palette('vlag', n_colors=100)[99],
               alpha=0.6)
    ax.axhline(chart_75,
               color=sns.color_palette('vlag', n_colors=100)[79],
               linestyle='--',
               alpha=0.5)
    ax.axhline(chart_mean if (metric in ['Swing Aggression','Pitch Hittability']) else 100,
               color='w',
               alpha=0.5)
    ax.axhline(chart_25,
               color=sns.color_palette('vlag', n_colors=100)[19],
               linestyle='--',
               alpha=0.5)
    ax.axhline(chart_10,
               color=sns.color_palette('vlag', n_colors=100)[0],
               alpha=0.6)
    
    ax.text(line_text_loc,
            chart_90,
            '90th %' if abs(chart_90 - season_avg) > (ax.get_ylim()[1] - ax.get_ylim()[0])/25 else '',
            va='center',
            color=sns.color_palette('vlag', n_colors=100)[99],
            alpha=1)
    ax.text(line_text_loc,
            chart_75,
            '75th %' if abs(chart_75 - season_avg) > (ax.get_ylim()[1] - ax.get_ylim()[0])/25 else '',
            va='center',
            color=sns.color_palette('vlag', n_colors=100)[74],
            alpha=1)
    ax.text(line_text_loc,
            chart_mean if (metric in ['Swing Aggression','Pitch Hittability']) else 100,
            'MLB Avg' if abs(100 - season_avg) > (ax.get_ylim()[1] - ax.get_ylim()[0])/25 else '',
            va='center',
            color='w',
            alpha=0.75)
    ax.text(line_text_loc,
            chart_25,
            '25th %' if abs(chart_25 - season_avg) > (ax.get_ylim()[1] - ax.get_ylim()[0])/25 else '',
            va='center',
            color=sns.color_palette('vlag', n_colors=100)[24],
            alpha=1)
    ax.text(line_text_loc,
            chart_10,
            '10th %' if abs(chart_10 - season_avg) > (ax.get_ylim()[1] - ax.get_ylim()[0])/25 else '',
            va='center',
            color=sns.color_palette('vlag', n_colors=100)[9],
            alpha=1)
    
    y_pad = (chart_90-chart_10)/10
    
    chart_min = min(chart_10,
                    rolling_df['Rolling_Stat'].min() if (metric in ['Swing Aggression','Pitch Hittability']) else rolling_df['Rolling_Stat+'].min()
                   ) - y_pad
    
    chart_max = max(chart_90,
                    rolling_df['Rolling_Stat'].max() if (metric in ['Swing Aggression','Pitch Hittability']) else rolling_df['Rolling_Stat+'].max()
                   ) + y_pad
    
    plus_text = ''  if (metric in ['Swing Aggression','Pitch Hittability']) else '+'

    if metric == 'Swing Aggression':
        ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(100,decimals=0))

    if metric == 'Pitch Hittability':
        ax.yaxis.set_major_formatter(mpl.ticker.PercentFormatter(100,decimals=1))
        
    locator = mdates.AutoDateLocator(minticks=4, maxticks=7)
    formatter = mdates.ConciseDateFormatter(locator,
                                            show_offset=False,
                                            formats=['%Y', '%-m/1', '%-m/%d', '%H:%M', '%H:%M', '%S.%f'])
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    
    ax.set_xlabel('Game Date', labelpad=8)
    ax.set(ylabel=stat_values[list(stat_names.keys())[list(stat_names.values()).index(metric)]],
           ylim=(chart_min, 
                 chart_max)           
          )

    pitch_text = f'; vs {pitchtype_select[0]}' if pitchtype_base == 'Offspeed' else f'; vs {pitchtype_select[0]}s'
    
    fig.suptitle("{}'s {} {}\n{}".format(player,
                                         year,
                                         metric,
                                         '(Rolling {} {}{}{}{})'.format(window,
                                                                        rolling_denom[metric],
                                                                        '' if pitchtype_base == 'All' else pitch_text,
                                                                        '' if count_select=='All' else f'; in {selected_options} counts' if count_select=='Custom' else f'; in {count_select} Counts',
                                                                        '' if (handedness=='All') else f'; {hitter_hand[0]}HH vs {hand_map[handedness][0]}HP'
                                                                        )
                                         ),
                 fontsize=14
                )
    
    # Add PL logo
    pl_ax = fig.add_axes([0.8,-0.01,0.2,0.2], anchor='SE', zorder=1)
    pl_ax.imshow(logo)
    pl_ax.axis('off')
    
    sns.despine()
    st.pyplot(fig)
if window > season_sample:
    st.write(f'Not enough {rolling_denom[metric]} ({rolling_df.shape[0]})')
else:
    rolling_chart()

def big_three_chart():    
    fig, ax = plt.subplots(figsize=(6,6))
    sns.lineplot(data=rolling_df,
                 x='game_date',
                 y='Rolling_Decision Value+',
                 color=sns.color_palette('vlag',n_colors=1000)[0],
                 ax=ax
                 )
    sns.lineplot(data=rolling_df,
                 x='game_date',
                 y='Rolling_Contact Ability+',
                 color='w',
                 ax=ax
                 )
    sns.lineplot(data=rolling_df,
                 x='game_date',
                 y='Rolling_Power+',
                 color=sns.color_palette('vlag',n_colors=1000)[-1],
                 ax=ax
                 )
    
    line_text_loc = rolling_df['game_date'].min() + pd.Timedelta(days=(rolling_df['game_date'].max() - rolling_df['game_date'].min()).days * 1.05)
    
    ax.axhline(stat_vals['Decision Value'][2], 
               color=sns.color_palette('vlag',n_colors=1000)[0],
               linestyle='--')
    ax.text(line_text_loc,
            stat_vals['Decision Value'][2],
            'DecVal',
            va='center',
            color=sns.color_palette('vlag',n_colors=1000)[0])
    
    ax.axhline(stat_vals['Contact Ability'][2], 
               color='w',
               linestyle='--')
    ax.text(line_text_loc,
            stat_vals['Contact Ability'][2],
            'Contact',
            va='center',
            color='w')
    
    ax.axhline(stat_vals['Power'][2], 
               color=sns.color_palette('vlag',n_colors=1000)[-1],
               linestyle='--')
    ax.text(line_text_loc,
            stat_vals['Power'][2],
            'Power',
            va='center',
            color=sns.color_palette('vlag',n_colors=1000)[-1])

    offset_check = 0
    chart_lims = [75,125]
    for stat in big_three:
        chart_lims[0] = min([chart_lims[0],stat_vals[stat][3]])
        chart_lims[1] = max([chart_lims[1],stat_vals[stat][4]])
        if abs(100 - stat_vals[stat][2]) > (ax.get_ylim()[1] - ax.get_ylim()[0])/25:
            offset_check = 1
    
    ax.axhline(100,
               color='w',
               alpha=0.5)
    ax.text(line_text_loc,
            100,
            'MLB Avg' if offset_check==0 else '',
            va='center',
            color='w',
            alpha=0.75)
    
    y_pad = (chart_lims[1]-chart_lims[0])/10
    
    chart_min = chart_lims[0] - y_pad
    chart_max = chart_lims[1] + y_pad
    
    plus_text = '+'

    locator = mdates.AutoDateLocator(minticks=4, maxticks=7)
    formatter = mdates.ConciseDateFormatter(locator,
                                            show_offset=False,
                                            formats=['%Y', '%-m/1', '%-m/%d', '%H:%M', '%H:%M', '%S.%f'])
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    
    ax.set_xlabel('Game Date', labelpad=8)
    ax.set(ylabel='',
           ylim=(chart_min, 
                 chart_max)           
          )

    pitch_text = f'vs {pitchtype_select[0]}' if pitchtype_base == 'Offspeed' else f'vs {pitchtype_select[0]}s'
    
    fig.suptitle(f"{player}'s {year} Rolling PLV Metrics\n{}".format('{}{}{}'.format(
        'vs All Pitches' if pitchtype_base == 'All' else pitch_text,
        '; in All Counts' if count_select=='All' else f'; in {selected_options} Counts' if count_select=='Custom' else f'; in {count_select} Counts',
        'vs All Pitchers' if (handedness=='All') else f'; {hitter_hand[0]}HH vs {hand_map[handedness][0]}HP'
        )
                                                                     ),
                 fontsize=14
                 )
    
    # Add PL logo
    pl_ax = fig.add_axes([0.8,-0.01,0.2,0.2], anchor='SE', zorder=1)
    pl_ax.imshow(logo)
    pl_ax.axis('off')
    
    sns.despine()
    st.pyplot(fig)
big_three_chart()

st.write("If you have questions or ideas on what you'd like to see, DM me! [@Blandalytics](https://twitter.com/blandalytics)")
st.write("Heatmaps can now be found at [plv-hitter-heatmaps.streamlit.app](https://plv-hitter-heatmaps.streamlit.app/)")
