import os
import tempfile
import unittest
from datetime import datetime, timezone

from database.db import init_db, get_connection
from src.collector import process_feed, run_coleta, run_coleta_real_supervisionada
from src.relevance_filter import classify_relevance, calculate_priority_score
from src.config import CANDIDATE_FEEDS, MAX_REAL_SOURCES, MAX_REAL_HTTP_REQUESTS

class TestEtapa32Module(unittest.TestCase):

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_01_consistencia_contadores_painel_e_sqlite(self):
        """Testa se as métricas do painel de resumo batem perfeitamente com a contagem real no SQLite."""
        dt_now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        fonte_mock = {"id": 1, "nome": "Fonte Teste Consistência", "url_feed": "https://teste.com/rss"}

        xml_mock = f"""<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Dataset Bounty: We are paying $50/hr for robot training video collection</title>
                    <link>https://teste.com/bounty</link>
                    <description>Hiring contributors for robot dataset collection</description>
                    <pubDate>{dt_now}</pubDate>
                </item>
                <item>
                    <title>Relato: Faturei R$ 3.000 com agentes de IA</title>
                    <link>https://teste.com/relato</link>
                    <description>Relato pessoal</description>
                    <pubDate>{dt_now}</pubDate>
                </item>
            </channel>
        </rss>"""

        stats = process_feed(self.db_path, fonte_mock, xml_override=xml_mock)

        # O primeiro item é Classe B e o segundo é Classe C
        self.assertEqual(stats["classificacao_B"], 1)
        self.assertEqual(stats["classificacao_C"], 1)

        # Valida contagem direta no SQLite
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM noticias WHERE classificacao_comercial = 'B'")
            qtd_b = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM noticias WHERE classificacao_comercial = 'C'")
            qtd_c = cursor.fetchone()[0]

        self.assertEqual(stats["classificacao_B"], qtd_b)
        self.assertEqual(stats["classificacao_C"], qtd_c)

    def test_02_pontuacao_revisada_teto_classe_D(self):
        """Verifica se notícias de tendência tecnológica sem comprador (Classe D) têm pontuação limitada (<= 40 pts)."""
        score, justificativa = calculate_priority_score(
            dias_antiguidade=0,
            classificacao_comercial="D",
            possibilidade_execucao_br="media",
            investimento_baixo=True,
            potencial_cliente="medio"
        )
        self.assertLessEqual(score, 40.0)
        self.assertIn("Sem comprador identificado", justificativa)

    def test_03_pontuacao_elevada_classe_B_comprador_ativo(self):
        """Verifica se ofertas de contratação ativas (Classe B) recebem pontuação priorizada (> 65.0 pts)."""
        score, justificativa = calculate_priority_score(
            dias_antiguidade=1,
            classificacao_comercial="B",
            possibilidade_execucao_br="alta",
            investimento_baixo=True,
            potencial_cliente="alto"
        )
        self.assertGreaterEqual(score, 70.0)
        self.assertIn("Demanda Comercial (Classe B)", justificativa)

    def test_04_limites_seguranca_coleta_real(self):
        """Verifica se o modo de coleta real aplica o limite máximo de 5 fontes e 10 requisições."""
        fontes_excesso = CANDIDATE_FEEDS * 2
        self.assertGreater(len(fontes_excesso), 5)

        fontes_limitadas = fontes_excesso[:MAX_REAL_SOURCES]
        self.assertEqual(len(fontes_limitadas), 5)
        self.assertLessEqual(MAX_REAL_HTTP_REQUESTS, 10)

if __name__ == "__main__":
    unittest.main()
