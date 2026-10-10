import os
import tempfile
import unittest
from datetime import datetime, timezone

from database.db import init_db, get_connection
from src.collector import parse_rss_content, process_feed, run_coleta, fetch_feed_url
from src.relevance_filter import classify_relevance

class TestCollectorModule(unittest.TestCase):

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_01_parse_rss_valido(self):
        """Testa o parsing de um XML RSS 2.0 válido em memória."""
        xml_valido = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Blog de IA Fictício</title>
                <item>
                    <title>Como faturei R$ 2.000 criando agentes de IA com Python</title>
                    <link>https://blog.ficticio.com/agentes-ia?utm_source=rss</link>
                    <description>Relato de experiência e modelo de receita comercial.</description>
                    <pubDate>Thu, 09 Oct 2026 10:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""

        items = parse_rss_content(xml_valido, "Blog Fictício")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["titulo"], "Como faturei R$ 2.000 criando agentes de IA com Python")
        self.assertEqual(items[0]["link"], "https://blog.ficticio.com/agentes-ia?utm_source=rss")

    def test_02_parse_feed_vazio(self):
        """Testa o comportamento ao processar feed RSS sem itens."""
        xml_vazio = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Vazio</title></channel></rss>"""
        items = parse_rss_content(xml_vazio, "Fonte Vazia")
        self.assertEqual(len(items), 0)

    def test_03_parse_rss_malformado(self):
        """Verifica se XML malformado gera exceção de parsing amigável."""
        xml_invalido = "<html><body>Não é XML de RSS válido</body></html>"
        with self.assertRaises(ValueError):
            parse_rss_content(xml_invalido, "Fonte Inválida")

    def test_04_tratamento_timeout_e_erro_url(self):
        """Simula falha de conexão / timeout em URL inexistente."""
        content, error = fetch_feed_url("http://127.0.0.1:59999/feed.xml", timeout=1)
        self.assertIsNone(content)
        self.assertIsNotNone(error)
        self.assertTrue("Erro" in error or "Timeout" in error or "Conexão" in error)

    def test_05_filtro_relevancia_pt_e_en(self):
        """Testa a classificação de relevância em conteúdos em Português e Inglês."""
        dt_now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        c1 = classify_relevance("Faturei R$ 3.500 no primeiro mês com automação de IA", "Relato no fórum.", date_str=dt_now)
        self.assertTrue(c1["is_relevant"])
        self.assertEqual(c1["categoria"], "relato_receita")

        c2 = classify_relevance("How I made $5,000/month selling AI agents to small businesses", "Case study.", date_str=dt_now)
        self.assertTrue(c2["is_relevant"])
        self.assertEqual(c2["categoria"], "relato_receita")

        c3 = classify_relevance("Novo agente de IA open-source para automação comercial", "Projeto GitHub.", date_str=dt_now)
        self.assertFalse(c3["is_relevant"])

        c4 = classify_relevance("Sam Altman testifies at congressional hearing regarding AI policy", "US Congress hearing.", date_str=dt_now)
        self.assertFalse(c4["is_relevant"])
        self.assertEqual(c4["categoria"], "irrelevante_generico")

    def test_06_pipeline_coleta_simulado_persistencia_sqlite(self):
        """Testa o pipeline completo de coleta com feed mockado e persistência no SQLite."""
        fonte_mock = {
            "id": 1,
            "nome": "Fonte Mock Teste",
            "url_feed": "https://exemplo-ficticio.com/rss.xml"
        }
        dt_now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        xml_mock = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Feed Teste</title>
                <item>
                    <title>Relato: Ganhei R$ 1.500 criando bots Telegram com IA</title>
                    <link>https://exemplo-ficticio.com/post-1?utm_source=rss</link>
                    <description>Relato de ganhos reais com venda de agentes de IA.</description>
                    <pubDate>{dt_now}</pubDate>
                </item>
                <item>
                    <title>Notícia Política de IA sem relação com vendas</title>
                    <link>https://exemplo-ficticio.com/post-2?utm_source=rss</link>
                    <description>Discussão legislativa sobre regulação.</description>
                    <pubDate>{dt_now}</pubDate>
                </item>
            </channel>
        </rss>"""

        stats = process_feed(self.db_path, fonte_mock, xml_override=xml_mock)
        self.assertEqual(stats["total_lidos"], 2)
        self.assertEqual(stats["relevantes"], 1)
        self.assertEqual(stats["descartados"], 1)

        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT titulo, status FROM noticias ORDER BY id ASC")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["status"], "coletado")
            self.assertEqual(rows[1]["status"], "rejeitado")

    def test_07_run_coleta_e_historico_execucoes(self):
        """Testa a execução do run_coleta com gravação na tabela execucoes."""
        dt_now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        fontes = [
            {"id": 1, "nome": "Fonte A", "url_feed": "https://fonte-a.com/rss"},
            {"id": 2, "nome": "Fonte B", "url_feed": "https://fonte-b.com/rss"}
        ]

        mocks = {
            "https://fonte-a.com/rss": f"""<?xml version="1.0"?><rss version="2.0"><channel><item><title>Made $1k selling AI service</title><link>https://fonte-a.com/post1</link><description>MRR report</description><pubDate>{dt_now}</pubDate></item></channel></rss>""",
            "https://fonte-b.com/rss": f"""<?xml version="1.0"?><rss version="2.0"><channel><item><title>NVIDIA stock market report</title><link>https://fonte-b.com/post2</link><description>Financial market</description><pubDate>{dt_now}</pubDate></item></channel></rss>"""
        }

        summary = run_coleta(self.db_path, fontes, mock_feeds=mocks)
        self.assertEqual(summary["total_noticias_analisadas"], 2)
        self.assertEqual(summary["noticias_relevantes"], 1)
        self.assertEqual(summary["noticias_descartadas"], 1)
        self.assertEqual(summary["erros_coleta"], 0)

        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT operacao, resultado FROM execucoes WHERE operacao LIKE 'coleta_rss%'")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["resultado"], "sucesso")

if __name__ == "__main__":
    unittest.main()
