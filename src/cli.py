"""
CLI de Coleta e Publicação do RADAR RENDA IA.
Suporta Modo Simulado com Mocks, Modo Real Supervisionado e Integração com Telegram.
"""

import os
import sys
import tempfile
import argparse
from typing import Optional

from database.db import init_db, get_connection
from src.collector import run_coleta, run_coleta_real_supervisionada
from src.config import CANDIDATE_FEEDS, MAX_REAL_SOURCES, MAX_REAL_HTTP_REQUESTS
from src.telegram_bot import (
    check_telegram_connection,
    check_telegram_channel_permissions,
    send_telegram_message,
    preparar_fila_publicacao,
    get_publicacoes_pendentes,
    get_publicacoes_aprovadas,
    aprovar_publicacao,
    publicar_oportunidades_aprovadas,
    run_telegram_pipeline_round,
    run_telegram_pipeline_forced_test,
    mask_secret,
    get_telegram_config
)

MOCK_FEEDS_SIMULATION = {
    "https://hnrss.org/newest?q=AI+income+OR+agent+OR+bounty": """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>HN RSS Mock</title>
            <item>
                <title>Dataset Bounty: We are paying $50/hr for robot training video collection</title>
                <link>https://news.ycombinator.com/item?id=99001&amp;utm_source=rssfeed</link>
                <description>Embodied AI startup hiring contributors to collect kitchen task videos for robot training data.</description>
                <pubDate>Thu, 09 Oct 2026 12:00:00 GMT</pubDate>
            </item>
            <item>
                <title>Sam Altman testifies at congressional hearing regarding AI policy</title>
                <link>https://news.ycombinator.com/item?id=99002&amp;utm_source=rssfeed</link>
                <description>Bipartisan committee discusses federal AI regulations and semiconductor supply chains.</description>
                <pubDate>Thu, 09 Oct 2026 13:00:00 GMT</pubDate>
            </item>
        </channel>
    </rss>""",
    
    "https://www.tabnews.com.br/recentes/rss": """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>TabNews RSS Mock</title>
            <item>
                <title>Relato: Faturei R$ 4.500 no primeiro mês criando automações comerciais com IA e Telegram</title>
                <link>https://www.tabnews.com.br/usuario/relato-ia-automacao?ref=tabnews_rss</link>
                <description>Compartilhando minha experiência vendendo bots de suporte para e-commerce local.</description>
                <pubDate>Thu, 09 Oct 2026 14:00:00 GMT</pubDate>
            </item>
            <item>
                <title>Relato: Faturei R$ 4.500 no primeiro mês criando automações comerciais com IA e Telegram</title>
                <link>https://www.tabnews.com.br/usuario/relato-ia-automacao?ref=tabnews_rss&amp;utm_medium=email</link>
                <description>Compartilhando minha experiência vendendo bots de suporte para e-commerce local.</description>
                <pubDate>Thu, 09 Oct 2026 14:05:00 GMT</pubDate>
            </item>
        </channel>
    </rss>"""
}

def safe_str(s: str) -> str:
    """Substitui caracteres incompatíveis com o console padrão do Windows."""
    if not s:
        return ""
    return s.encode("ascii", "replace").decode("ascii")

def run_cli_telegram_check():
    print("=" * 75, flush=True)
    print("  RADAR RENDA IA - VERIFICACAO DE CONEXAO & PERMISSOES NO CANAL TELEGRAM", flush=True)
    print("=" * 75, flush=True)
    token, chat_id = get_telegram_config()
    print(f"[+] Token configurado: {mask_secret(token)}", flush=True)
    print(f"[+] Chat ID configurado: {safe_str(str(chat_id))}", flush=True)
    print("\n[ HTTP ] 1. Consultando Telegram API (getMe)...", flush=True)

    res_me = check_telegram_connection(token=token)
    if res_me.get("ok"):
        print("\n[ SUCCESS ] Conexão com o bot do Telegram estabelecida com sucesso!", flush=True)
        print(f"    - ID do Bot:     {res_me.get('id')}", flush=True)
        print(f"    - Nome do Bot:   {res_me.get('first_name')}", flush=True)
        print(f"    - Username:      @{res_me.get('username')}", flush=True)

        print("\n[ HTTP ] 2. Verificando permissões no canal (getChatMember)...", flush=True)
        res_perm = check_telegram_channel_permissions(token=token, chat_id=chat_id)
        if res_perm.get("ok"):
            status_m = res_perm.get("status_membro", "").upper()
            is_adm = res_perm.get("e_administrador")
            can_p = res_perm.get("pode_publicar")
            print(f"\n[ SUCCESS ] Status do bot no canal '{chat_id}':", flush=True)
            print(f"    - Função no canal:         {status_m}", flush=True)
            print(f"    - É Administrador?         {'SIM' if is_adm else 'NÃO'}", flush=True)
            print(f"    - Permissão para Publicar: {'SIM' if can_p else 'NÃO'}", flush=True)
        else:
            print(f"\n[ ERRO ] Não foi possível validar permissões no canal '{chat_id}':", flush=True)
            print(f"    {res_perm.get('erro')}", flush=True)
            print("    Dica: Certifique-se de que o bot @radar_renda_ia_bot foi adicionado como ADMINISTRADOR do canal com permissão para postar mensagens.", flush=True)
    else:
        print("\n[ ERRO ] Não foi possível conectar ao Telegram:", flush=True)
        print(f"    {res_me.get('erro')}", flush=True)
    print("=" * 75 + "\n", flush=True)

