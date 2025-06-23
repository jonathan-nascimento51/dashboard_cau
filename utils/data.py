from pathlib import Path
from dotenv import load_dotenv
import os
import requests
import pandas as pd
from functools import lru_cache

# Carrega variáveis de ambiente do .env na raiz do projeto
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

API_URL_RAW = os.getenv("GLPI_API_URL")
API_URL = API_URL_RAW.rstrip("/") if API_URL_RAW else None
APP_TOKEN  = os.getenv("GLPI_APP_TOKEN")
USER_TOKEN = os.getenv("GLPI_USER_TOKEN")
DEFAULT_START_DATE = os.getenv("DEFAULT_START_DATE")
DEFAULT_END_DATE   = os.getenv("DEFAULT_END_DATE")

if not all([API_URL, APP_TOKEN, USER_TOKEN, DEFAULT_START_DATE, DEFAULT_END_DATE]):
    raise ValueError(
        "Defina GLPI_API_URL, GLPI_APP_TOKEN, GLPI_USER_TOKEN, DEFAULT_START_DATE e DEFAULT_END_DATE em .env"
    )

# Configura sessão com tokens e headers
session = requests.Session()
headers = {
    "App-Token": str(APP_TOKEN),
    "Authorization": f"user_token {USER_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}
# Remove any headers with None values
session.headers.update({k: v for k, v in headers.items() if v is not None})

# Inicia sessão GLPI para obter session_token
init_url = f"{API_URL}/initSession"
resp = session.get(init_url)
resp.raise_for_status()
data = resp.json()
SESSION_TOKEN = data.get("session_token")
if not SESSION_TOKEN:
    raise RuntimeError(f"Não foi possível obter session_token: {data!r}")
session.headers.update({"Session-Token": SESSION_TOKEN})


def fetch_glpi_tickets(start_date: str | None = None,
                       end_date:   str | None = None) -> list[dict]:
    """
    Busca todos tickets via GET /Ticket e filtra localmente pelo campo de data.
    Usa o primeiro campo de data encontrado entre 'date_creation', 'date', 'date_mod'.
    """
    start = start_date or DEFAULT_START_DATE
    end   = end_date   or DEFAULT_END_DATE

    url = f"{API_URL}/Ticket?range=0-1000"
    resp = session.get(url)
    resp.raise_for_status()
    tickets = resp.json()

    filtered = []
    for t in tickets:
        # detecta o campo de data disponível
        dt_full = t.get("date_creation") or t.get("date") or t.get("date_mod") or ""
        if not dt_full:
            continue
        # extrai apenas a parte AAAA-MM-DD
        dt_date = dt_full.split()[0]
        if start <= dt_date <= end:
            filtered.append(t)
    return filtered


@lru_cache(maxsize=4)
def load_data(start_date: str | None = None,
              end_date:   str | None = None) -> pd.DataFrame:
    """
    Carrega tickets filtrados e retorna DataFrame agregado por nível:
    ['Nível', 'Novos', 'Em Atendimento', 'Resolvidos', 'Não Resolvidos']
    """
    tickets = fetch_glpi_tickets(start_date, end_date)
    if not tickets:
        # retorna DataFrame com zeros para cada nível
        return pd.DataFrame({
            'Nível': ['N1','N2','N3','N4'],
            'Novos': [0,0,0,0],
            'Em Atendimento': [0,0,0,0],
            'Resolvidos': [0,0,0,0],
            'Não Resolvidos': [0,0,0,0]
        })

    df = pd.DataFrame(tickets)

    # Ajuste o nome do campo de nível conforme sua API
    df["Nível"] = df.get("itilcategories_id", pd.NA)
    df["Status"] = df.get("status", pd.NA)

    # Gera pivot table de contagem por nível e status
    pivot = pd.crosstab(df["Nível"], df["Status"]).reindex(
        index=["N1","N2","N3","N4"], fill_value=0
    )

    # Renomeia colunas de status para os nomes desejados
    pivot = pivot.rename(columns={
        # ajuste conforme seus códigos de status retornados pela API
        1: "Novos", 2: "Em Atendimento", 3: "Resolvidos", 4: "Não Resolvidos"
    })

    # Garante todas as colunas existam
    for col in ["Novos", "Em Atendimento", "Resolvidos", "Não Resolvidos"]:
        if col not in pivot:
            pivot[col] = 0

    print(df.head())
    print(pivot)

    result = pivot.reset_index().rename_axis(columns=None)
    return result
