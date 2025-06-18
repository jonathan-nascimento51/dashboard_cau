import os
from dotenv import load_dotenv
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from components.cards import make_level_card
from components.graphs import make_distribution_chart, make_trend_chart
from utils.data import load_data
from callbacks import register_callbacks

load_dotenv()

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY, '/assets/styles.css']
)

DEFAULT_START = os.getenv("DEFAULT_START_DATE")  # '2025-06-11'
DEFAULT_END   = os.getenv("DEFAULT_END_DATE")    # '2025-06-18'

app.layout = html.Div(className="layout-container", children=[
    html.Div(className="layout-header", children=[
        html.H1("Painel Casa Civil TI"),
        html.Div(
            dcc.DatePickerRange(
                id="date-range",
                start_date=DEFAULT_START,
                end_date=DEFAULT_END,
                display_format="DD/MM/YYYY"
            ),
            className="datepicker-custom"
        )
    ]),
    html.Div(id="cards-row", className="layout-cards"),
    html.Div(className="layout-charts", children=[
        make_distribution_chart(load_data(DEFAULT_START, DEFAULT_END)),
        make_trend_chart(load_data(DEFAULT_START, DEFAULT_END)),
    ])
])

register_callbacks(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)