def run_cli_telegram_send_test():
    print("=" * 75, flush=True)
    print("  RADAR TECH OPEN SOURCE - ENVIO DE MENSAGEM DE TESTE ÚNICA (CANAL)", flush=True)
    print("=" * 75, flush=True)
    token, chat_id = get_telegram_config()
    print(f"[+] Token configurado: {mask_secret(token)}", flush=True)
    print(f"[+] Chat ID configurado: {safe_str(str(chat_id))}", flush=True)

    texto_teste = (
        "🚀 TESTE DE CONEXÃO — RADAR TECH OPEN SOURCE\n\n"
        "Bot conectado com sucesso ao canal!\n\n"
        "Em breve: notícias de tecnologia, inteligência artificial, projetos open source e novidades do GitHub."
    )

    print("\n[ HTTP ] Enviando mensagem de teste autorizada para o canal do Telegram...", flush=True)
    res = send_telegram_message(text=texto_teste, token=token, chat_id=chat_id, mock=False)

    if res.get("ok"):
        result_obj = res.get("result", {})
        chat_obj = result_obj.get("chat", {})
        print("\n[ SUCCESS ] Mensagem de teste enviada com sucesso!", flush=True)
        print(f"    - Message ID:          {res.get('message_id')}", flush=True)
        print(f"    - Chat Username/ID:    {chat_obj.get('username') or chat_obj.get('id')}", flush=True)
        print(f"    - Nome do Canal:       {chat_obj.get('title')}", flush=True)
        print("    - Status API:          OK (200)", flush=True)
    else:
        print("\n[ ERRO ] Falha ao enviar mensagem de teste:", flush=True)
        print(f"    {res.get('erro')}", flush=True)
    print("=" * 75 + "\n", flush=True)

def run_cli_telegram_pipeline_test(modo_real: bool = True):
    print("=" * 75, flush=True)
    print("  RADAR RENDA IA - TESTE FORÇADO DO PIPELINE TELEGRAM", flush=True)
    print("=" * 75, flush=True)
    db_path = "radar_renda.db"
    init_db(db_path)

    token, chat_id = get_telegram_config()
    print(f"[+] Token configurado: {mask_secret(token)}", flush=True)
    print(f"[+] Chat ID configurado: {mask_secret(chat_id)}", flush=True)

    res = run_telegram_pipeline_forced_test(db_path=db_path, modo_real=modo_real, mock_telegram=False)
    if res.get("ok"):
        print("\n[ SUCCESS ] Teste do pipeline executado e enviado com sucesso!", flush=True)
        print(f"    - Message ID: {res.get('message_id')}", flush=True)
        print(f"    - Título:     {safe_str(res.get('titulo'))}", flush=True)
        print(f"    - Classe:     {res.get('classe')}", flush=True)
        print(f"    - Score:      {res.get('score')}/100", flush=True)
    else:
        print(f"\n[ ERRO ] Falha no teste do pipeline: {res.get('erro')}", flush=True)
    print("=" * 75 + "\n", flush=True)

