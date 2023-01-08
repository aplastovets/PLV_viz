import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from matplotlib import ticker

## Set Styling
#pd.set_option("display.precision", 1)
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

line_color = sns.color_palette('vlag', n_colors=20)[0]

st.title("Batter Ability Metrics")
st.write('- ***Swing Aggression***: How much more often a batter swings at pitches, given the swing likelihoods of the pitches they face.')
st.write('''
- ***Strikezone Judgement***: The "correctness" of a batter's swings and takes, using the likelihood of a pitch being a called strike (for swings) or a ball/HBP (for takes).
''')
st.write("- ***Decision Value***: The opportunity cost of a batter's swing decision, using the predicted outcomes for that pitch.")
st.write("- ***Contact Ability***: A batter's ability to make contact (foul strike or BIP), above the contact expectation of each pitch.")
st.write("- ***Adjusted Power***: Modelled number of extra bases (aka ISO) above a pitch's expectation, for each BBE.")
st.write("- ***Hitter Efficiency***: wOBA added by the batter to each pitch they see (including swing/take decisions), after accounting for pitch quality.")

## Selectors
# Year
year = st.radio('Choose a year:', [2022,2021,2020])

def z_score_scaler(series):
    return (series - series.mean()) / series.std()

stat_names = {
    'swing_agg':'Swing Agg (%)',
    'strike_zone_judgement':'SZ Judge',
    'decision_value':'Dec Value',
    'contact_over_expected':'Contact',
    'adj_power':'Adj Power',
    'batter_wOBA':'Hit Eff'
}

# Load Data
def load_season_data():
    file_name = f'https://github.com/Blandalytics/PLV_viz/blob/main/data/{year}_PLV_App_Data.parquet?raw=true'
    df = pd.read_parquet(file_name)
    return df

plv_df = load_season_data()
plv_df['swing_agg'] = plv_df['swing_agg'].mul(100).astype('float')
plv_df['contact_over_expected'] = plv_df['contact_over_expected'].mul(100).astype('float')
plv_df['strike_zone_judgement'] = plv_df['strike_zone_judgement'].mul(100).astype('float')

season_df = (plv_df
             .rename(columns=stat_names)
             .groupby('hittername')
             [['pitch_id']+list(stat_names.values())]
             .agg({
                 'pitch_id':'count',
                 'Swing Agg (%)':'mean',
                 'SZ Judge':'mean',
                 'Dec Value':'mean',
                 'Contact':'mean',
                 'Adj Power':'mean',
                 'Hit Eff':'mean'
             })
             .query('pitch_id >= 400')
             .rename(columns={'hittername':'Name',
                              'pitch_id':'Pitches'})
             .sort_values('Hit Eff', ascending=False)
            )

for stat in ['SZ Judge','Contact','Dec Value','Adj Power','Hit Eff']:
    season_df[stat] = round(z_score_scaler(season_df[stat])*2+10,0)*5
    season_df[stat] = np.clip(season_df[stat], a_min=20, a_max=80).astype('int')

st.write('Metrics on a 20-80 scale. Table is sortable.')

def color_scale(v, cmap=''):
    return styler

st.dataframe(season_df
             .style
             .format(precision=1, thousands=',')
             .background_gradient(axis=None, vmin=20, vmax=80, cmap="vlag",
                                  subset=['SZ Judge','Dec Value','Contact',
                                          'Adj Power','Hit Eff']
                                 ) 
            )

### Rolling Charts
stat_names = {
    'swing_agg':'Swing Aggression',
    'strike_zone_judgement':'Strikezone Judgement',
    'decision_value':'Decision Value',
    'contact_over_expected':'Contact Ability',
    'adj_power':'Adjusted Power'
}
plv_df = plv_df.rename(columns=stat_names)
st.title("Rolling Ability Charts")
# Player
players = list(plv_df['hittername'].unique())
default_player = players.index('Juan Soto')
player = st.selectbox('Choose a player:', players, index=default_player)

# Metric
metrics = list(stat_names.values())
default_stat = metrics.index('Decision Value')
metric = st.selectbox('Choose a metric:', metrics, index=default_stat)

rolling_denom = {
    'Swing Aggression':'Pitches',
    'Strikezone Judgement':'Pitches',
    'Decision Value':'Pitches',
    'Contact Ability':'Swings',
    'Adjusted Power': 'BBE'
}

rolling_threshold = {
    'Swing Aggression':400,
    'Strikezone Judgement':400,
    'Decision Value':400,
    'Contact Ability':200,
    'Adjusted Power': 75
}

rolling_df = (plv_df
              .sort_values('pitch_id')
              .loc[(plv_df['hittername']==player),
                   ['hittername',metric]]
              .dropna()
              .reset_index(drop=True)
              .reset_index()
              #.assign(Rolling_Stat=lambda x: x[metric].rolling(window).mean())
             )

# Rolling Window
window = st.number_input(f'Choose a {rolling_denom[metric]} threshold:', 
                         min_value=50, 
                         max_value=int(round(rolling_df.shape[0]/10)*5),
                         step=5, 
                         value=rolling_threshold[metric])

rolling_df['Rolling_Stat'] = rolling_df[metric].rolling(window).mean()

def rolling_chart():
    rolling_df['index'] = rolling_df['index']+1 #Yay 0-based indexing
    fig, ax = plt.subplots(figsize=(6,6))
    sns.lineplot(data=rolling_df,
                 x='index',
                 y='Rolling_Stat',
                 color=line_color)

    ax.axhline(rolling_df[metric].mean(), 
               color=line_color,
               linestyle='--')
    ax.text(rolling_df.shape[0]*1.05,
            rolling_df[metric].mean(),
            'Szn Avg',
            va='center',
            color=sns.color_palette('vlag', n_colors=20)[3])

    ax.axhline(0 if metric in ['Swing Aggression','Contact Ability'] else plv_df[metric].mean(),
               color='w',
               linestyle='--',
               alpha=0.5)
    ax.text(rolling_df.shape[0]*1.05,
            0 if metric in ['Swing Aggression','Contact Ability'] else plv_df[metric].mean(),
            'MLB Avg' if abs(plv_df[metric].mean() - rolling_df[metric].mean()) > (ax.get_ylim()[1] - ax.get_ylim()[0])/25 else '',
            va='center',
            color='w',
            alpha=0.75)

    min_value = 50 if metric=='Strikezone Judgement' else 0

    ax.set(xlabel=rolling_denom[metric],
           ylabel=metric,
           ylim=(min(min_value,rolling_df['Rolling_Stat'].min(),plv_df[metric].mean()) + ax.get_ylim()[0]/20 * (-1 if ax.get_ylim()[0] >= 0 else 1),
                 max(0,rolling_df['Rolling_Stat'].max(),plv_df[metric].mean()) + ax.get_ylim()[1]/20),
           title="{}'s {} Rolling {} ({} {})".format(player,
                                                     year,
                                                     metric,
                                                     window,
                                                     rolling_denom[metric]))
    
    if metric in ['Swing Aggression','Contact Ability','Strikezone Judgement']:
        ax.yaxis.set_major_formatter(ticker.PercentFormatter())

    sns.despine()
    st.pyplot(fig)
if window > rolling_df.shape[0]:
    st.write(f'Not enough {rolling_denom[metric]} ({rolling_df.shape[0]})')
else:
    rolling_chart()
