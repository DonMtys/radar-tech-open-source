import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, List, Optional, Tuple

# --- PALAVRAS-CHAVE POR CATEGORIA (PT, EN, ZH-CN) ---

# 1. Robótica, Embodied AI e Coleta de Vídeos/Dados para Robôs
ROBOTICS_DATA_KEYWORDS_PT = [
    "robótica", "ia corporalizada", "embodied ai", "coleta de vídeo para robôs",
    "treinamento de robôs", "anotação de dados", "visão computacional",
    "empresas pagando por datasets", "dataset remunerado", "coleta de dados para ia",
    "bounty de dataset", "coleta de dados"
]
ROBOTICS_DATA_KEYWORDS_EN = [
    "robotics", "embodied ai", "robot training data", "robot training", "video collection",
    "data collection", "data annotation", "computer vision dataset", "paid dataset",
    "selling training data", "dataset bounty", "bounty", "robot vision dataset"
]
ROBOTICS_DATA_KEYWORDS_ZH = [
    "机器人", "具身智能", "采集视频", "机器人训练", "数据标注",
    "计算机视觉", "数据集付费", "数据采集悬赏", "训练数据采集"
]

# 2. Agentes de IA, Automação Comercial & Micro-SaaS
COMMERCIAL_SERVICES_KEYWORDS_PT = [
    "agente de ia", "automação de vendas", "serviço de ia", "freelance com ia",
    "micro-saas", "github", "open source", "bot telegram", "n8n", "make.com", "chatgpt",
    "automação comercial", "vídeo com ia", "marketing com ia", "serviços de automação",
    "vender ia para empresas", "trabalho remunerado ia"
]
COMMERCIAL_SERVICES_KEYWORDS_EN = [
    "ai agent", "ai service", "ai automation", "micro-saas", "github",
    "open source", "freelance ai", "chatgpt wrapper", "ai video generator",
    "ai marketing service", "no-code ai", "monetize ai", "remunerated ai job"
]
COMMERCIAL_SERVICES_KEYWORDS_ZH = [
    "ai代理服务", "商业自动化", "微型saas", "开源ai工具", "生成式ai服务",
    "视频生成ai", "ai营销服务", "兼职收益", "兼职收入", "赚取外汇", "首批付费客户"
]

# 3. Relatos e Provas de Receita
REVENUE_KEYWORDS_PT = [
    "renda extra", "ganhei r$", "faturei r$", "faturamento", "lucro", "primeiros clientes",
    "r$ 1.000", "r$ 5.000", "r$ 10.000", "minha agencia", "vendi meu agente"
]
REVENUE_KEYWORDS_EN = [
    "made $", "revenue", "mrr", "first $1k", "first $5k", "first $10k", "side income",
    "side hustle", "monetized", "first paid customers", "bootstrapped", "ai agency"
]
REVENUE_KEYWORDS_ZH = [
    "赚取美元", "月收入", "首期营收", "兼职变现", "ai变现"
]

# 4. Palavras-chave de Exclusão (Big Tech / Regulamentação / Geopolítica)
IRRELEVANT_KEYWORDS = [
    "sam altman congress", "nvidia stock", "billion dollar investment", "eu ai act",
    "regulamentação de ia", "tpu v5", "biden administration", "defense department",
    "semiconductor factory", "cotação de ações", "fusão bilionária", "bipartisan bill"
]

def parse_date_utc(date_str: Optional[str]) -> Tuple[Optional[datetime], str]:
    """
    Converte strings de data em um objeto datetime ciente do fuso horário (UTC).
    """
    if not date_str or not date_str.strip():
        return None, "em_revisao_data"

    date_str = date_str.strip()

    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt, "valida"
    except Exception:
        pass

    try:
        clean_iso = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt, "valida"
    except Exception:
        pass

    return None, "em_revisao_data"

