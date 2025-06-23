import requests
import json

# --- Configurações da API do GLPI ---
import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()

# --- Configurações da API do GLPI ---
# Valores são obtidos das variáveis de ambiente
GLPI_URL = os.getenv("GLPI_URL")
APP_TOKEN = os.getenv("APP_TOKEN")
USER_TOKEN = os.getenv("USER_TOKEN")

# --- Variável para armazenar o Session-Token ---
SESSION_TOKEN = None

# --- Função para fazer chamadas à API ---
def call_glpi_api(endpoint, method="GET", params=None, data=None):
    global SESSION_TOKEN
    url = f"{GLPI_URL}{endpoint}"

    headers = {
        "App-Token": APP_TOKEN,
        "Content-Type": "application/json"
    }
    if SESSION_TOKEN:
        headers["Session-Token"] = SESSION_TOKEN
    else: # Se o session_token ainda não foi obtido (apenas para initSession), usa user_token
        headers["Authorization"] = f"user_token {USER_TOKEN}"

    try:
        response = requests.request(method, url, headers=headers, params=params, json=data)
        response.raise_for_status() # Lança um erro para status 4xx/5xx 

        # Tenta retornar JSON. Se falhar, imprime o conteúdo e retorna None. 
        try:
            return response.json()
        except json.JSONDecodeError:
            print(f"Aviso: Resposta da API para {endpoint} não é um JSON válido.")
            print(f"       Status Code: {response.status_code}, Conteúdo Bruto: {response.text[:500]}...")
            return None # Retorna None se não for JSON válido 

    except requests.exceptions.RequestException as e:
        print(f"Erro ao chamar a API GLPI no endpoint {endpoint}: {e}")
        if response is not None:
            print(f"Status Code: {response.status_code}, Response: {response.text}")
        return None

