import time
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
import socket
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

from database.db import get_connection, add_noticia, add_oportunidade
from src.deduplicator import normalize_url, compute_content_hash, is_duplicate_url, find_similar_noticia
from src.relevance_filter import classify_relevance

def parse_rss_content(xml_text: str, source_name: str) -> List[Dict[str, Any]]:
    """
    Parser robusto para RSS 2.0 e Atom utilizando a biblioteca padrão (xml.etree.ElementTree).
    Trata namespaces e formatos comuns sem depender de pacotes externos.
    """
    items = []
    if not xml_text or not xml_text.strip():
        return items

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"Erro ao interpretar XML do feed: {e}")

    tag = root.tag.lower()

    if "rss" in tag or root.find("channel") is not None:
        channel = root.find("channel")
        if channel is None:
            channel = root
        for elem in channel.findall("item"):
            titulo = elem.findtext("title") or "Sem título"
            link = elem.findtext("link") or ""
            resumo = elem.findtext("description") or elem.findtext("encoded") or ""
            data_pub = elem.findtext("pubDate") or elem.findtext("date") or ""

            items.append({
                "titulo": titulo.strip(),
                "link": link.strip(),
                "resumo": resumo.strip(),
                "data_publicacao": data_pub.strip(),
                "fonte": source_name
            })

    elif "feed" in tag: # Atom Feed
        ns = ""
        if "}" in root.tag:
            ns = root.tag.split("}")[0] + "}"

        for entry in root.findall(f"{ns}entry"):
            titulo = entry.findtext(f"{ns}title") or "Sem título"
            link_elem = entry.find(f"{ns}link")
            link = ""
            if link_elem is not None:
                link = link_elem.attrib.get("href", "")
            if not link:
                link = entry.findtext(f"{ns}id") or ""

            resumo = entry.findtext(f"{ns}summary") or entry.findtext(f"{ns}content") or ""
            data_pub = entry.findtext(f"{ns}published") or entry.findtext(f"{ns}updated") or ""

            items.append({
                "titulo": titulo.strip(),
                "link": link.strip(),
                "resumo": resumo.strip(),
                "data_publicacao": data_pub.strip(),
                "fonte": source_name
            })
    else:
        raise ValueError(f"Conteúdo XML não corresponde a um feed RSS/Atom válido (tag raiz: '{root.tag}')")

    return items