def evaluate_recency(date_str: Optional[str], cutoff_days: int = 90) -> Dict[str, Any]:
    """
    Filtro temporal configurável de 90 dias em relação a UTC.
    """
    dt_utc, status_data = parse_date_utc(date_str)

    if status_data == "em_revisao_data" or dt_utc is None:
        return {
            "status_tempo": "em_revisao_data",
            "dias_antiguidade": None,
            "aprovado": False,
            "motivo": "Data não verificável ou ausente. Notícia colocada em revisão de data."
        }

    now_utc = datetime.now(timezone.utc)
    delta_days = (now_utc - dt_utc).days

    if delta_days < 0:
        delta_days = 0

    if delta_days > cutoff_days:
        return {
            "status_tempo": "descartado_antigo",
            "dias_antiguidade": delta_days,
            "aprovado": False,
            "motivo": f"Notícia com {delta_days} dias de antiguidade, excedendo o limite de {cutoff_days} dias."
        }

    return {
        "status_tempo": "recentemente_publicado",
        "dias_antiguidade": delta_days,
        "aprovado": True,
        "motivo": f"Notícia recente publicada há {delta_days} dias."
    }

CANDIDATE_KEYWORDS_ZH = [
    "求职", "找工作", "求职意向", "个人求职", "接单", "接私活", "自荐", 
    "寻找工作", "寻找机会", "求一个", "后端工程师求职", "前端工程师求职"
]
CANDIDATE_KEYWORDS_EN = [
    "for hire", "looking for work", "looking for a job", "available for freelance",
    "available for hire", "seeking employment", "seeking work", "hire me",
    "my portfolio", "open for work", "open to work"
]
CANDIDATE_KEYWORDS_PT = [
    "procurando trabalho", "procurando emprego", "buscando oportunidade",
    "disponível para freelance", "disponível para contratação", "ofereço meus serviços",
    "ofereço serviços", "meu portfólio"
]

BUYER_HIRING_KEYWORDS_ZH = [
    "招聘", "招具身智能", "诚聘", "招募", "兼职招募", "外包招聘", "寻找开发者",
    "寻找工程师", "数据采集招募", "付费采集", "悬赏"
]
BUYER_HIRING_KEYWORDS_EN = [
    "hiring", "we are hiring", "looking for someone to", "looking for a developer",
    "looking for an engineer", "looking to hire", "job opening", "bounty",
    "budget $", "paying $", "need an ai", "need someone to", "seeking a freelancer",
    "seeking a developer", "dataset bounty"
]
BUYER_HIRING_KEYWORDS_PT = [
    "contratando", "vaga aberta", "procuro desenvolvedor", "procuro freelancer",
    "preciso de alguém", "orçamento r$", "pagando r$", "oferta de trabalho"
]

KNOWN_BUYERS = [
    "scale ai", "appen", "remotasks", "physical intelligence", "tesla", "figma", 
    "upwork", "fiverr", "kaggle", "openai", "anthropic", "google", "meta", 
    "hugging face", "baidu", "tencent", "alibaba", "bytedance"
]

