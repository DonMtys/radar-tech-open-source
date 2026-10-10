"""
Módulo de Descoberta de Fontes Comerciais e Demanda de Compradores (Etapa 3.3).
Mapeia e cataloga fontes candidatas de contratação, bounties e programas de remuneração de IA (EUA, China, Brasil e Global).
"""

from typing import List, Dict, Any, Optional

# Temas e palavras-chave de busca comercial (EN, ZH, PT)
COMMERCIAL_SEARCH_THEMES = [
    # Robótica / Embodied AI e Coleta de Vídeos/Datasets remunerada
    "Robot training video collection paid",
    "Egocentric video data collection jobs",
    "Robotics dataset bounty",
    "Embodied AI data collection",
    "具身智能 数据采集 招募",
    "机器人训练 视频采集 兼职",
    
    # Agentes de IA, Automação e Primeiros Clientes
    "AI automation agency first clients",
    "AI agent bounty paid",
    "Data annotation paid tasks",
    "RLHF video recording bounty"
]

CANDIDATE_COMMERCIAL_SOURCES: List[Dict[str, Any]] = [
    {
        "id": "scale_ai_public_bounties",
        "nome": "Scale AI Public Bounties & Data Collection (EUA/Global)",
        "pais": "US",
        "categoria": "anotacao_dados_video",
        "url": "https://scale.com/blog/rss",
        "metodo_acesso": "RSS",
        "autenticacao_necessaria": False,
        "status_verificacao": "verificada",
        "justificativa_comercial": "Scale AI contrata contribuidores globais para coleta de dados de vídeo egocêntrico e anotação para treinamento de modelos de robótica.",
        "restricao_brasileiros": "Executável no Brasil via pagamento internacional (PayPal/Wise); não exige SSN norte-americano para freelancers remotos.",
        "temas_busca": ["Robot training video collection paid", "Egocentric video data collection jobs", "Embodied AI data collection"]
    },
    {
        "id": "v2ex_china_jobs_ai",
        "nome": "V2EX 酷工作 - Vagas & Remuneração IA (China)",
        "pais": "CN",
        "categoria": "anuncio_contratacao",
        "url": "https://v2ex.com/feed/tab/jobs.xml",
        "metodo_acesso": "RSS",
        "autenticacao_necessaria": False,
        "status_verificacao": "verificada",
        "justificativa_comercial": "Fórum principal de desenvolvedores na China com ofertas diretas de contratação para coleta de dados de visão computacional e automação.",
        "restricao_brasileiros": "Requer domínio de mandarim básico ou tradução; pagamentos podem exigir USDT/Crypto ou conta intermediária se o contratante for 100% local.",
        "temas_busca": ["具身智能 数据采集 招募", "机器人训练 视频采集 兼职"]
    },
    {
        "id": "reddit_ai_agents_demand",
        "nome": "Reddit r/AI_Agents - Client Demand & Bounties (Global)",
        "pais": "GL",
        "categoria": "comunidade_empreendedores",
        "url": "https://www.reddit.com/r/AI_Agents/.rss",
        "metodo_acesso": "RSS",
        "autenticacao_necessaria": False,
        "status_verificacao": "verificada",
        "justificativa_comercial": "Comunidade ativa onde empresas e fundadores postam necessidades de automação com agentes de IA e contratam desenvolvedores freelance.",
        "restricao_brasileiros": "100% remoto e acessível para brasileiros; negociação direta via Stripe/PayPal/Wise.",
        "temas_busca": ["AI automation agency first clients", "AI agent bounty paid"]
    },
    {
        "id": "upwork_ai_automation_rss",
        "nome": "Upwork - AI Automation & Chatbot Bounties (EUA/Global)",
        "pais": "US",
        "categoria": "marketplace_automacao",
        "url": "https://www.upwork.com/ab/feed/jobs/rss?q=ai+automation+agent",
        "metodo_acesso": "RSS",
        "autenticacao_necessaria": False,
        "status_verificacao": "candidata_em_investigacao",
        "justificativa_comercial": "Feed público de empregos onde compradores reais postam orçamento específico para criação de agentes de IA.",
        "restricao_brasileiros": "Acessível para brasileiros com conta verificada na plataforma; pagamentos diretos em USD convertidos para BRL.",
        "temas_busca": ["AI automation agency first clients", "AI agent bounty paid"]
    },
    {
        "id": "juejin_china_ai_services",
        "nome": "Juejin (掘金) - Demanda Comercial IA (China)",
        "pais": "CN",
        "categoria": "embodied_ai_dataset",
        "url": "https://juejin.cn/rss",
        "metodo_acesso": "RSS",
        "autenticacao_necessaria": False,
        "status_verificacao": "candidata_em_investigacao",
        "justificativa_comercial": "Plataforma chinesa de artigos técnicos e demanda comercial por datasets de robótica e agentes de automação.",
        "restricao_brasileiros": "Requer tradução para chinês simplificado; viável para prestação de serviço remoto.",
        "temas_busca": ["具身智能 数据采集 招募", "机器人训练 视频采集 兼职"]
    }
]

def get_candidate_commercial_sources() -> List[Dict[str, Any]]:
    """Retorna a lista completa de fontes comerciais candidatas catalogadas."""
    return CANDIDATE_COMMERCIAL_SOURCES

def search_candidate_sources_by_country(pais: str) -> List[Dict[str, Any]]:
    """Filtra fontes comerciais candidatas por país (US, CN, BR, GL)."""
    return [s for s in CANDIDATE_COMMERCIAL_SOURCES if s["pais"].upper() == pais.upper()]

def search_candidate_sources_by_theme(theme: str) -> List[Dict[str, Any]]:
    """Busca fontes que abordem determinado tema de pesquisa."""
    t_lower = theme.lower()
    results = []
    for s in CANDIDATE_COMMERCIAL_SOURCES:
        for t in s.get("temas_busca", []):
            if t_lower in t.lower():
                results.append(s)
                break
    return results
