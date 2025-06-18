from pathlib import Path
from dotenv import load_dotenv

# ➜ Ajuste aqui o path para o seu .env
# Se o .env fica na raiz do projeto (um nível acima desta pasta):
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import os
import requests
import pandas as pd
from functools import lru_cache

API_URL    = os.getenv("GLPI_API_URL")
APP_TOKEN  = os.getenv("GLPI_APP_TOKEN")
USER_TOKEN = os.getenv("GLPI_USER_TOKEN")

if not all([API_URL, APP_TOKEN, USER_TOKEN]):
    raise ValueError(
        "Defina GLPI_API_URL, GLPI_APP_TOKEN e GLPI_USER_TOKEN em .env"
    )

session = requests.Session()
session.headers.update({
    "App-Token": str(APP_TOKEN),
    "Authorization": f"user_token {str(USER_TOKEN)}",
    "Content-Type": "application/json"
})

DEFAULT_START_DATE = os.getenv("DEFAULT_START_DATE")  # 2025-06-11
DEFAULT_END_DATE   = os.getenv("DEFAULT_END_DATE")    # 2025-06-18

def fetch_glpi_tickets(start_date: str | None = None,
                       end_date:   str | None = None) -> list[dict]:
    """
    Busca tickets. Se datas forem None, usa valores padrão do .env.
    """
    start_date = start_date or DEFAULT_START_DATE
    end_date   = end_date   or DEFAULT_END_DATE

    # se as duas datas existem, usar POST /search/Ticket
    if start_date and end_date:
        url = f"{API_URL}/search/Ticket"
        payload = {
            "criteria": [{
                "field": "date", "searchtype": "between",
                "value": [start_date, end_date]
            }],
            "range": "0-1000"
        }
        resp = session.post(url, json=payload)
    else:
        url  = f"{API_URL}/Ticket"
        resp = session.get(url)

    resp.raise_for_status()
    data = resp.json()
    return data["data"] if isinstance(data, dict) else data


@lru_cache(maxsize=4)
def load_data(start_date: str | None = None,
              end_date:   str | None = None) -> pd.DataFrame:
    tickets = fetch_glpi_tickets(start_date, end_date)
    df = pd.DataFrame(tickets)
    level_map = {10:"N1",20:"N2",30:"N3",40:"N4"}
    df["Nível"] = df["9"].astype(int).map(level_map).fillna("N1")
    df["status"] = df["10"].astype(int)
    stats = df.groupby("Nível")["status"].value_counts().unstack(fill_value=0)
    def classify(s):
        return "Novos" if s==1 else "Em Atendimento" if s==2 else "Resolvidos" if s==3 else "Não Resolvidos"
    records = []
    for lvl, row in stats.iterrows():
        rec = {"Nível":lvl}
        rec.update({classify(s):c for s,c in row.items()})
        records.append(rec)
    result = pd.DataFrame(records)
    cols = ["Nível","Novos","Em Atendimento","Resolvidos","Não Resolvidos"]
    return result[cols]
