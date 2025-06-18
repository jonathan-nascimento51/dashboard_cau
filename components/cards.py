import dash_bootstrap_components as dbc
from dash import html

def make_level_card(level: str, stats: dict, color: str) -> dbc.Card:
    items = []
    for metric, value in stats.items():
        items.append(
            html.Div([
                html.Span(f"{metric}:", className="me-2"),
                html.Span(value, className="fw-bold")
            ], className="d-flex justify-content-between px-2 py-1 border-bottom")
        )

    total = sum(stats.values())
    footer = dbc.CardFooter([
        html.Div("TOTAL", className="text-muted small text-center mb-1"),
        html.Div(total, className="h4 text-center mb-0")
    ], className="bg-light border-top py-2")

    return dbc.Card([
        dbc.CardHeader(html.H6(level, className="text-white m-0 text-center"),
                       style={"backgroundColor": color}),
        dbc.CardBody(items),
        footer
    ], className="card-custom shadow-sm")