def fetch_feed_url(url: str, timeout: int = 5, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RadarRendaIA/1.0") -> Tuple[Optional[str], Optional[str]]:
    """
    Busca o conteúdo XML de uma URL utilizando urllib.request com timeout reduzido de 5s para agilidade e tratamento de erros.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/atom+xml, text/xml, application/xml, */*"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read().decode("utf-8", errors="replace")
            return content, None
    except urllib.error.HTTPError as e:
        return None, f"Erro HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, f"Erro de Conexão/URL: {e.reason}"
    except (socket.timeout, TimeoutError):
        return None, "Timeout atingido durante a conexão."
    except Exception as e:
        return None, f"Erro inesperado: {str(e)}"

def safe_str(s: str) -> str:
    if not s:
        return ""
    return s.encode("ascii", "replace").decode("ascii")

def process_feed(
    db_path: str,
    fonte: Dict[str, Any],
    xml_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Processa um feed RSS: busca, parseia, normaliza, desduplica, filtra por recência/relevância e persiste no SQLite.
    """
    nome_fonte = fonte.get("nome", "Fonte Desconhecida")
    url_feed = fonte.get("url_feed", "")
    fonte_id = fonte.get("id")

    if fonte_id is not None:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM fontes WHERE id = ?", (fonte_id,))
            if not cursor.fetchone():
                fonte_id = None

    stats = {
        "fonte": nome_fonte,
        "total_lidos": 0,
        "relevantes": 0,
        "descartados": 0,
        "descartados_antigos": 0,
        "descartados_topico": 0,
        "em_revisao_data": 0,
        "duplicatas_url": 0,
        "similares_alertados": 0,
        "classificacao_A": 0,
        "classificacao_B": 0,
        "classificacao_C": 0,
        "classificacao_D": 0,
        "erro": None
    }

    if xml_override is not None:
        xml_content, error = xml_override, None
    else:
        print(f" [HTTP] Requisitando feed: {url_feed} ...", flush=True)
        xml_content, error = fetch_feed_url(url_feed)

    if error:
        print(f" [HTTP ERRO] {safe_str(nome_fonte)}: {error}", flush=True)
        stats["erro"] = error
        return stats

    try:
        raw_items = parse_rss_content(xml_content, nome_fonte)
    except Exception as e:
        print(f" [XML ERRO] {safe_str(nome_fonte)}: {e}", flush=True)
        stats["erro"] = str(e)
        return stats

    print(f" [HTTP OK] {safe_str(nome_fonte)}: {len(raw_items)} itens lidos.", flush=True)
    stats["total_lidos"] = len(raw_items)

    for item in raw_items:
        url_orig = item["link"]
        url_norm = normalize_url(url_orig)
        titulo = item["titulo"]
        resumo = item["resumo"]
        data_pub = item.get("data_publicacao")
        hash_c = compute_content_hash(titulo, resumo)

        # 1. Checa duplicata por URL normalizada
        if is_duplicate_url(db_path, url_norm):
            stats["duplicatas_url"] += 1
            stats["descartados"] += 1
            continue

        # 2. Checa similaridade com títulos existentes
        similar = find_similar_noticia(db_path, titulo)
        if similar:
            stats["similares_alertados"] += 1

        # 3. Classificação por relevância, recência (90 dias) e viabilidade comercial
        classificacao = classify_relevance(titulo, resumo, date_str=data_pub)
        is_relevant = classificacao["is_relevant"]
        categoria = classificacao["categoria"]
        status_tempo = classificacao["status_tempo"]
        class_comercial = classificacao.get("classificacao_comercial", "D")
        priority_score = classificacao.get("pontuacao_prioridade", 0.0)

        if status_tempo == "descartado_antigo":
            status_noticia = "descartado_antigo"
            stats["descartados_antigos"] += 1
            stats["descartados"] += 1
        elif status_tempo == "em_revisao_data":
            status_noticia = "em_revisao_data"
            stats["em_revisao_data"] += 1
            if not is_relevant:
                stats["descartados_topico"] += 1
                stats["descartados"] += 1
        elif is_relevant:
            status_noticia = "coletado"
            stats["relevantes"] += 1
        else:
            status_noticia = "rejeitado"
            stats["descartados_topico"] += 1
            stats["descartados"] += 1

        key_class = f"classificacao_{class_comercial}"
        if key_class in stats:
            stats[key_class] += 1

        # 4. Salva Notícia no SQLite
        noticia_id = add_noticia(
            db_path=db_path,
            fonte_id=fonte_id,
            titulo=titulo,
            url_original=url_orig,
            url_normalizada=url_norm,
            resumo_bruto=f"[{categoria.upper()}] {resumo}",
            hash_conteudo=hash_c,
            data_publicacao=data_pub,
            status=status_noticia,
            status_novidade_br="novidade_no_brasil_nao_verificada",
            classificacao_comercial=class_comercial,
            pontuacao_prioridade=priority_score
        )

        # 5. Salva Estrutura de Oportunidade se relevante
        if is_relevant and "estruturado" in classificacao:
            est = classificacao["estruturado"]
            add_oportunidade(
                db_path=db_path,
                noticia_id=noticia_id,
                modelo_negocio=categoria,
                ferramentas=", ".join(classificacao.get("keywords_encontradas", [])),
                publico_alvo=est.get("quem_paga"),
                dificuldade_estimada="media",
                custo_estimado=0.0,
                potencial_venda=0.0,
                pais=est.get("pais", "GL"),
                empresa_pessoa=est.get("empresa_pessoa"),
                servico_atividade=est.get("servico_atividade"),
                quem_paga=est.get("quem_paga"),
                valor_alegado=est.get("valor_alegado"),
                tipo_evidencia=est.get("tipo_evidencia"),
                possibilidade_execucao_br=est.get("possibilidade_execucao_br"),
                restricoes_geograficas=est.get("restricoes_geograficas"),
                investimento_necessario=est.get("investimento_necessario"),
                hipotese_monetizacao=est.get("hipotese_monetizacao"),
                proximo_passo_validacao=est.get("proximo_passo_validacao"),
                forma_pagamento=est.get("forma_pagamento", "Não informado"),
                requisitos_tecnicos=est.get("requisitos_tecnicos", "Não informado"),
                tipo_oportunidade=classificacao.get("tipo_registro_minucioso", "Não informado"),
                evidencia_existencia=est.get("evidencia_existencia", "Não informado"),
                valor_orcamento_anunciado=est.get("valor_orcamento_anunciado", "Não informado"),
                valor_pagamento_comprovado=est.get("valor_pagamento_comprovado", "Não informado"),
                evidencia_pagamento=est.get("evidencia_pagamento", "Não informado"),
                status_verificacao=est.get("status_verificacao", "Não informado")
            )

    return stats

def run_coleta(
    db_path: str,
    fontes: List[Dict[str, Any]],
    mock_feeds: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Executa o pipeline de coleta para uma lista de fontes (modo simulado com mocks ou real).
    """
    inicio_iso = datetime.now().isoformat()

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO execucoes (operacao, inicio, resultado) VALUES (?, ?, ?)",
            ("coleta_rss_v3.2", inicio_iso, "em_andamento")
        )
        exec_id = cursor.lastrowid

    summary = {
        "total_noticias_analisadas": 0,
        "noticias_relevantes": 0,
        "noticias_descartadas": 0,
        "descartados_antigos": 0,
        "descartados_topico": 0,
        "em_revisao_data": 0,
        "duplicatas_detectadas": 0,
        "classificacao_A": 0,
        "classificacao_B": 0,
        "classificacao_C": 0,
        "classificacao_D": 0,
        "erros_coleta": 0,
        "detalhes_fontes": []
    }

    try:
        for fonte in fontes:
            url_feed = fonte.get("url_feed", "")
            xml_override = mock_feeds.get(url_feed) if mock_feeds else None

            res_fonte = process_feed(db_path, fonte, xml_override=xml_override)
            summary["detalhes_fontes"].append(res_fonte)

            summary["total_noticias_analisadas"] += res_fonte["total_lidos"]
            summary["noticias_relevantes"] += res_fonte["relevantes"]
            summary["noticias_descartadas"] += res_fonte["descartados"]
            summary["descartados_antigos"] += res_fonte["descartados_antigos"]
            summary["descartados_topico"] += res_fonte.get("descartados_topico", 0)
            summary["em_revisao_data"] += res_fonte["em_revisao_data"]
            summary["duplicatas_detectadas"] += res_fonte["duplicatas_url"]
            summary["classificacao_A"] += res_fonte["classificacao_A"]
            summary["classificacao_B"] += res_fonte["classificacao_B"]
            summary["classificacao_C"] += res_fonte["classificacao_C"]
            summary["classificacao_D"] += res_fonte["classificacao_D"]
            if res_fonte["erro"]:
                summary["erros_coleta"] += 1

        fim_iso = datetime.now().isoformat()
        res_final = "sucesso" if summary["erros_coleta"] == 0 else "falha"

        with get_connection(db_path) as conn:
            conn.execute(
                "UPDATE execucoes SET fim = ?, resultado = ? WHERE id = ?",
                (fim_iso, res_final, exec_id)
            )

    except Exception as e:
        fim_iso = datetime.now().isoformat()
        with get_connection(db_path) as conn:
            conn.execute(
                "UPDATE execucoes SET fim = ?, resultado = 'falha', erro = ? WHERE id = ?",
                (fim_iso, str(e), exec_id)
            )
        raise e

    return summary

def run_coleta_real_supervisionada(
    db_path: str,
    fontes: List[Dict[str, Any]],
    max_fontes: int = 5,
    max_requisicoes: int = 10,
    timeout: int = 5,
    delay_entre_req: float = 0.5
) -> Dict[str, Any]:
    """
    Modo de Coleta Real Supervisionada (Etapa 3.2).
    Aplica limites estritos de segurança (máximo 5 fontes e máximo 10 requisições HTTP)
    e executa requisições HTTP reais em páginas públicas respeitando intervalos corteses.
    """
    if len(fontes) > max_fontes:
        fontes = fontes[:max_fontes]

    fontes_executar = fontes[:max_requisicoes]
    print(f"\n[!] INICIANDO COLETA REAL SUPERVISIONADA (Limite: {len(fontes_executar)} fontes / máx {max_requisicoes} reqs HTTP)", flush=True)

    summary = run_coleta(db_path, fontes_executar, mock_feeds=None)

    time.sleep(delay_entre_req)
    return summary