def run_cli_run_once_telegram(modo_real: bool = True):
    print("=" * 75, flush=True)
    print("  RADAR RENDA IA - PIPELINE AUTOMATICO COMPLETO (SINGLE RUN)", flush=True)
    print("=" * 75, flush=True)
    db_path = "radar_renda.db"
    init_db(db_path)

    token, chat_id = get_telegram_config()
    print(f"[+] Token configurado: {mask_secret(token)}", flush=True)
    print(f"[+] Chat ID configurado: {mask_secret(chat_id)}", flush=True)

    print("\n[!] INICIANDO COLETA E PROCESSAMENTO AUTOMATICO DO PIPELINE...", flush=True)
    res = run_telegram_pipeline_round(db_path=db_path, min_prioridade=0.0, modo_real=modo_real, mock_telegram=False)

    print("\n" + "-" * 65, flush=True)
    print("RESUMO DA EXECUÇÃO DO PIPELINE AUTOMÁTICO", flush=True)
    print("-" * 65, flush=True)
    print(f" Total de notícias lidas/coletadas:   {res['total_coletados']}", flush=True)
    print(f" Passaram pelos filtros:              {res['passaram_filtro']}", flush=True)
    print(f" Oportunidades Classe A/B encontradas:{res['qtd_ab']}", flush=True)
    print(f" Atingiram score mínimo (>= 0):       {res['atingiram_score']}", flush=True)
    print(f" Oportunidades enviadas ao Telegram:  {res['enviados']}", flush=True)
    print(f" Message IDs enviados:               {res['message_ids']}", flush=True)
    print(f" Ignoradas por duplicidade:           {res['ignorados_duplicidade']}", flush=True)
    print("-" * 65 + "\n", flush=True)

