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

st.title("Hitter Ability Metrics")
st.write('- ***Swing Aggression***: How much more often a hitter swings at pitches, given the swing likelihoods of the pitches they face.')
st.write('''
- ***Strikezone Judgement***: The "correctness" of a hitter's swings and takes, using the likelihood of a pitch being a called strike (for swings) or a ball/HBP (for takes).
''')
st.write("- ***Decision Value***: Modeled value of a hitter's decision to swing or take, minus the modeled value of the other option.")
st.write("- ***Contact Ability***: A hitter's ability to make contact (foul strike or BIP), above the contact expectation of each pitch.")
st.write("- ***Power***: Modeled number of extra bases (aka ISO) above a pitch's expectation, for each BBE.")
st.write("- ***Hitter Perfromance (HP)***: wOBA added by the hitter to each pitch they see (including swing/take decisions), after accounting for pitch quality.")

## Selectors
# Year
year = st.radio('Choose a year:', [2022,2021,2020])

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
@st.cache
def load_season_data(year):
    file_name = f'https://github.com/Blandalytics/PLV_viz/blob/main/data/{year}_PLV_App_Data.parquet?raw=true'
    df = pd.read_parquet(file_name)[['hittername','pitch_id','swing_agg','strike_zone_judgement',
                                     'decision_value','contact_over_expected','adj_power','batter_wOBA']]
    
    for stat in ['swing_agg','strike_zone_judgement','contact_over_expected']:
        df[stat] = df[stat].mul(100).astype('float')
        
    return df

plv_df = load_season_data(year)

season_df = (plv_df
             .rename(columns=season_names)
             .groupby('hittername')
             [['pitch_id']+list(season_names.values())]
             .agg({
                 'pitch_id':'count',
                 'Swing Agg (%)':'mean',
                 'SZ Judge':'mean',
                 'Dec Value':'mean',
                 'Contact':'mean',
                 'Power':'mean',
                 'HP':'mean'
             })
             .query('pitch_id >= 400')
             .rename(columns={'hittername':'Name',
                              'pitch_id':'Pitches'})
             .sort_values('Hit Eff', ascending=False)
            )

for stat in ['SZ Judge','Contact','Dec Value','Power','HP']:
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
                                          'Power','HP']
                                 ) 
            )

### Rolling Charts
stat_names = {
    'swing_agg':'Swing Aggression',
    'strike_zone_judgement':'Strikezone Judgement',
    'decision_value':'Decision Value',
    'contact_over_expected':'Contact Ability',
    'adj_power':'Power',
    'batter_wOBA':'Hitter Performance'
}
plv_df = plv_df.rename(columns=stat_names)
st.title("Rolling Ability Charts")

# Player
players = list(plv_df.groupby('hittername', as_index=False)[['pitch_id','Hitter Performance']].agg({
    'pitch_id':'count',
    'Hitter Performance':'mean'}).query('pitch_id >=400').sort_values('Hitter Performance', ascending=False)['hittername'])
default_player = players.index('Juan Soto')
player = st.selectbox('Choose a hitter:', players, index=default_player)

# Metric
metrics = list(stat_names.values())
default_stat = metrics.index('Decision Value')
metric = st.selectbox('Choose a metric:', metrics, index=default_stat)

rolling_denom = {
    'Swing Aggression':'Pitches',
    'Strikezone Judgement':'Pitches',
    'Decision Value':'Pitches',
    'Contact Ability':'Swings',
    'Power': 'BBE',
    'Hitter Performance':'Pitches'
}

rolling_threshold = {
    'Swing Aggression':400,
    'Strikezone Judgement':400,
    'Decision Value':400,
    'Contact Ability':200,
    'Power': 75,
    'Hitter Performance':800
}

rolling_df = (plv_df
              .sort_values('pitch_id')
              .loc[(plv_df['hittername']==player),
                   ['hittername',metric]]
              .dropna()
              .reset_index(drop=True)
              .reset_index()
             )

window_max = max(rolling_threshold[metric],int(round(rolling_df.shape[0]/10)*5))

# Rolling Window
window = st.number_input(f'Choose a {rolling_denom[metric]} threshold:', 
                         min_value=50, 
                         max_value=window_max,
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
                 max(0,rolling_df['Rolling_Stat'].max(),plv_df[metric].mean()) + ax.get_ylim()[1]/10),
           title="{}'s {} Rolling {} ({} {})".format(player,
                                                     year,
                                                     metric,
                                                     window,
                                                     rolling_denom[metric]))
    
    if metric in ['Swing Aggression','Contact Ability','Strikezone Judgement']:
        #ax.yaxis.set_major_formatter(ticker.PercentFormatter())
        ax.set_yticklabels([f'{int(x)}%' for x in ax.get_yticks()])

    sns.despine()
    st.pyplot(fig)
if window > rolling_df.shape[0]:
    st.write(f'Not enough {rolling_denom[metric]} ({rolling_df.shape[0]})')
else:
    rolling_chart()
