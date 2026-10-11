"""
Módulo de Integração do RADAR RENDA IA com a API Oficial do Telegram.
Oferece suporte a autenticação via .env, verificação de bot (getMe),
fila de moderação/aprovação, prevenção de envios duplicados no SQLite e modo simulado/mock.
"""

import os
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from database.db import get_connection, add_publicacao, update_publicacao_status

def load_env_file(env_path: str = ".env") -> Dict[str, str]:
    """
    Lê o arquivo .env se existente no diretório raiz e carrega variáveis no os.environ.
    Nunca expõe credenciais em logs.
    """
    env_vars = {}
    if not os.path.exists(env_path):
        return env_vars

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    env_vars[key] = val
                    if key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass
    return env_vars

def mask_secret(secret: Optional[str]) -> str:
    """Retorna uma versão mascarada de segredos para logs seguros."""
    if not secret or len(secret) < 8:
        return "***"
    return f"{secret[:4]}...{secret[-4:]}"

def get_telegram_config() -> Tuple[Optional[str], Optional[str]]:
    """Carrega credenciais do Telegram do ambiente ou do arquivo .env local."""
    load_env_file()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    return token, chat_id

def check_telegram_connection(token: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifica a conexão com a API do Telegram usando o método getMe.
    Retorna o status da conexão sem expor a chave de API nos logs.
    """
    if not token:
        token, _ = get_telegram_config()

    if not token or token == "seu_bot_token_aqui":
        return {
            "ok": False,
            "erro": "TELEGRAM_BOT_TOKEN não configurado no arquivo .env local ou variáveis de ambiente."
        }

    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data.get("ok"):
                bot_info = res_data.get("result", {})
                return {
                    "ok": True,
                    "id": bot_info.get("id"),
                    "first_name": bot_info.get("first_name"),
                    "username": bot_info.get("username"),
                    "can_join_groups": bot_info.get("can_join_groups")
                }
            else:
                return {"ok": False, "erro": res_data.get("description", "Erro desconhecido da API Telegram.")}
    except urllib.error.HTTPError as e:
        return {"ok": False, "erro": f"HTTP Error {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"ok": False, "erro": f"Erro de conexão com o Telegram: {e.reason}"}
    except Exception as e:
        return {"ok": False, "erro": f"Falha ao consultar Telegram getMe: {str(e)}"}

def check_telegram_channel_permissions(token: Optional[str] = None, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifica a conexão com getMe e testa as permissões do bot no canal especificado usando getChatMember.
    Retorna se o bot é administrador com permissão para publicar mensagens.
    """
    if not token or not chat_id:
        env_token, env_chat_id = get_telegram_config()
        token = token or env_token
        chat_id = chat_id or env_chat_id

    res_me = check_telegram_connection(token=token)
    if not res_me.get("ok"):
        return {"ok": False, "erro": f"Falha no getMe: {res_me.get('erro')}"}

    bot_id = res_me.get("id")
    bot_username = res_me.get("username")

    url = f"https://api.telegram.org/bot{token}/getChatMember?chat_id={urllib.parse.quote(str(chat_id))}&user_id={bot_id}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data.get("ok"):
                member = res_data.get("result", {})
                status = member.get("status")
                can_post = member.get("can_post_messages", False)
                is_admin = status in ["administrator", "creator"]
                
                return {
                    "ok": True,
                    "bot_id": bot_id,
                    "bot_username": bot_username,
                    "chat_id": chat_id,
                    "status_membro": status,
                    "e_administrador": is_admin,
                    "pode_publicar": can_post or is_admin,
                    "detalhes": member
                }
            else:
                return {
                    "ok": False,
                    "erro": f"Erro getChatMember: {res_data.get('description', 'Erro ao verificar permissões no canal.')}"
                }
    except urllib.error.HTTPError as e:
        return {"ok": False, "erro": f"HTTP Error {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"ok": False, "erro": f"Erro de conexão com getChatMember: {e.reason}"}
    except Exception as e:
        return {"ok": False, "erro": f"Falha ao consultar getChatMember: {str(e)}"}

def format_telegram_message(r: Dict[str, Any]) -> str:
    """
    Formata uma publicação estruturada em Markdown para o Telegram.
    """
    comprador = r.get("quem_paga") or r.get("empresa_pessoa") or "Não informado"
    servico = r.get("servico_atividade") or r.get("titulo") or "Não informado"
    link = r.get("url_original", "Não informado")
    data_pub = r.get("data_publicacao") or "Não informado"
    pais = r.get("pais", "GL")
    orcamento = r.get("valor_orcamento_anunciado") or r.get("valor_alegado") or "Não informado"
    pagamento_comprovado = r.get("valor_pagamento_comprovado") or "Não informado"
    evidencia_pag = r.get("evidencia_pagamento") or "Não informado"
    status_verif = r.get("status_verificacao") or "Não informado"
    forma_pag = r.get("forma_pagamento") or "Não informado"
    pode_br = "Sim" if r.get("possibilidade_execucao_br") in ["alta", "media", "Sim"] else "Não informado"
    restricoes = r.get("restricoes_geograficas") or "Não informado"
    requisitos = r.get("requisitos_tecnicos") or "Não informado"
    tipo_op = r.get("tipo_oportunidade") or "Não informado"
    classe = r.get("classificacao_comercial", "B")
    prioridade = r.get("pontuacao_prioridade", 0.0)

    msg = (
        f"🎯 *RADAR RENDA IA — OPORTUNIDADE COMERCIAL*\n\n"
        f"🏢 *Comprador / Contratante:* {comprador}\n"
        f"💼 *Serviço Solicitado:* {servico}\n"
        f"🔗 *Link Original:* {link}\n"
        f"📅 *Data da Publicação:* {data_pub}\n"
        f"🌐 *País:* {pais}\n"
        f"💰 *Orçamento Anunciado:* {orcamento}\n"
        f"✅ *Pagamento Comprovado:* {pagamento_comprovado}\n"
        f"🔍 *Evidência de Pagamento:* {evidencia_pag}\n"
        f"🛡️ *Status da Verificação:* {status_verif}\n"
        f"💳 *Forma de Pagamento:* {forma_pag}\n"
        f"🇧🇷 *Aceita Brasileiros:* {pode_br} ({restricoes})\n"
        f"🛠️ *Requisitos Técnicos:* {requisitos}\n"
        f"📌 *Tipo de Oportunidade:* {tipo_op}\n"
        f"🏷️ *Classificação:* Classe [{classe}] (Prioridade: {prioridade}/100)"
    )
    return msg

def get_chat_id_from_updates(token: Optional[str] = None) -> Optional[str]:
    """
    Busca o chat_id mais recente consultando getUpdates da API do Telegram.
    Útil caso o usuário tenha iniciado a conversa com o bot mas ainda não tenha inserido o chat_id no .env.
    """
    if not token:
        token, _ = get_telegram_config()
    if not token:
        return None

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data.get("ok"):
                results = res_data.get("result", [])
                for item in reversed(results):
                    message = item.get("message") or item.get("edited_message") or item.get("channel_post")
                    if message and "chat" in message:
                        chat_id = str(message["chat"]["id"])
                        return chat_id
    except Exception:
        pass
    return None

def send_telegram_message(
    text: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    mock: bool = False
) -> Dict[str, Any]:
    """
    Envia uma mensagem de texto via API do Telegram.
    Se mock=True, simula o envio e retorna um id fictício sem fazer requisição HTTP real.
    """
    if mock:
        return {
            "ok": True,
            "result": {"message_id": 999001, "text": text},
            "mocked": True
        }

    if not token or not chat_id:
        env_token, env_chat_id = get_telegram_config()
        token = token or env_token
        chat_id = chat_id or env_chat_id

    if not token or token == "seu_bot_token_aqui":
        return {"ok": False, "erro": "TELEGRAM_BOT_TOKEN não fornecido nem configurado."}

    if not chat_id or chat_id == "seu_chat_id_aqui":
        # Tenta descobrir o chat_id automaticamente via getUpdates
        discovered_chat_id = get_chat_id_from_updates(token)
        if discovered_chat_id:
            chat_id = discovered_chat_id
        else:
            return {"ok": False, "erro": "TELEGRAM_CHAT_ID não encontrado. Por favor, envie uma mensagem/Start para o bot @radar_renda_ia_bot no Telegram."}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": False
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data.get("ok"):
                return {
                    "ok": True,
                    "result": res_data.get("result", {}),
                    "message_id": res_data.get("result", {}).get("message_id")
                }
            else:
                return {"ok": False, "erro": res_data.get("description", "Erro ao enviar mensagem no Telegram.")}
    except urllib.error.HTTPError as e:
        return {"ok": False, "erro": f"HTTP Error {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"ok": False, "erro": f"Erro de conexão: {e.reason}"}
    except Exception as e:
        return {"ok": False, "erro": f"Falha ao enviar mensagem Telegram: {str(e)}"}

# --- GERENCIAMENTO DA FILA DE PUBLICAÇÃO NO SQLITE ---

def preparar_fila_publicacao(db_path: str, min_prioridade: float = 70.0) -> int:
    """
    Busca notícias coletadas relevantes (Classe A ou B) que ainda não estão na fila de publicação
    e insere na tabela 'publicacoes' com status 'pendente'.
    Retorna o número de novos itens adicionados à fila.
    """
    adicionados = 0
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT n.id, n.titulo, n.data_publicacao, n.url_original, n.classificacao_comercial,
                   n.pontuacao_prioridade,
                   o.pais, o.empresa_pessoa, o.servico_atividade, o.quem_paga, o.valor_alegado,
                   o.tipo_evidencia, o.possibilidade_execucao_br, o.restricoes_geograficas,
                   o.forma_pagamento, o.requisitos_tecnicos, o.tipo_oportunidade, o.evidencia_existencia,
                   o.valor_orcamento_anunciado, o.valor_pagamento_comprovado, o.evidencia_pagamento, o.status_verificacao
            FROM noticias n
            LEFT JOIN oportunidades o ON n.id = o.noticia_id
            WHERE n.status = 'coletado'
              AND n.classificacao_comercial IN ('A', 'B')
              AND n.pontuacao_prioridade >= ?
              AND n.id NOT IN (SELECT noticia_id FROM publicacoes)
            ORDER BY n.pontuacao_prioridade DESC
            """,
            (min_prioridade,)
        )
        rows = cursor.fetchall()

        for r in rows:
            dict_row = dict(r)
            texto_formatado = format_telegram_message(dict_row)
            try:
                cursor.execute(
                    "INSERT INTO publicacoes (noticia_id, texto_preparado, status_aprovacao) VALUES (?, ?, ?)",
                    (dict_row["id"], texto_formatado, "pendente")
                )
                adicionados += 1
            except sqlite3.IntegrityError:
                pass

    return adicionados

def get_publicacoes_pendentes(db_path: str) -> List[Dict[str, Any]]:
    """Retorna todas as publicações com status 'pendente'."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.id as publicacao_id, p.noticia_id, p.texto_preparado, p.status_aprovacao,
                   n.titulo, n.url_original, n.classificacao_comercial, n.pontuacao_prioridade
            FROM publicacoes p
            JOIN noticias n ON p.noticia_id = n.id
            WHERE p.status_aprovacao = 'pendente'
            ORDER BY n.pontuacao_prioridade DESC
            """
        )
        return [dict(row) for row in cursor.fetchall()]

def get_publicacoes_aprovadas(db_path: str) -> List[Dict[str, Any]]:
    """Retorna todas as publicações aprovadas aguardando envio."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.id as publicacao_id, p.noticia_id, p.texto_preparado, p.status_aprovacao,
                   n.titulo, n.url_original, n.classificacao_comercial
            FROM publicacoes p
            JOIN noticias n ON p.noticia_id = n.id
            WHERE p.status_aprovacao = 'aprovado'
            ORDER BY p.id ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]

def aprovar_publicacao(db_path: str, publicacao_id: int) -> bool:
    """Marca uma publicação como 'aprovado' no banco de dados."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return update_publicacao_status(db_path, publicacao_id, "aprovado", data_aprovacao=now_iso)

def rejeitar_publicacao(db_path: str, publicacao_id: int) -> bool:
    """Marca uma publicação como 'rejeitado' no banco de dados."""
    return update_publicacao_status(db_path, publicacao_id, "rejeitado")

def publicar_oportunidades_aprovadas(
    db_path: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    mock: bool = False
) -> Dict[str, Any]:
    """
    Publica no Telegram todas as oportunidades que foram aprovadas previamente.
    Garante idempotência: verifica registros no SQLite para evitar envios duplicados.
    """
    aprovadas = get_publicacoes_aprovadas(db_path)
    resumo = {
        "total_aprovadas": len(aprovadas),
        "enviadas_sucesso": 0,
        "falhas_envio": 0,
        "detalhes": []
    }

    now_iso = datetime.now(timezone.utc).isoformat()

    for item in aprovadas:
        pub_id = item["publicacao_id"]
        noticia_id = item["noticia_id"]
        texto = item["texto_preparado"]

        res_send = send_telegram_message(text=texto, token=token, chat_id=chat_id, mock=mock)

        if res_send.get("ok"):
            msg_id = res_send.get("message_id")
            update_publicacao_status(
                db_path,
                publicacao_id=pub_id,
                status_aprovacao="publicado",
                data_envio=now_iso,
                telegram_message_id=msg_id
            )
            with get_connection(db_path) as conn:
                conn.execute("UPDATE noticias SET status = 'publicado' WHERE id = ?", (noticia_id,))

            resumo["enviadas_sucesso"] += 1
            resumo["detalhes"].append({
                "publicacao_id": pub_id,
                "noticia_id": noticia_id,
                "status": "publicado",
                "message_id": msg_id
            })
        else:
            resumo["falhas_envio"] += 1
            resumo["detalhes"].append({
                "publicacao_id": pub_id,
                "noticia_id": noticia_id,
                "status": "erro",
                "erro": res_send.get("erro")
            })

    return resumo

def safe_str(s: str) -> str:
    """Substitui caracteres incompatíveis com a saída de texto."""
    if not s:
        return ""
    return s.encode("ascii", "replace").decode("ascii")

def format_telegram_pipeline_message(r: Dict[str, Any], is_test: bool = False) -> str:
    """
    Formata a mensagem para publicação no grupo do Telegram seguindo estritamente a estrutura solicitada.
    Se is_test=True, inclui '🧪 TESTE DO PIPELINE' no topo.
    Nunca infere dados; informações ausentes aparecem como 'Não informado'.
    """
    titulo = r.get("titulo") or r.get("servico_atividade") or "Não informado"
    contratante = r.get("quem_paga") or r.get("empresa_pessoa") or "Não informado"
    servico = r.get("servico_atividade") or r.get("titulo") or "Não informado"
    
    fonte_nome = r.get("fonte_nome") or "Fonte Pública"
    pais = r.get("pais") or "GL"
    fonte_pais = f"{fonte_nome} / {pais}"

    remuneracao = r.get("valor_orcamento_anunciado") or r.get("valor_alegado") or r.get("valor_pagamento_comprovado") or "Não informado"
    classe = r.get("classificacao_comercial", "B")
    prioridade = int(round(r.get("pontuacao_prioridade", 0.0)))
    data_pub = r.get("data_publicacao") or "Não informado"
    link = r.get("url_original") or "Não informado"

    prefixo = "🧪 TESTE DO PIPELINE\n\n" if is_test else ""

    msg = (
        f"{prefixo}🚨 NOVA OPORTUNIDADE — RADAR RENDA IA\n\n"
        f"📌 Título:\n{titulo}\n\n"
        f"🏢 Contratante:\n{contratante}\n\n"
        f"💼 Serviço:\n{servico}\n\n"
        f"🌎 Fonte/País:\n{fonte_pais}\n\n"
        f"💰 Remuneração:\n{remuneracao}\n\n"
        f"🧠 Classificação:\nClasse {classe}\n\n"
        f"⭐ Prioridade:\n{prioridade}/100\n\n"
        f"📅 Publicado:\n{data_pub}\n\n"
        f"🔗 Link:\n{link}"
    )
    return msg

def format_open_source_telegram_message(r: Dict[str, Any], is_test: bool = False) -> str:
    """
    Formata uma publicação de projeto Open Source ou Notícia Tech para o Telegram em PT-BR.
    """
    prefixo = "🧪 TESTE DO PIPELINE\n\n" if is_test else ""
    titulo = r.get("titulo") or "Não informado"
    fonte_nome = r.get("fonte_nome") or "GitHub Open Source"
    pais = r.get("pais") or "GL"
    estrelas = r.get("estrelas") or r.get("pontuacao_prioridade") or "Não informado"
    linguagem = r.get("requisitos_tecnicos") or r.get("ferramentas") or "Multilingue"
    o_que_faz = r.get("servico_atividade") or r.get("resumo_bruto") or "Não informado"
    aplicacao = r.get("hipotese_monetizacao") or r.get("proximo_passo_validacao") or "Automação e desenvolvimento de projetos."
    data_pub = r.get("data_publicacao") or "Não informado"
    link = r.get("url_original") or "Não informado"

    msg = (
        f"{prefixo}🔥 OPEN SOURCE & TECH — RADAR RENDA IA\n\n"
        f"📌 Projeto / Notícia:\n{titulo}\n\n"
        f"⭐ Estrelas / Fonte:\n{estrelas} ⭐ | {fonte_nome} ({pais})\n\n"
        f"🛠️ Tecnologia / Linguagem:\n{linguagem}\n\n"
        f"💡 O que faz (Funcionalidades):\n{o_que_faz}\n\n"
        f"🚀 Aplicação Prática:\n{aplicacao}\n\n"
        f"📅 Publicado / Criado:\n{data_pub}\n\n"
        f"🔗 Link Original:\n{link}"
    )
    return msg

def run_telegram_pipeline_round(
    db_path: str,
    min_prioridade: float = 0.0,
    modo_real: bool = True,
    mock_telegram: bool = False,
    max_daily_posts: int = 12
) -> Dict[str, Any]:
    """
    Executa uma rodada completa do pipeline automático:
    Coleta RSS + GitHub Open Source -> Filtro -> Classificação -> Ranking -> Telegram (com desduplicação no SQLite e limite de 12 publicações/dia).
    """
    from src.collector import run_coleta, run_coleta_real_supervisionada
    from src.config import CANDIDATE_FEEDS, MAX_REAL_SOURCES, MAX_REAL_HTTP_REQUESTS
    from src.github_trending import fetch_github_trending_repos, traduzir_e_explicar_repositorio
    from database.db import get_publicados_count_24h, registrar_metrica_canal, add_noticia, add_oportunidade
    from src.deduplicator import normalize_url, is_duplicate_url, compute_content_hash

    # 0. Verificação de Pausa de Emergência
    if os.getenv("PAUSE_RADAR") == "1":
        print("\n[PAUSA DE EMERGÊNCIA] Variável PAUSE_RADAR=1 detectada. Pipeline automático temporariamente suspenso.", flush=True)
        return {
            "total_coletados": 0,
            "passaram_filtro": 0,
            "qtd_ab": 0,
            "atingiram_score": 0,
            "enviados": 0,
            "message_ids": [],
            "ignorados_duplicidade": 0,
            "status": "pausado"
        }

    token, chat_id = get_telegram_config()

    # 1. Coleta Notícias RSS (US, China, Brasil)
    if modo_real:
        summary_coleta = run_coleta_real_supervisionada(
            db_path=db_path,
            fontes=CANDIDATE_FEEDS,
            max_fontes=MAX_REAL_SOURCES,
            max_requisicoes=MAX_REAL_HTTP_REQUESTS
        )
    else:
        summary_coleta = run_coleta(db_path, CANDIDATE_FEEDS[:2])

    total_coletados = summary_coleta["total_noticias_analisadas"]

    # 2. Coleta de Projetos Open Source no GitHub (Ascensão + Populares)
    if modo_real:
        try:
            print("\n[+] Coletando projetos Open Source no GitHub...", flush=True)
            repos_asc = fetch_github_trending_repos("ascensao", max_results=3)
            repos_pop = fetch_github_trending_repos("popular", max_results=2)
            all_repos = repos_asc + repos_pop

            for repo in all_repos:
                url_orig = repo.get("url_original")
                url_norm = normalize_url(url_orig)
                if not is_duplicate_url(db_path, url_norm):
                    t = traduzir_e_explicar_repositorio(repo)
                    hash_c = compute_content_hash(repo.get("nome_completo"), repo.get("descricao_original"))
                    noticia_id = add_noticia(
                        db_path=db_path,
                        fonte_id=None,
                        titulo=t.get("titulo_pt"),
                        url_original=url_orig,
                        url_normalizada=url_norm,
                        resumo_bruto=t.get("resumo_pt"),
                        hash_conteudo=hash_c,
                        data_publicacao=repo.get("data_publicacao"),
                        status="coletado",
                        status_novidade_br="novidade_no_brasil_nao_verificada",
                        classificacao_comercial="A",
                        pontuacao_prioridade=85.0
                    )
                    add_oportunidade(
                        db_path=db_path,
                        noticia_id=noticia_id,
                        modelo_negocio=repo.get("categoria_open_source", "open_source"),
                        ferramentas=repo.get("linguagem"),
                        quem_paga="Comunidade Open Source",
                        servico_atividade=t.get("funcionalidades"),
                        hipotese_monetizacao=t.get("aplicacao_pratica"),
                        pais=repo.get("pais", "US/GL"),
                        valor_orcamento_anunciado="Gratuito / Código Aberto"
                    )
                    total_coletados += 1
        except Exception as e:
            print(f"[!] Aviso: Coleta no GitHub enfrentou instabilidade: {e}", flush=True)

    # 3. Busca Oportunidades e Notícias Relevantes no SQLite
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT n.id, n.titulo, n.data_publicacao, n.url_original, n.classificacao_comercial,
                   n.pontuacao_prioridade, n.telegram_sent, f.nome as fonte_nome,
                   o.pais, o.empresa_pessoa, o.servico_atividade, o.quem_paga, o.valor_alegado,
                   o.valor_orcamento_anunciado, o.valor_pagamento_comprovado, o.evidencia_pagamento, o.status_verificacao
            FROM noticias n
            LEFT JOIN fontes f ON n.fonte_id = f.id
            LEFT JOIN oportunidades o ON n.id = o.noticia_id
            WHERE n.status IN ('coletado', 'analisado', 'aprovado', 'publicado')
            ORDER BY n.pontuacao_prioridade DESC
            """
        )
        rows = [dict(r) for r in cursor.fetchall()]

    passaram_filtro = len(rows)
    qtd_ab = sum(1 for r in rows if r["classificacao_comercial"] in ["A", "B"])
    atingiram_score = sum(1 for r in rows if r["classificacao_comercial"] in ["A", "B"] and r["pontuacao_prioridade"] >= min_prioridade)

    candidatos_envio = [
        r for r in rows
        if r["classificacao_comercial"] in ["A", "B"]
        and r["pontuacao_prioridade"] >= min_prioridade
        and (r.get("telegram_sent") or 0) == 0
    ]

    ignorados_duplicidade = sum(
        1 for r in rows
        if r["classificacao_comercial"] in ["A", "B"]
        and r["pontuacao_prioridade"] >= min_prioridade
        and (r.get("telegram_sent") or 0) == 1
    )

    # 4. Verifica Limite Diário de Publicações (máximo 12 por 24h)
    publicados_24h = get_publicados_count_24h(db_path)
    vagas_disponiveis = max(0, max_daily_posts - publicados_24h)

    print(f"\n[LIMITE DIÁRIO] Publicados nas últimas 24h: {publicados_24h}/{max_daily_posts} (Vagas restantes nesta rodada: {vagas_disponiveis})", flush=True)

    if vagas_disponiveis <= 0:
        print(f"[!] Limite máximo de {max_daily_posts} publicações por dia atingido. Nenhuma nova mensagem será enviada nesta rodada.", flush=True)
        candidatos_envio = []
    else:
        candidatos_envio = candidatos_envio[:vagas_disponiveis]

    enviados = 0
    message_ids = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for item in candidatos_envio:
        if "github.com" in (item.get("url_original") or "").lower():
            texto_formatado = format_open_source_telegram_message(item, is_test=False)
        else:
            texto_formatado = format_telegram_pipeline_message(item, is_test=False)

        res_send = send_telegram_message(text=texto_formatado, token=token, chat_id=chat_id, mock=mock_telegram)

        if res_send.get("ok"):
            msg_id = res_send.get("message_id")
            with get_connection(db_path) as conn:
                conn.execute(
                    """
                    UPDATE noticias
                    SET telegram_sent = 1,
                        telegram_sent_at = ?,
                        telegram_message_id = ?,
                        status = 'publicado'
                    WHERE id = ?
                    """,
                    (now_iso, msg_id, item["id"])
                )

            enviados += 1
            message_ids.append(msg_id)

            print("\n[TELEGRAM] Oportunidade/Notícia enviada com sucesso", flush=True)
            print(f"  Título:     {safe_str(item['titulo'])}", flush=True)
            print(f"  Classe:     {item['classificacao_comercial']}", flush=True)
            print(f"  Score:      {item['pontuacao_prioridade']}/100", flush=True)
            print(f"  chat_id:    {chat_id}", flush=True)
            print(f"  message_id: {msg_id}", flush=True)

    # 5. Registra Métricas da Execução no SQLite para monetização e auditoria
    registrar_metrica_canal(
        db_path=db_path,
        categoria="pipeline_automatico",
        total_analisados=total_coletados,
        total_aprovados=passaram_filtro,
        total_publicados=enviados,
        cliques_estimados=0,
        engajamento_score=0.0
    )

    return {
        "total_coletados": total_coletados,
        "passaram_filtro": passaram_filtro,
        "qtd_ab": qtd_ab,
        "atingiram_score": atingiram_score,
        "enviados": enviados,
        "message_ids": message_ids,
        "ignorados_duplicidade": ignorados_duplicidade,
        "publicados_24h": publicados_24h + enviados
    }

def run_telegram_pipeline_forced_test(
    db_path: str,
    modo_real: bool = True,
    mock_telegram: bool = False
) -> Dict[str, Any]:
    """
    Executa o teste forçado do pipeline (--telegram-pipeline-test).
    Seleciona UMA oportunidade Classe B do banco SQLite e envia para o grupo com prefixo '🧪 TESTE DO PIPELINE'.
    """
    token, chat_id = get_telegram_config()

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT n.id, n.titulo, n.data_publicacao, n.url_original, n.classificacao_comercial,
                   n.pontuacao_prioridade, f.nome as fonte_nome,
                   o.pais, o.empresa_pessoa, o.servico_atividade, o.quem_paga, o.valor_alegado,
                   o.valor_orcamento_anunciado, o.valor_pagamento_comprovado, o.evidencia_pagamento, o.status_verificacao
            FROM noticias n
            LEFT JOIN fontes f ON n.fonte_id = f.id
            LEFT JOIN oportunidades o ON n.id = o.noticia_id
            WHERE n.classificacao_comercial IN ('A', 'B')
            ORDER BY n.pontuacao_prioridade DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()

    if not row:
        from src.collector import run_coleta_real_supervisionada, run_coleta
        from src.config import CANDIDATE_FEEDS, MAX_REAL_SOURCES, MAX_REAL_HTTP_REQUESTS
        if modo_real:
            run_coleta_real_supervisionada(db_path, CANDIDATE_FEEDS, MAX_REAL_SOURCES, MAX_REAL_HTTP_REQUESTS)
        else:
            run_coleta(db_path, CANDIDATE_FEEDS[:2])

        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT n.id, n.titulo, n.data_publicacao, n.url_original, n.classificacao_comercial,
                       n.pontuacao_prioridade, f.nome as fonte_nome,
                       o.pais, o.empresa_pessoa, o.servico_atividade, o.quem_paga, o.valor_alegado,
                       o.valor_orcamento_anunciado, o.valor_pagamento_comprovado, o.evidencia_pagamento, o.status_verificacao
                FROM noticias n
                LEFT JOIN fontes f ON n.fonte_id = f.id
                LEFT JOIN oportunidades o ON n.id = o.noticia_id
                WHERE n.classificacao_comercial IN ('A', 'B')
                ORDER BY n.pontuacao_prioridade DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()

    if not row:
        from database.db import add_noticia, add_oportunidade
        id_test = add_noticia(
            db_path=db_path,
            fonte_id=None,
            titulo="Looking for AI Specialist to Build Customer Support Bot",
            url_original="https://news.ycombinator.com/item?id=99001",
            url_normalizada="https://news.ycombinator.com/item?id=99001",
            resumo_bruto="Hiring AI developer to automate support desk with LLM agent",
            hash_conteudo="hash_test_pipeline_forced",
            data_publicacao="2026-10-09",
            status="coletado",
            status_novidade_br="novidade_no_brasil_nao_verificada",
            classificacao_comercial="B",
            pontuacao_prioridade=85.0
        )
        add_oportunidade(
            db_path=db_path,
            noticia_id=id_test,
            modelo_negocio="automação_ia",
            quem_paga="E-Commerce Startup",
            servico_atividade="Desenvolvimento de Agente de IA para Suporte",
            pais="US",
            valor_orcamento_anunciado="US$ 500",
            valor_pagamento_comprovado="Não informado",
            evidencia_pagamento="Não informado",
            status_verificacao="Não informado",
            forma_pagamento="Não informado",
            requisitos_tecnicos="Python, OpenAI API, Telegram Webhooks",
            tipo_oportunidade="freelance",
            possibilidade_execucao_br="alta"
        )
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT n.id, n.titulo, n.data_publicacao, n.url_original, n.classificacao_comercial,
                       n.pontuacao_prioridade, f.nome as fonte_nome,
                       o.pais, o.empresa_pessoa, o.servico_atividade, o.quem_paga, o.valor_alegado,
                       o.valor_orcamento_anunciado, o.valor_pagamento_comprovado, o.evidencia_pagamento, o.status_verificacao
                FROM noticias n
                LEFT JOIN fontes f ON n.fonte_id = f.id
                LEFT JOIN oportunidades o ON n.id = o.noticia_id
                WHERE n.id = ?
                """,
                (id_test,)
            )
            row = cursor.fetchone()

    if not row:
        print("[!] Nenhuma oportunidade Classe A ou B disponível para teste.", flush=True)
        return {"ok": False, "erro": "Nenhuma oportunidade Classe A ou B encontrada."}

    dict_item = dict(row)
    texto_formatado = format_telegram_pipeline_message(dict_item, is_test=True)

    print("\n[ HTTP ] Enviando teste forçado do pipeline para o Telegram...", flush=True)
    res_send = send_telegram_message(text=texto_formatado, token=token, chat_id=chat_id, mock=mock_telegram)

    if res_send.get("ok"):
        msg_id = res_send.get("message_id")
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_connection(db_path) as conn:
            conn.execute(
                """
                UPDATE noticias
                SET telegram_sent = 1,
                    telegram_sent_at = ?,
                    telegram_message_id = ?,
                    status = 'publicado'
                WHERE id = ?
                """,
                (now_iso, msg_id, dict_item["id"])
            )

        print("\n[TELEGRAM] Oportunidade enviada com sucesso", flush=True)
        print(f"  Título:     {safe_str(dict_item['titulo'])}", flush=True)
        print(f"  Classe:     {dict_item['classificacao_comercial']}", flush=True)
        print(f"  Score:      {dict_item['pontuacao_prioridade']}/100", flush=True)
        print(f"  chat_id:    {chat_id}", flush=True)
        print(f"  message_id: {msg_id}", flush=True)

        return {
            "ok": True,
            "message_id": msg_id,
            "titulo": dict_item["titulo"],
            "classe": dict_item["classificacao_comercial"],
            "score": dict_item["pontuacao_prioridade"]
        }
    else:
        print(f"\n[ ERRO ] Falha ao enviar teste do pipeline: {res_send.get('erro')}", flush=True)
        return {"ok": False, "erro": res_send.get("erro")}

