from dash import Input, Output
import dash_bootstrap_components as dbc
from utils.data import load_data
from components.cards import make_level_card

def register_callbacks(app):
    @app.callback(
        Output("cards-row","children"),
        Input("date-range","start_date"),
        Input("date-range","end_date")
    )
    def update_cards(start_date, end_date):
        df = load_data(start_date, end_date)
        colors = ['#2C7BE5','#F59C1A','#E91E63','#17B3A3']
        cols = []
        for i, (_, row) in enumerate(df.iterrows()):
            stats = {k: int(row[k]) for k in ['Novos','Em Atendimento','Resolvidos','Não Resolvidos']}
            cols.append(dbc.Col(make_level_card(f"NÍVEL {row['Nível']}", stats, colors[i]), width=3, className="p-1"))
        return cols