# --- Nova função para descoberta dinâmica de campos de grupo ---
def discover_group_field():
    """
    Descobre dinamicamente a entidade e os nomes dos campos para o ID do ticket
    e o ID do grupo, com fallbacks entre Ticket, Ticket_User e, se disponível, Ticket_Tgroup. 
    Retorna uma tupla (entidade_usada, ticket_id_field_name_for_search, group_id_field_name_direct, user_id_field_name_for_search, search_criteria_type). 
    group_id_field_name_direct pode ser o nome do campo direto no ticket/entidade auxiliar, ou None se precisar buscar via usuário. 
    user_id_field_name_for_search é o nome do campo para o ID do usuário (se a entidade for Ticket_User). 
    search_criteria_type é o valor numérico para o tipo de atribuição (ex: 2 para 'atribuído'). 
    Levanta um erro se não encontrar uma estratégia para obter o grupo. 
    """
    # Ordem de preferência para encontrar o grupo: Ticket direto -> Ticket_User -> Ticket_Tgroup
    # Importante: para search/Ticket_User e Ticket_Tgroup, o 'field' é o que importa nos critérios de busca.
    # Para Ticket, podemos usar o 'name' do campo se for uma propriedade direta do objeto Ticket.
    entities_to_check = {
        "Ticket": {
            "ticket_id_candidates_field": ["id"], # Campo interno 'id'
            "group_id_candidates_field": ["groups_id", "group_tech_id", "group_id"], # Tentar buscar grupo direto 
            "user_id_candidates_field": []
        },
        "Ticket_User": { # Se Ticket não tiver o grupo direto, usamos Ticket_User para achar o usuário e depois o grupo dele
            "ticket_id_candidates_field": ["tickets_id", "ticket_id", "id"], # 'id' do ticket no 'Ticket_User.Ticket.id'
            "user_id_candidates_field": ["users_id", "user_id", "id"] # O 'id' do usuário no 'Ticket_User.User.id' 
        },
        "Ticket_Tgroup": { # Se Ticket_User não for suficiente ou não existir
            "ticket_id_candidates_field": ["tickets_id", "ticket_id"],
            "group_id_candidates_field": ["groups_id", "group_id"],
            "user_id_candidates_field": []
        }
    }

    debug_logs = {}

    # --- Estratégia 1: Buscar group_id diretamente no Ticket ---
    print("Tentando Estratégia 1: Buscar grupo diretamente na entidade Ticket...")
    entity = "Ticket"
    options_raw = call_glpi_api(f"listSearchOptions/{entity}")
    debug_logs[entity] = options_raw

    if options_raw and isinstance(options_raw, dict):
        options = [opt for key, opt in options_raw.items() if isinstance(opt, dict) and key != 'common']
        
        print(f"  Campos 'field' -> 'name' encontrados em {entity}:")
        for opt in options:
            if 'field' in opt and 'name' in opt:
                print(f"    - {opt['field']} -> {opt['name']}")
        print(f"  JSON bruto para {entity}: {json.dumps(options_raw, indent=2)}\n")

        # No caso de Ticket, o ID do ticket em si é 'id' (field) e 'ID' (name)
        # Usamos o 'field' para acesso direto no objeto do ticket.
        ticket_id_field_for_access_in_ticket = next((opt['field'] for opt in options if opt.get('field') == 'id'), None)
        found_group_id_field_direct = None

        for candidate_field in entities_to_check[entity]["group_id_candidates_field"]:
            for opt in options:
                if opt.get('field') == candidate_field:
                    found_group_id_field_direct = opt['field'] # Usar o 'field' para acesso 
                    print(f"  DEBUG: Em '{entity}', campo de grupo '{candidate_field}' mapeado para '{found_group_id_field_direct}' (via 'field').")
                    break
            if found_group_id_field_direct:
                break
        
        if ticket_id_field_for_access_in_ticket and found_group_id_field_direct:
            print(f"  Estratégia 1 SUCESSO: Grupo encontrado diretamente no Ticket. Ticket ID Field (para acesso direto)='{ticket_id_field_for_access_in_ticket}', Grupo ID Field='{found_group_id_field_direct}'\n")
            # Retorna None para user_id_field_name_for_search e search_criteria_type, pois não são aplicáveis aqui
            return entity, ticket_id_field_for_access_in_ticket, found_group_id_field_direct, None, None
    else:
        print(f"  Aviso: Não foi possível obter as opções de busca para {entity} ou a resposta não é um dicionário válido. Prosseguindo para a próxima estratégia.")

    # --- Estratégia 2: Buscar grupo via Ticket_User e User ---
    print("Tentando Estratégia 2: Buscar grupo via Ticket_User e entidade User...")
    entity = "Ticket_User"
    options_raw = call_glpi_api(f"listSearchOptions/{entity}")
    debug_logs[entity] = options_raw

    if options_raw and isinstance(options_raw, dict):
        options = [opt for key, opt in options_raw.items() if isinstance(opt, dict) and key != 'common']

        print(f"  Campos 'field' -> 'name' encontrados em {entity}:")
        for opt in options:
            if 'field' in opt and 'name' in opt:
                print(f"    - {opt['field']} -> {opt['name']}")
        print(f"  JSON bruto para {entity}: {json.dumps(options_raw, indent=2)}\n")

        found_ticket_id_field_for_search = None
        found_user_id_field_for_search = None
        
        # Para Ticket_User, o ID do ticket é o 'field' 'id' que tem 'name' 'Chamado' 
        for opt in options:
            if opt.get('name') == "Chamado" and opt.get('field') == 'id' and opt.get('table') == 'glpi_tickets':
                found_ticket_id_field_for_search = opt['field'] # Usar o 'field' para critérios de busca 
                print(f"  DEBUG: Em '{entity}', campo de ticket ID '{opt['field']}' mapeado para '{found_ticket_id_field_for_search}' (via 'name' 'Chamado').")
                break
        
        # Para Ticket_User, o ID do usuário é o 'field' 'id' que tem 'name' 'Usuário' 
        for opt in options:
            if opt.get('name') == "Usuário" and opt.get('field') == 'id' and opt.get('table') == 'glpi_users':
                found_user_id_field_for_search = opt['field'] # Usar o 'field' para critérios de busca 
                print(f"  DEBUG: Em '{entity}', campo de usuário '{opt['field']}' mapeado para '{found_user_id_field_for_search}' (via 'name' 'Usuário').")
                break
        
        # O tipo de atribuição (e.g., 2 para 'assign') pode não estar em listSearchOptions, 
        # mas sabemos que é um campo comum em Ticket_User.  Vamos assumir 'type' como field. 
        # Se não funcionar, o call_glpi_api vai mostrar erro no critério. 
        # Como o JSON fornecido não mostra um campo 'type', vamos assumir que o 'field' 'type' existe 
        # mas não é listado, ou que não precisamos filtrar por ele se só há atribuições. 
        # Mas para a busca, se quisermos 'type=2', precisamos do 'field' 'type'. 
        type_field_name_for_search = 'type' # Assumindo 'type' é o field padrão, mesmo que não listado 

        if found_ticket_id_field_for_search and found_user_id_field_for_search:
            print(f"  Estratégia 2 SUCESSO: Grupo será buscado via Ticket_User -> User. Ticket ID Field (para busca)='{found_ticket_id_field_for_search}', User ID Field (para busca)='{found_user_id_field_for_search}'\n")
            # Retorna None para group_id_field_name_direct pois ele não está direto nesta entidade, e sim no User
            return entity, found_ticket_id_field_for_search, None, found_user_id_field_for_search, 2 # 2 é o tipo para atribuição 
    else:
        print(f"  Aviso: Não foi possível obter as opções de busca para {entity} ou a resposta não é um dicionário válido. Prosseguindo para a próxima estratégia.")

    # --- Estratégia 3: Buscar grupo via Ticket_Tgroup (se existir) ---
    print("Tentando Estratégia 3: Buscar grupo via Ticket_Tgroup...")
    entity = "Ticket_Tgroup"
    options_raw = call_glpi_api(f"listSearchOptions/{entity}")
    debug_logs[entity] = options_raw

    if options_raw and isinstance(options_raw, dict): # Apenas se a entidade existir e retornar algo 
        options = [opt for key, opt in options_raw.items() if isinstance(opt, dict) and key != 'common']

        print(f"  Campos 'field' -> 'name' encontrados em {entity}:")
        for opt in options:
            if 'field' in opt and 'name' in opt:
                print(f"    - {opt['field']} -> {opt['name']}")
        print(f"  JSON bruto para {entity}: {json.dumps(options_raw, indent=2)}\n")

        found_ticket_id_field_for_search = None
        found_group_id_field_direct = None

        for candidate_field in entities_to_check[entity]["ticket_id_candidates_field"]:
            for opt in options:
                if opt.get('field') == candidate_field:
                    found_ticket_id_field_for_search = opt['field']
                    print(f"  DEBUG: Em '{entity}', campo de ticket ID '{candidate_field}' mapeado para '{found_ticket_id_field_for_search}'.")
                    break
            if found_ticket_id_field_for_search:
                break
        
        for candidate_field in entities_to_check[entity]["group_id_candidates_field"]:
            for opt in options:
                if opt.get('field') == candidate_field:
                    found_group_id_field_direct = opt['field']
                    print(f"  DEBUG: Em '{entity}', campo de grupo '{candidate_field}' mapeado para '{found_group_id_field_direct}'.")
                    break
                if "name" in opt and "grupo" in opt['name'].lower() and opt.get('field') and opt['field'].endswith('_id'):
                    found_group_id_field_direct = opt['field']
                    print(f"  DEBUG: Em '{entity}', candidato a campo de grupo '{opt['field']}' mapeado para '{found_group_id_field_direct}' (via 'name' contendo 'Grupo' e '_id').")
                    break
            if found_group_id_field_direct:
                break

        if found_ticket_id_field_for_search and found_group_id_field_direct:
            print(f"  Estratégia 3 SUCESSO: Grupo encontrado via Ticket_Tgroup. Ticket ID (para busca)='{found_ticket_id_field_for_search}', Grupo ID (direto)='{found_group_id_field_direct}'\n")
            # Retorna None para user_id_field_name_for_search, pois não é aplicável aqui
            return entity, found_ticket_id_field_for_search, found_group_id_field_direct, None, 2 # Assume tipo 2 para Tgroup também 
    else:
        print(f"  Aviso: Entidade {entity} não retornou dados válidos ou não existe. Finalizando.")


    # Se chegou até aqui, significa que nenhuma estratégia foi bem-sucedida
    error_msg = "Erro Crítico: Não foi possível encontrar uma estratégia para vincular tickets a grupos após tentar Ticket, Ticket_User e Ticket_Tgroup.\n"
    for entity, raw_data in debug_logs.items():
        error_msg += f"\n--- JSON de listSearchOptions/{entity} ---\n"
        error_msg += json.dumps(raw_data, indent=2) + "\n"
    raise ValueError(error_msg)