def analyze_semantic_demand(titulo: str, resumo: str, url_fonte: Optional[str] = None) -> Dict[str, Any]:
    """
    Validação Semântica de Demanda (Etapa 3.4.1):
    Diferencia candidaturas/ofertas de vendedores de ofertas reais de compradores/contratantes.
    Preenche campos fáticos sem inferências; usa "Não informado" quando omitidos na fonte.
    """
    texto_full = f"{titulo} {resumo}".lower()
    url_lower = (url_fonte or "").lower()

    # 1. Checa Postagem de Candidato / Vendedor
    is_candidate = any(kw in texto_full for kw in CANDIDATE_KEYWORDS_ZH + CANDIDATE_KEYWORDS_EN + CANDIDATE_KEYWORDS_PT)

    has_hiring_intent = any(kw in texto_full for kw in (
        BUYER_HIRING_KEYWORDS_ZH + BUYER_HIRING_KEYWORDS_EN + BUYER_HIRING_KEYWORDS_PT
    ))
    has_revenue_claim = any(kw in texto_full for kw in (
        REVENUE_KEYWORDS_ZH + REVENUE_KEYWORDS_EN + REVENUE_KEYWORDS_PT
    ))

    # 3. Identifica Nome do Comprador
    buyer_name = "Não informado"
    for b in KNOWN_BUYERS:
        if b in texto_full or b in url_lower:
            buyer_name = b.title()
            break

    if is_candidate:
        return {
            "buyer_present": False,
            "buyer_name": "Não informado",
            "buyer_type": "Não informado",
            "seller_present": True,
            "candidate_post": True,
            "hiring_intent": False,
            "revenue_claim": False,
            "payment_explicit": "Não informado",
            "remote_explicit": "Não informado",
            "brazil_eligible_explicit": "Não informado",
            "source_verified": True
        }

    buyer_present = has_hiring_intent or has_revenue_claim
    hiring_intent = has_hiring_intent

    # Extrai Valor / Pagamento Explicito (Sem inferências)
    money_match = re.search(r"(\$\s?\d+[\d\.,]*|r\$\s?\d+[\d\.,]*|\d+\s?元|\d+\s?美元)", texto_full)
    payment_explicit = money_match.group(0).upper() if money_match else "Não informado"

    # Extrai Trabalho Remoto Explicito
    remote_explicit = "Sim" if any(r in texto_full for r in ["remote", "remoto", "远程"]) else \
                      "Não" if any(r in texto_full for r in ["on-site", "presencial"]) else "Não informado"

    # Extrai Elegibilidade de Brasileiros Explicita
    brazil_eligible_explicit = "Sim" if any(b in texto_full for b in ["worldwide", "global", "brazil", "brasil", "latam", "anywhere"]) else \
                               "Não" if any(b in texto_full for b in ["us only", "us resident only", "ssn required", "china local only"]) else "Não informado"

    buyer_type = "empresa" if buyer_name != "Não informado" else \
                 ("plataforma" if any(p in url_lower for p in ["upwork", "scale", "appen"]) else \
                 ("cliente_individual" if buyer_present else "Não informado"))

    return {
        "buyer_present": buyer_present,
        "buyer_name": buyer_name,
        "buyer_type": buyer_type,
        "seller_present": False,
        "candidate_post": False,
        "hiring_intent": hiring_intent,
        "revenue_claim": has_revenue_claim,
        "payment_explicit": payment_explicit,
        "remote_explicit": remote_explicit,
        "brazil_eligible_explicit": brazil_eligible_explicit,
        "source_verified": True
    }

