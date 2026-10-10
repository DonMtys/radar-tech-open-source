"""
Módulo de Descoberta de Projetos Open Source para o RADAR OPEN SOURCE & TECH.
Utiliza APIs públicas gratuitas do GitHub REST API sem requerer chaves pagas.
Diferencia repositórios em crescimento recente (Breakout/Ascensão) de repositórios populares consolidados.
Extrai informações completas com data verificável, link original, estrelas, funcionalidades e aplicações práticas em PT-BR.
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

def fetch_github_trending_repos(
    categoria: str = "ascensao", # "ascensao" ou "popular"
    days_back: int = 30,
    max_results: int = 10,
    github_token: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Busca repositórios no GitHub utilizando a API pública gratuita.
    - Se categoria == 'ascensao': projetos criados nos últimos `days_back` dias que ganharam tração rápida (stars entre 10 e 2000).
    - Se categoria == 'popular': projetos populares consolidados com mais de 2000 estrelas e atualização recente.
    """
    date_cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    if categoria == "ascensao":
        query = f"created:>{date_cutoff} stars:10..2000"
    else:
        query = f"pushed:>{date_cutoff} stars:>2000"

    url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page={max_results}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RadarOpenSourceBot/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    repos = []
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            items = data.get("items", [])
            for item in items:
                stars = item.get("stargazers_count", 0)
                is_ascensao = stars < 2000 and (categoria == "ascensao")
                cat_tipo = "open_source_ascensao" if is_ascensao else "open_source_popular"

                created_at_str = item.get("created_at", "")
                if created_at_str and "T" in created_at_str:
                    data_formatada = created_at_str.split("T")[0]
                else:
                    data_formatada = created_at_str or "Não informada"

                repo_info = {
                    "id": item.get("id"),
                    "nome": item.get("name"),
                    "nome_completo": item.get("full_name"),
                    "autor": item.get("owner", {}).get("login", "Não informado"),
                    "url_original": item.get("html_url"),
                    "descricao_original": item.get("description") or "Sem descrição fornecida.",
                    "estrelas": stars,
                    "linguagem": item.get("language") or "Multilingue",
                    "topicos": item.get("topics", []),
                    "data_publicacao": data_formatada,
                    "data_criacao": created_at_str,
                    "data_atualizacao": item.get("updated_at"),
                    "licenca": item.get("license", {}).get("spdx_id") if item.get("license") else "Não informada",
                    "categoria_open_source": cat_tipo,
                    "fonte_nome": "GitHub REST API Pública",
                    "pais": "US/GL"
                }
                repos.append(repo_info)
    except Exception as e:
        print(f"[!] Erro ao buscar repositórios no GitHub API ({categoria}): {e}", flush=True)

    return repos

def traduzir_e_explicar_repositorio(repo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gera uma explicação em Português Brasileiro (PT-BR) sobre as funcionalidades
    e aplicações práticas do repositório Open Source.
    Diferencia 'Projeto em Ascensão' de 'Projeto Popular Consolidado'.
    """
    nome = repo.get("nome_completo", repo.get("nome"))
    desc_orig = repo.get("descricao_original", "")
    ling = repo.get("linguagem", "Tech")
    stars = repo.get("estrelas", 0)
    cat_tipo = repo.get("categoria_open_source", "open_source_ascensao")
    topicos = ", ".join(repo.get("topicos", [])[:5]) or "Open Source"

    if cat_tipo == "open_source_ascensao":
        prefixo_titulo = "🚀 OPEN SOURCE EM ASCENSÃO"
        contexto_categoria = "em rápido crescimento recente"
    else:
        prefixo_titulo = "⭐ PROJETO POPULAR CONSOLIDADO"
        contexto_categoria = "popular e consolidado na comunidade"

    resumo_pt = (
        f"Projeto open source {contexto_categoria}, desenvolvido em {ling} com {stars} estrelas no GitHub. "
        f"Descrição principal: {desc_orig}"
    )

    aplicacao_pratica = (
        f"Excelente opção para desenvolvedores e equipes de engenharia trabalhando com {ling} e {topicos}. "
        f"Permite acelerar a criação de produtos, soluções automatizadas e sistemas de alta performance."
    )

    return {
        "titulo_pt": f"{prefixo_titulo}: {nome} ({stars}⭐)",
        "resumo_pt": resumo_pt,
        "funcionalidades": desc_orig,
        "aplicacao_pratica": aplicacao_pratica,
        "linguagem": ling,
        "estrelas": stars,
        "topicos": topicos,
        "categoria_open_source": cat_tipo
    }