def run_cli_demo(modo_real: bool = False, action: str = "demo", approve_id: Optional[int] = None):
    if action == "check_telegram":
        run_cli_telegram_check()
        return
    elif action == "telegram_send_test":
        run_cli_telegram_send_test()
        return
    elif action == "telegram_pipeline_test":
        run_cli_telegram_pipeline_test(modo_real=modo_real)
        return
    elif action == "run_once_telegram":
        run_cli_run_once_telegram(modo_real=modo_real)
        return

    print("=" * 75, flush=True)
    print("  RADAR RENDA IA - RELATORIO DE COLETA & INTELIGENCIA COMERCIAL", flush=True)
    print("=" * 75, flush=True)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        init_db(db_path)
        print(f"\n[+] Banco SQLite temporario inicializado: {db_path}", flush=True)

        if modo_real:
            print("[!] INICIANDO PRIMEIRA COLETA REAL SUPERVISIONADA DE FONTES PUBLICAS...", flush=True)
            summary = run_coleta_real_supervisionada(
                db_path=db_path,
                fontes=CANDIDATE_FEEDS,
                max_fontes=MAX_REAL_SOURCES,
                max_requisicoes=MAX_REAL_HTTP_REQUESTS
            )
        else:
            print("[+] Executando em MODO SIMULADO (Mocks em memória)...", flush=True)
            summary = run_coleta(db_path, CANDIDATE_FEEDS[:2], mock_feeds=MOCK_FEEDS_SIMULATION)

        soma_parcial = (
            summary['noticias_relevantes'] +
            summary['descartados_antigos'] +
            summary.get('descartados_topico', 0) +
            summary['em_revisao_data'] +
            summary['duplicatas_detectadas']
        )
        status_reconciliacao = "100% OK" if soma_parcial == summary['total_noticias_analisadas'] else f"INCONSISTENTE ({soma_parcial} != {summary['total_noticias_analisadas']})"

        print("\n" + "-" * 65, flush=True)
        print("PAINEL DE METRICAS CONSOLIDADAS & RECONCILIACAO MATEMATICA", flush=True)
        print("-" * 65, flush=True)
        print(f" Total de notícias lidas/analisadas:      {summary['total_noticias_analisadas']}", flush=True)
        print(f"   - Relevantes (0-90 dias):              {summary['noticias_relevantes']}", flush=True)
        print(f"   - Descartadas por data (>90 dias):     {summary['descartados_antigos']}", flush=True)
        print(f"   - Descartadas por tópico irrelevante:  {summary.get('descartados_topico', 0)}", flush=True)
        print(f"   - Em revisão de data:                  {summary['em_revisao_data']}", flush=True)
        print(f"   - Duplicatas de URL descartadas:       {summary['duplicatas_detectadas']}", flush=True)
        print(f" Erros de requisição / leitura HTTP:      {summary['erros_coleta']}", flush=True)
        print(f" Status da Reconciliação Matemática:      {status_reconciliacao}", flush=True)
        print("-" * 65, flush=True)
        print(" CLASSIFICACAO COMERCIAL (Aplica-se apenas às notícias processadas):", flush=True)
        print(f"   - [A] Pagamento Documentado Auditável: {summary['classificacao_A']}", flush=True)
        print(f"   - [B] Oferta de Contratação Verificável:{summary['classificacao_B']}", flush=True)
        print(f"   - [C] Relato Não Comprovado (Fórum):  {summary['classificacao_C']}", flush=True)
        print(f"   - [D] Tendência / Especulação Tech:   {summary['classificacao_D']}", flush=True)
        print(" Nota: As categorias A/B/C/D incluem apenas notícias que passaram pelo filtro básico.", flush=True)
        print("-" * 65, flush=True)

        if action == "preview_telegram":
            novos = preparar_fila_publicacao(db_path, min_prioridade=70.0)
            pendentes = get_publicacoes_pendentes(db_path)
            print(f"\n[ TELEGRAM PREVIEW ] Fila de Moderação: {len(pendentes)} publicações pendentes ({novos} novas enfileiradas).", flush=True)
            for idx, item in enumerate(pendentes, 1):
                print("\n" + "=" * 65, flush=True)
                print(f"FILA ITEM #{item['publicacao_id']} (Notícia ID #{item['noticia_id']}) - Status: {item['status_aprovacao'].upper()}", flush=True)
                print("-" * 65, flush=True)
                print(safe_str(item["texto_preparado"]), flush=True)
                print("=" * 65, flush=True)
            print("\n[!] NENHUMA MENSAGEM FOI ENVIADA AO TELEGRAM (Modo Visualização / Dry-Run).", flush=True)

        elif action == "approve_telegram" and approve_id is not None:
            preparar_fila_publicacao(db_path, min_prioridade=70.0)
            ok = aprovar_publicacao(db_path, approve_id)
            if ok:
                print(f"\n[ SUCCESS ] Publicação ID #{approve_id} aprovada com sucesso no SQLite.", flush=True)
            else:
                print(f"\n[ ERRO ] Publicação ID #{approve_id} não encontrada na fila.", flush=True)

        elif action == "publish_telegram":
            preparar_fila_publicacao(db_path, min_prioridade=70.0)
            aprovadas = get_publicacoes_aprovadas(db_path)
            if not aprovadas:
                print("\n[!] Nenhuma publicação com status 'aprovado' encontrada na fila.", flush=True)
                print("    Dica: use --approve-telegram <ID> para aprovar uma publicação antes do envio.", flush=True)
            else:
                print(f"\n[!] PUBLICANDO {len(aprovadas)} OPORTUNIDADES APROVADAS NO TELEGRAM...", flush=True)
                res_pub = publicar_oportunidades_aprovadas(db_path)
                print(f"    - Enviadas com Sucesso: {res_pub['enviadas_sucesso']}", flush=True)
                print(f"    - Falhas de Envio:       {res_pub['falhas_envio']}", flush=True)

        else:
            print("\nOPORTUNIDADES REAIS IDENTIFICADAS NO BANCO SQLITE (Ate 5 exibidas):", flush=True)
            with get_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT n.id, n.titulo, n.data_publicacao, n.url_original, n.classificacao_comercial,
                           n.pontuacao_prioridade, n.status_novidade_br,
                           o.pais, o.empresa_pessoa, o.servico_atividade, o.quem_paga, o.valor_alegado,
                           o.tipo_evidencia, o.possibilidade_execucao_br, o.restricoes_geograficas,
                           o.forma_pagamento, o.requisitos_tecnicos, o.tipo_oportunidade, o.evidencia_existencia,
                           o.valor_orcamento_anunciado, o.valor_pagamento_comprovado, o.evidencia_pagamento, o.status_verificacao
                    FROM noticias n
                    LEFT JOIN oportunidades o ON n.id = o.noticia_id
                    WHERE n.status = 'coletado' AND n.classificacao_comercial IN ('A', 'B', 'C')
                    ORDER BY n.pontuacao_prioridade DESC
                    LIMIT 10
                    """
                )
                rows = cursor.fetchall()
                if not rows:
                    print("\n [!] Nenhuma oportunidade comercial real das classes A, B ou C foi encontrada neste lote.", flush=True)
                    print("     (As notícias coletadas foram classificadas como tendências genéricas ou notícias informativas).", flush=True)
                for idx, r in enumerate(rows, 1):
                    pode_br = "Sim" if r['possibilidade_execucao_br'] in ['alta', 'media', 'Sim'] else "Não informado"
                    print("\n" + "~" * 70, flush=True)
                    print(f"[{idx}] 1. Comprador / Contratante: {safe_str(r['quem_paga'] or r['empresa_pessoa'] or 'Não informado')}", flush=True)
                    print(f"    2. Serviço Solicitado:     {safe_str(r['servico_atividade'] or 'Não informado')}", flush=True)
                    print(f"    3. Link Original:          {safe_str(r['url_original'])}", flush=True)
                    print(f"    4. Data da Publicação:     {safe_str(r['data_publicacao'] or 'Não informado')}", flush=True)
                    print(f"    5. País:                   {safe_str(r['pais'] or 'GL')}", flush=True)
                    print(f"    6. Orçamento Anunciado:    {safe_str(r['valor_orcamento_anunciado'] or r['valor_alegado'] or 'Não informado')}", flush=True)
                    print(f"    7. Pagamento Comprovado:   {safe_str(r['valor_pagamento_comprovado'] or 'Não informado')}", flush=True)
                    print(f"    8. Evidência de Pagamento: {safe_str(r['evidencia_pagamento'] or 'Não informado')}", flush=True)
                    print(f"    9. Status Verificação:     {safe_str(r['status_verificacao'] or 'Não informado')}", flush=True)
                    print(f"   10. Forma de Pagamento:     {safe_str(r['forma_pagamento'] or 'Não informado')}", flush=True)
                    print(f"   11. Aceita Brasileiros?     {pode_br} ({safe_str(r['restricoes_geograficas'] or 'Não informado')})", flush=True)
                    print(f"   12. Requisitos Técnicos:    {safe_str(r['requisitos_tecnicos'] or 'Não informado')}", flush=True)
                    print(f"   13. Tipo de Oportunidade:   {safe_str(r['tipo_oportunidade'] or 'Não informado')}", flush=True)
                    print(f"   14. Evidência de Existência:{safe_str(r['evidencia_existencia'] or 'Não informado')}", flush=True)
                    print(f"   15. Classificação:          Classe [{r['classificacao_comercial']}] (Prioridade: {r['pontuacao_prioridade']}/100)", flush=True)
                    print("~" * 70, flush=True)

        print("\n" + "=" * 75, flush=True)
        print(" Coleta e processamento concluídos com sucesso.", flush=True)
        print("=" * 75 + "\n", flush=True)

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI Radar Renda IA - Coleta Real Supervisionada & Telegram Integration")
    parser.add_argument("--real", action="store_true", help="Executa em modo real supervisionado (máx 5 fontes, máx 10 reqs HTTP)")
    parser.add_argument("--check-telegram", action="store_true", help="Verifica a conexão com a API do Telegram (getMe)")
    parser.add_argument("--preview-telegram", action="store_true", help="Exibe a visualização (dry-run) das mensagens preparadas para o Telegram")
    parser.add_argument("--approve-telegram", type=int, help="Aprova uma publicação específica na fila por ID")
    parser.add_argument("--telegram-send-test", action="store_true", help="Envia mensagem de teste única autorizada para o chat do Telegram")
    parser.add_argument("--publish-telegram", action="store_true", help="Envia publicações aprovadas para o Telegram (requer credenciais)")
    parser.add_argument("--run-once-telegram", action="store_true", help="Executa uma rodada completa do pipeline automático e publica oportunidades A/B válidas no Telegram")
    parser.add_argument("--telegram-pipeline-test", action="store_true", help="Executa um envio forçado de teste do pipeline com 1 oportunidade Classe B formatada")
    args = parser.parse_args()

    if args.check_telegram:
        run_cli_demo(action="check_telegram")
    elif args.telegram_send_test:
        run_cli_demo(action="telegram_send_test")
    elif args.telegram_pipeline_test:
        run_cli_demo(modo_real=args.real, action="telegram_pipeline_test")
    elif args.run_once_telegram:
        run_cli_demo(modo_real=args.real, action="run_once_telegram")
    elif args.preview_telegram:
        run_cli_demo(modo_real=args.real, action="preview_telegram")
    elif args.approve_telegram is not None:
        run_cli_demo(modo_real=args.real, action="approve_telegram", approve_id=args.approve_telegram)
    elif args.publish_telegram:
        run_cli_demo(modo_real=args.real, action="publish_telegram")
    else:
        run_cli_demo(modo_real=args.real)

