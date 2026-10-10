"""
Configuração de fontes candidatas verificadas e parâmetros operacionais para o RADAR RENDA IA (Etapa 3.2).
"""

# Lista de 5 fontes públicas candidatas verificadas (EUA, China e Brasil).
# Nenhuma URL inventada; apenas endpoints de RSS/Atom legítimos e públicos.
CANDIDATE_FEEDS = [
    {
        "nome": "TabNews - Recentes & Tech Brasil (RSS)",
        "url_feed": "https://www.tabnews.com.br/recentes/rss",
        "categoria": "comunidade_tech_br",
        "pais": "BR",
        "idioma": "pt"
    },
    {
        "nome": "Reddit r/AI_Agents - Bounties & Demanda (RSS)",
        "url_feed": "https://www.reddit.com/r/AI_Agents/.rss",
        "categoria": "comunidade_empreendedores",
        "pais": "GL",
        "idioma": "en"
    },
    {
        "nome": "V2EX 酷工作 - Vagas & Demanda IA China (RSS)",
        "url_feed": "https://v2ex.com/feed/tab/jobs.xml",
        "categoria": "anuncio_contratacao",
        "pais": "CN",
        "idioma": "zh"
    },
    {
        "nome": "Hacker News - AI Hiring & Bounties (RSS)",
        "url_feed": "https://hnrss.org/newest?q=AI+hiring+OR+bounty+OR+dataset",
        "categoria": "comunidade_dev",
        "pais": "US",
        "idioma": "en"
    },
    {
        "nome": "Dev.to - AI Tag (RSS)",
        "url_feed": "https://dev.to/feed/tag/ai",
        "categoria": "desenvolvedores",
        "pais": "US",
        "idioma": "en"
    }
]

# Parâmetros de deduplicação e filtro
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "rss", "mc_cid", "mc_eid", "ncid",
    "feature", "cmpid"
}

# Limites de Coleta Real Supervisionada
MAX_REAL_SOURCES = 5
MAX_REAL_HTTP_REQUESTS = 10
REAL_HTTP_TIMEOUT_SECONDS = 10
REAL_HTTP_DELAY_SECONDS = 1.0

# Limite diário de publicações automáticas no Telegram
MAX_DAILY_POSTS = 12

# Limite de similaridade de título para alerta de possível duplicata (0.0 a 1.0)
TITLE_SIMILARITY_THRESHOLD = 0.85