def determine_commercial_classification(
    texto: str, 
    nivel_comprovacao: str = "relato",
    url_fonte: Optional[str] = None,
    tem_link_original: bool = True,
    semantic_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Classificação Comercial Estrita (A, B, C, D) com Validação Semântica (Etapa 3.4.1):
    A — Comprador identificado + contratação explícita + pagamento explícito/documentado;
    B — Comprador identificado + contratação explícita + fonte original verificável;
    C — Possível demanda comercial, mas comprador ou condições incompletas;
    D — Discussão, notícia, candidato procurando emprego, vendedor oferecendo serviço.
    """
    if not semantic_info:
        semantic_info = analyze_semantic_demand(texto, "", url_fonte)

    # REGRA FUNDAMENTAL: Post de candidato ou sem comprador/demanda -> Classe D obrigatoriamente
    if semantic_info["candidate_post"] or semantic_info["seller_present"] or not semantic_info["buyer_present"]:
        return "D"

    texto_lower = texto.lower()
    url_lower = (url_fonte or "").lower()
    has_bounty_kw = any(k in texto_lower for k in ["dataset bounty", "hiring bounty", "vaga aberta", "contratando", "bounty remunerado", "paid video collection", "budget $", "orçamento", "looking for someone"])

    # CLASSE A: Somente evidência independente e verificável de pagamento efetivamente realizado
    if "audited report" in texto_lower or "contrato público auditado" in texto_lower or "payout confirmed" in texto_lower or nivel_comprovacao == "validacao_independente":
        return "A"

    # CLASSE B: Anúncios de contratação e ofertas ativas de contratação (exige intenção explícita de contratação)
    if (has_bounty_kw or semantic_info["hiring_intent"]) and (tem_link_original or "http" in texto_lower):
        return "B"

    if any(k in texto_lower for k in ["made $", "faturei r$", "ganhei r$", "my revenue", "mrr", "lucro de"]) or semantic_info.get("revenue_claim", False):
        return "C"

    return "D"

def categorize_record_type(texto: str, class_comercial: str) -> str:
    """
    Categorização Minuciosa dos 6 Tipos de Registro (Etapa 3.3):
    1. noticia_tecnologica
    2. oferta_contratacao
    3. programa_remuneracao
    4. relato_pessoal_faturamento
    5. servico_comprador_identificado
    6. hipotese_comercial
    """
    t_lower = texto.lower()

    if class_comercial == "A":
        return "programa_remuneracao"
    elif class_comercial == "B":
        if any(k in t_lower for k in ["video collection", "dataset", "anotação", "dados"]):
            return "programa_remuneracao"
        return "oferta_contratacao"
    elif class_comercial == "C":
        if any(k in t_lower for k in ["meu cliente", "vendi para", "serviço contratado", "primeiro cliente"]):
            return "servico_comprador_identificado"
        return "relato_pessoal_faturamento"
    else:
        if any(k in t_lower for k in ["micro-saas", "ideia", "oportunidade", "como monetizar", "tendência"]):
            return "hipotese_comercial"
        return "noticia_tecnologica"

def calculate_priority_score(
    dias_antiguidade: Optional[int],
    classificacao_comercial: str,
    possibilidade_execucao_br: str,
    investimento_baixo: bool,
    potencial_cliente: str,
    restricoes_geograficas: Optional[str] = None
) -> Tuple[float, str]:
    """
    Calcula a Pontuação de Prioridade (0.0 a 100.0) de forma transparente e revisada (Etapa 3.2).
    Evita pontuações inflacionadas em notícias da Classe D (Tendências/SEO/Especulações).
    Retorna (score, justificativa).
    """
    score = 0.0
    justificativas = []

    # 1. Recência (0 a 20 pontos)
    if dias_antiguidade is not None and dias_antiguidade >= 0:
        pts_rec = max(0.0, 20.0 - (dias_antiguidade * 20.0 / 90.0))
        score += pts_rec
        justificativas.append(f"Recência ({dias_antiguidade}d): +{pts_rec:.1f}pts")
    else:
        justificativas.append("Recência: 0.0pts (Data não verificada)")

    # 2. Evidência de Demanda Comercial (0 a 25 pontos)
    comercial_map = {"A": 25.0, "B": 20.0, "C": 10.0, "D": 0.0}
    pts_com = comercial_map.get(classificacao_comercial, 0.0)
    score += pts_com
    justificativas.append(f"Demanda Comercial (Classe {classificacao_comercial}): +{pts_com:.1f}pts")

    # 3. Facilidade de Testar no Brasil (0 a 25 pontos)
    if restricoes_geograficas and any(r in restricoes_geograficas.lower() for r in ["us only", "apenas eua", "ssn required", "somente china"]):
        justificativas.append("Execução no BR: 0.0pts (Restrição geográfica impeditiva)")
    else:
        br_map = {"alta": 25.0, "media": 15.0, "baixa": 5.0}
        pts_br = br_map.get(possibilidade_execucao_br.lower(), 0.0)
        if classificacao_comercial == "D":
            pts_br = min(pts_br, 5.0)
        score += pts_br
        justificativas.append(f"Execução no BR ({possibilidade_execucao_br}): +{pts_br:.1f}pts")

    # 4. Baixo Investimento Inicial (0 a 15 pontos)
    if investimento_baixo:
        score += 15.0
        justificativas.append("Investimento Inicial Baixo: +15.0pts")
    else:
        justificativas.append("Investimento Inicial: 0.0pts")

    # 5. Potencial do Primeiro Cliente (0 a 15 pontos)
    if classificacao_comercial == "D":
        justificativas.append("Potencial 1º Cliente: 0.0pts (Sem comprador identificado)")
    else:
        cliente_map = {"alto": 15.0, "medio": 10.0, "baixo": 5.0}
        pts_cli = cliente_map.get(potencial_cliente.lower(), 0.0)
        score += pts_cli
        justificativas.append(f"Potencial 1º Cliente ({potencial_cliente}): +{pts_cli:.1f}pts")

    final_score = round(score, 1)
    justificativa_texto = " | ".join(justificativas)
    return final_score, justificativa_texto

def classify_relevance(titulo: str, resumo: str, date_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Filtro de relevância expandido e revisado (Etapa 3.2).
    """
    texto_full = f"{titulo} {resumo}".lower()

    # 1. Filtro Temporal de 90 dias
    recency = evaluate_recency(date_str, cutoff_days=90)
    if not recency["aprovado"] and recency["status_tempo"] == "descartado_antigo":
        return {
            "is_relevant": False,
            "categoria": "irrelevante_generico",
            "status_tempo": recency["status_tempo"],
            "motivo": recency["motivo"],
            "classificacao_comercial": "D",
            "pontuacao_prioridade": 0.0,
            "justificativa_prioridade": "Descartado por ser notícia antiga (>90 dias)",
            "keywords_encontradas": []
        }

    # 2. Filtro de Exclusão Genérica
    for kw in IRRELEVANT_KEYWORDS:
        if kw in texto_full and not any(r_kw in texto_full for r_kw in REVENUE_KEYWORDS_PT + REVENUE_KEYWORDS_EN + REVENUE_KEYWORDS_ZH):
            return {
                "is_relevant": False,
                "categoria": "irrelevante_generico",
                "status_tempo": recency["status_tempo"],
                "motivo": f"Palavra-chave de exclusão detectada: '{kw}'",
                "classificacao_comercial": "D",
                "pontuacao_prioridade": 0.0,
                "justificativa_prioridade": f"Descartado por palavra irrelevante: '{kw}'",
                "keywords_encontradas": [kw]
            }

    # 3. Validação Semântica de Demanda (Etapa 3.4.1)
    semantic_info = analyze_semantic_demand(titulo, resumo)

    # REGRA FUNDAMENTAL: Post de candidato / vendedor sem comprador -> Classe D
    if semantic_info["candidate_post"] or semantic_info["seller_present"] or not semantic_info["buyer_present"]:
        return {
            "is_relevant": False,
            "categoria": "irrelevante_generico",
            "tipo_registro_minucioso": "candidato_ou_vendedor",
            "status_tempo": recency["status_tempo"],
            "motivo": "Post de candidato procurando emprego ou vendedor oferecendo serviços (sem comprador/contratante).",
            "classificacao_comercial": "D",
            "pontuacao_prioridade": 0.0,
            "justificativa_prioridade": "Descartado por ser candidato ou vendedor sem comprador contratante.",
            "keywords_encontradas": [],
            "semantic_info": semantic_info
        }

    # 4. Procura Palavras-Chave nas 3 línguas
    k_robotics = [k for k in (ROBOTICS_DATA_KEYWORDS_PT + ROBOTICS_DATA_KEYWORDS_EN + ROBOTICS_DATA_KEYWORDS_ZH) if k.lower() in texto_full]
    k_services = [k for k in (COMMERCIAL_SERVICES_KEYWORDS_PT + COMMERCIAL_SERVICES_KEYWORDS_EN + COMMERCIAL_SERVICES_KEYWORDS_ZH) if k.lower() in texto_full]
    k_revenue = [k for k in (REVENUE_KEYWORDS_PT + REVENUE_KEYWORDS_EN + REVENUE_KEYWORDS_ZH) if k.lower() in texto_full]

    # Identificação de Idioma / País
    pais_origem = "US" if any(c in texto_full for c in ["made $", "us$", "ai agency", "mrr", "paying $"]) else \
                  "CN" if any(c in texto_full for c in ROBOTICS_DATA_KEYWORDS_ZH + COMMERCIAL_SERVICES_KEYWORDS_ZH + REVENUE_KEYWORDS_ZH) else \
                  "BR" if any(c in texto_full for c in ["r$", "faturei", "renda extra"]) else "GL"

    classificacao_comercial = determine_commercial_classification(texto_full, semantic_info=semantic_info)
    tipo_registro = categorize_record_type(texto_full, classificacao_comercial)

    possibilidade_br = "alta" if semantic_info["brazil_eligible_explicit"] == "Sim" else ("baixa" if semantic_info["brazil_eligible_explicit"] == "Não" else "media")
    investimento_baixo = True
    potencial_cliente = "alto" if classificacao_comercial in ["A", "B"] else "medio"

    score, justificativa_prioridade = calculate_priority_score(
        dias_antiguidade=recency["dias_antiguidade"],
        classificacao_comercial=classificacao_comercial,
        possibilidade_execucao_br=possibilidade_br,
        investimento_baixo=investimento_baixo,
        potencial_cliente=potencial_cliente,
        restricoes_geograficas=semantic_info["brazil_eligible_explicit"]
    )

    categoria = "relato_receita" if k_revenue else ("ferramenta_oportunidade" if k_services else "demanda_comercial_verificada")

    return {
        "is_relevant": True,
        "categoria": categoria,
        "tipo_registro_minucioso": tipo_registro,
        "status_tempo": recency["status_tempo"],
        "motivo": "Oportunidade comercial com intenção explícita de contratação identificada.",
        "classificacao_comercial": classificacao_comercial,
        "pontuacao_prioridade": score,
        "justificativa_prioridade": justificativa_prioridade,
        "keywords_encontradas": k_robotics + k_services + k_revenue,
        "semantic_info": semantic_info,
        "estruturado": {
            "pais": pais_origem,
            "empresa_pessoa": semantic_info["buyer_name"],
            "servico_atividade": titulo,
            "quem_paga": semantic_info["buyer_name"],
            "valor_alegado": semantic_info["payment_explicit"],
            "tipo_evidencia": f"Anúncio Ativo ({semantic_info['buyer_type']})",
            "possibilidade_execucao_br": possibilidade_br,
            "restricoes_geograficas": "US Only / SSN Required" if "ssn required" in texto_full or "us resident only" in texto_full else ("Não informado" if semantic_info["brazil_eligible_explicit"] == "Não informado" else ("Atende Brasileiros" if semantic_info["brazil_eligible_explicit"] == "Sim" else "Restrição Geográfica Impeditiva")),
            "investimento_necessario": "Não informado",
            "hipotese_monetizacao": "Prestação direta de serviço de IA / Automação para o contratante",
            "proximo_passo_validacao": "Submeter proposta/candidatura ao comprador no link original",
            "forma_pagamento": semantic_info["payment_explicit"],
            "requisitos_tecnicos": "Python / Automação / IA (Conforme descrição original)",
            "tipo_oportunidade": tipo_registro,
            "evidencia_existencia": f"Publicação original de contratação ({semantic_info['buyer_name']})",
            "valor_orcamento_anunciado": semantic_info["payment_explicit"] if classificacao_comercial in ["B", "C"] else "Não informado",
            "valor_pagamento_comprovado": semantic_info["payment_explicit"] if classificacao_comercial == "A" else "Não informado",
            "evidencia_pagamento": "Relatório auditado / Comprovante de pagamento independente" if classificacao_comercial == "A" else ("Anúncio de contratação com orçamento anunciado (não comprova pagamento realizado)" if classificacao_comercial == "B" else "Não informado"),
            "status_verificacao": "pagamento_comprovado" if classificacao_comercial == "A" else ("orcamento_anunciado_nao_comprovado" if classificacao_comercial == "B" else "nao_verificado")
        }
    }
