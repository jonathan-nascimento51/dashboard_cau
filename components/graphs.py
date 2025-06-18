import plotly.express as px
from dash import dcc
import pandas as pd

def make_distribution_chart(df: pd.DataFrame) -> dcc.Graph:
    d = df.copy()
    d['Total'] = d[["Novos","Em Atendimento","Resolvidos","Não Resolvidos"]].sum(axis=1)
    fig = px.bar(d, x='Nível', y='Total', title='Distribuição por Nível',
                 color='Nível', color_discrete_map={
                     'N1':'#2C7BE5','N2':'#F59C1A','N3':'#E91E63','N4':'#17B3A3'
                 })
    fig.update_layout(showlegend=False, margin=dict(l=20,r=20,t=40,b=20), height=300)
    fig.update_traces(marker_line_width=0)
    return dcc.Graph(figure=fig, config={'displayModeBar': False}, className='dash-graph')

def make_trend_chart(df: pd.DataFrame) -> dcc.Graph:
    trend = pd.DataFrame({
        'Data': pd.date_range(start=pd.Timestamp.today().normalize() - pd.Timedelta(days=6), periods=7),
        'Chamados': [2,3,1,5,3,6,9]
    })
    fig = px.line(trend, x='Data', y='Chamados', title='Chamados por Dia', markers=True)
    fig.update_layout(margin=dict(l=20,r=20,t=40,b=20), height=300)
    fig.update_traces(line=dict(width=2, color='#5C7CFA'))
    return dcc.Graph(figure=fig, config={'displayModeBar': False}, className='dash-graph')