# --- Main Logic ---
def main():
    global SESSION_TOKEN
    processed_tickets_count = 0
    results_table = []
    
    assignment_search_range = "0-1" # Buscar apenas 1 resultado para otimizar

    print("Iniciando consulta à API do GLPI...\n")

    # --- 0. Inicializar a Sessão e obter o Session-Token ---
    print("0. Inicializando sessão para obter Session-Token...")
    init_session_headers = {
        "App-Token": APP_TOKEN,
        "Authorization": f"user_token {USER_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        init_response = requests.get(f"{GLPI_URL}initSession", headers=init_session_headers)
        init_response.raise_for_status()
        session_data = init_response.json()
        SESSION_TOKEN = session_data.get("session_token")
        if not SESSION_TOKEN:
            print(f"Erro: 'session_token' não encontrado na resposta de initSession. Resposta: {session_data}")
            return
        print(f"  Session-Token obtido com sucesso: {SESSION_TOKEN[:10]}...\n")
    except requests.exceptions.RequestException as e:
        print(f"Erro fatal ao iniciar a sessão GLPI: {e}")
        if init_response is not None:
            print(f"Status Code: {init_response.status_code}, Response: {init_response.text}")
        return

    # A partir daqui, todas as chamadas `call_glpi_api` usarão o `SESSION_TOKEN`

    # 1. Obter nomes internos dos campos para Ticket (para exibir título e status)
    print("1. Buscando searchOptions para Ticket (para metadados básicos)...")
    ticket_options_raw = call_glpi_api("listSearchOptions/Ticket")
    if not ticket_options_raw:
        print("Erro: Não foi possível obter as opções de busca para Ticket. Verifique o log acima para detalhes da resposta da API.")
        return
    if not isinstance(ticket_options_raw, dict):
        print(f"Erro Crítico: Resposta inesperada para listSearchOptions/Ticket. Esperado um dicionário, recebido: {type(ticket_options_raw)}. Conteúdo: {str(ticket_options_raw)[:500]}...")
        return
    ticket_options = [opt for key, opt in ticket_options_raw.items() if isinstance(opt, dict) and key != 'common']

    # IMPORTANTE: Para search/Ticket, os dados vêm com os 'field's internos como chaves, não os 'name's.
    # Precisamos do 'field' 'id' para acessar o ID do ticket.
    # O 'name' será usado apenas para exibição ou critérios de busca onde o GLPI aceita o 'name'.
    ticket_id_field_for_access = next((opt['field'] for opt in ticket_options if opt.get('field') == 'id'), 'id') # Usar 'field' para acesso 
    ticket_name_field_for_display = next((opt['name'] for opt in ticket_options if opt.get('field') == 'name'), 'Título')
    ticket_status_field_for_display = next((opt['name'] for opt in ticket_options if opt.get('field') == 'status'), 'Status')
    print(f"  Campos do Ticket: ID (acesso interno)={ticket_id_field_for_access}, Título (display)={ticket_name_field_for_display}, Status (display)={ticket_status_field_for_display}\n")

    # **NOVO**: Chamada à função de descoberta dinâmica de campos de grupo
    try:
        entity_for_group, ticket_field_in_entity, group_field_in_entity_direct, user_id_field_in_entity, search_criteria_type = discover_group_field()
        print(f"Descoberta de campos de grupo concluída. Usando entidade: '{entity_for_group}'")
        if ticket_field_in_entity:
            print(f"  Campo de ID do Ticket na entidade: '{ticket_field_in_entity}'")
        if group_field_in_entity_direct:
            print(f"  Campo de ID do Grupo DIRETO na entidade: '{group_field_in_entity_direct}'")
        if user_id_field_in_entity:
            print(f"  Campo de ID do Usuário na entidade: '{user_id_field_in_entity}'")
        if search_criteria_type:
            print(f"  Critério de tipo de busca: '{search_criteria_type}'")
        print("\n")
    except ValueError as e:
        print(e)
        return

    # 2. Obter nomes internos dos campos para User (para buscar grupo principal do usuário se necessário)
    print("2. Buscando searchOptions para User...")
    user_options_raw = call_glpi_api("listSearchOptions/User")
    if not user_options_raw:
        print("Erro: Não foi possível obter as opções de busca para User. Verifique o log acima.")
        return
    if not isinstance(user_options_raw, dict):
        print(f"Erro Crítico: Resposta inesperada para listSearchOptions/User. Esperado um dicionário, recebido: {type(user_options_raw)}. Conteúdo: {str(user_options_raw)[:500]}...")
        return
    user_options = [opt for key, opt in user_options_raw.items() if isinstance(opt, dict) and key != 'common']
    user_groups_id_field_for_access = next((opt['field'] for opt in user_options if opt.get('field') == 'groups_id'), 'groups_id') # Usar o 'field' para acesso ao objeto User 
    print(f"  Campo de User (acesso interno para grupo): Group ID={user_groups_id_field_for_access}\n")

    # 3. Obter nomes internos dos campos para Group (para obter o nome do grupo)
    print("3. Buscando searchOptions para Group...")
    group_options_raw = call_glpi_api("listSearchOptions/Group")
    if not group_options_raw:
        print("Erro: Não foi possível obter as opções de busca para Group. Verifique o log acima.")
        return
    if not isinstance(group_options_raw, dict):
        print(f"Erro Crítico: Resposta inesperada para listSearchOptions/Group. Esperado um dicionário, recebido: {type(group_options_raw)}. Conteúdo: {str(group_options_raw)[:500]}...")
        return
    group_options = [opt for key, opt in group_options_raw.items() if isinstance(opt, dict) and key != 'common']
    group_name_field_for_display = next((opt['name'] for opt in group_options if opt.get('field') == 'name'), 'name') # Usar o 'name' para exibição 
    print(f"  Campo de Group (display): Nome={group_name_field_for_display}\n")

    # 4. Buscar todos os Tickets
    print("4. Buscando todos os Tickets...")
    # Explicitamente solicitar os campos necessários na busca de tickets
    # O "field" 'id' é crucial para identificar o ticket.
    # 'name' é o título e 'status' é o status.
    search_ticket_params = {
        "fields": "id,name,status"
    }
    tickets_response = call_glpi_api("search/Ticket", params=search_ticket_params)

    if not tickets_response:
        print("Erro: Não foi possível buscar os tickets. Verifique o log acima para detalhes da resposta da API.")
        return
    if not isinstance(tickets_response, dict) or 'data' not in tickets_response or not isinstance(tickets_response['data'], list):
        print(f"Erro Crítico: Resposta inesperada para search/Ticket. Esperado um dicionário com chave 'data' sendo uma lista. Conteúdo: {str(tickets_response)[:500]}...")
        return
    tickets = tickets_response['data']
    print(f"  Encontrados {len(tickets)} tickets.\n")

    # Iterar sobre cada Ticket
    for ticket in tickets:
        # Acessar os dados do ticket usando os 'field's internos, não os 'name's que são para display
        ticket_id = ticket.get('id') # Agora esperamos que 'id' esteja presente 
        ticket_title = ticket.get('name')
        ticket_status = ticket.get('status')

        if not ticket_id:
            print(f"Aviso: Ticket sem ID encontrado no objeto. Pulando.")
            print(f"  DEBUG: Objeto do ticket sem ID: {ticket}") # Adicionado para depuração
            continue

        processed_tickets_count += 1
        group_id = "N/A"
        group_name = "N/A"
        
        print(f"Processando Ticket ID: {ticket_id} - Título: {ticket_title}")

        # --- Lógica para buscar atribuição de grupo ---
        if entity_for_group == "Ticket" and group_field_in_entity_direct and ticket.get(group_field_in_entity_direct) is not None:
            # Estratégia 1: Grupo encontrado diretamente no ticket
            group_id = ticket[group_field_in_entity_direct]
            print(f"  Ticket {ticket_id} -> Grupo ID '{group_id}' (diretamente no Ticket)")
        elif entity_for_group == "Ticket_User" and ticket_field_in_entity and user_id_field_in_entity:
            # Estratégia 2: Buscar via Ticket_User -> User -> Group
            search_params = {
                f"criteria[0][field]": ticket_field_in_entity, # Ex: 'id' 
                f"criteria[0][value]": ticket_id,
                "range": assignment_search_range
            }
            if search_criteria_type:
                # Inclui o critério de tipo, se houver.  Assumimos 'type' como o 'field' interno. 
                # Nota: Seu JSON de Ticket_User não lista 'type', mas é um campo comum. 
                # Se der erro, pode ser que o GLPI não permita filtrar por 'type' aqui. 
                search_params[f"criteria[1][field]"] = "type"
                search_params[f"criteria[1][value]"] = search_criteria_type

            print(f"  DEBUG: Requisição para search/{entity_for_group} com parâmetros: {search_params}")
            ticket_assignments_response = call_glpi_api(f"search/{entity_for_group}", params=search_params)

            if ticket_assignments_response and isinstance(ticket_assignments_response, dict) and 'data' in ticket_assignments_response and isinstance(ticket_assignments_response['data'], list) and len(ticket_assignments_response['data']) > 0:
                assignment = ticket_assignments_response['data'][0]
                # Acessa o ID do usuário usando o 'field' que descobrimos (ex: 'id' para 'Usuário')
                user_id = assignment.get(user_id_field_in_entity)

                if user_id is not None:
                    print(f"  DEBUG: Atribuição a usuário {user_id} encontrada em {entity_for_group}. Buscando grupo principal do usuário...")
                    # Acessa o detalhes do usuário pelo ID e busca o group_id usando o 'field' descoberto para User
                    user_details = call_glpi_api(f"User/{user_id}")
                    if user_details and isinstance(user_details, dict) and user_details.get(user_groups_id_field_for_access) is not None:
                        group_id = user_details.get(user_groups_id_field_for_access)
                        print(f"  Ticket {ticket_id} -> Grupo ID '{group_id}' (via Ticket_User -> User)")
                    else:
                        print(f"  Aviso: Não foi possível encontrar o grupo principal do usuário {user_id} ou resposta inesperada para User/{user_id}.")
                else:
                    print(f"  Aviso: Atribuição em {entity_for_group} sem user_id válido para o Ticket {ticket_id}.")
            else:
                print(f"  Nenhuma atribuição encontrada para o Ticket {ticket_id} na entidade {entity_for_group}.")
        elif entity_for_group == "Ticket_Tgroup" and ticket_field_in_entity and group_field_in_entity_direct:
            # Estratégia 3: Buscar via Ticket_Tgroup (se encontrado pela descoberta)
            search_params = {
                f"criteria[0][field]": ticket_field_in_entity,
                f"criteria[0][value]": ticket_id,
                # Não é necessário o critério de grupo aqui, pois estamos buscando o registro da relação, não filtrando pelo grupo. 
                # Se o GLPI exigir o grupo para a busca em Ticket_Tgroup, a lógica precisaria de mais um passo. 
                "range": assignment_search_range
            }
            if search_criteria_type:
                search_params[f"criteria[1][field]"] = "type"
                search_params[f"criteria[1][value]"] = search_criteria_type

            print(f"  DEBUG: Requisição para search/{entity_for_group} com parâmetros: {search_params}")
            ticket_assignments_response = call_glpi_api(f"search/{entity_for_group}", params=search_params)
            
            if ticket_assignments_response and isinstance(ticket_assignments_response, dict) and 'data' in ticket_assignments_response and isinstance(ticket_assignments_response['data'], list) and len(ticket_assignments_response['data']) > 0:
                assignment = ticket_assignments_response['data'][0]
                # Acessa o group_id usando o 'field' que descobrimos para Ticket_Tgroup
                group_id = assignment.get(group_field_in_entity_direct)
                if group_id is not None:
                    print(f"  Ticket {ticket_id} -> Grupo ID '{group_id}' (via Ticket_Tgroup)")
                else:
                    print(f"  Aviso: Grupo ID nulo ou não encontrado em {entity_for_group} para o Ticket {ticket_id}.")
            else:
                print(f"  Nenhuma atribuição encontrada para o Ticket {ticket_id} na entidade {entity_for_group}.")
        else:
            print(f"  Nenhum método de atribuição de grupo configurado ou detectado para o Ticket {ticket_id}.")


        # Obter o nome do Grupo
        if group_id != "N/A":
            group_details = call_glpi_api(f"Group/{group_id}")
            if group_details and isinstance(group_details, dict) and group_details.get(group_name_field_for_display) is not None:
                group_name = group_details.get(group_name_field_for_display)
                print(f"Ticket {ticket_id} → Grupo {group_name} (ID: {group_id})")
            else:
                print(f"  Aviso: Não foi possível obter o nome para o Grupo ID {group_id} ou resposta inesperada para Group/{group_id}.")
                print(f"Ticket {ticket_id} → Grupo {group_id}") # Mostra o ID se o nome não for encontrado 
        else:
            print(f"Ticket {ticket_id} → Nenhum grupo encontrado nas entidades: Ticket, Ticket_User, Ticket_Tgroup")

        results_table.append({
            "Ticket ID": ticket_id,
            "Título": ticket_title,
            "Status": ticket_status,
            "Group ID": group_id,
            "Nome do Grupo": group_name
        })
        print("-" * 30)

    # --- Gerar Tabela Markdown ---
    print("\n--- Tabela de Resultados ---\n")
    if not results_table:
        print("Nenhum ticket processado para gerar a tabela.")
        return

    headers = ["Ticket ID", "Título", "Status", "Group ID", "Nome do Grupo"]
    markdown_table = "| " + " | ".join(headers) + " |\n"
    markdown_table += "|---|---|---|---|---|\n"

    for row in results_table:
        markdown_table += "| " + " | ".join([str(row[h]) for h in headers]) + " |\n"

    print(markdown_table)

    # --- Sumário ---
    print("\n--- Sumário ---")
    print(f"Total de Tickets processados: {processed_tickets_count}")
    print(f"Tickets com atribuições de grupo encontradas: {len([r for r in results_table if r['Group ID'] != 'N/A'])}")

if __name__ == "__main__":
    main()