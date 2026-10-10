import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from database.db import init_db, get_connection, get_noticia_by_id
from src.collector import process_feed, parse_rss_content
from src.relevance_filter import classify_relevance, evaluate_recency, calculate_priority_score

class TestEtapa31Module(unittest.TestCase):

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_01_noticia_10_dias_aceita(self):
        """Verifica se notícia com 10 dias de publicação é aceita como recente."""
        dt_10d = datetime.now(timezone.utc) - timedelta(days=10)
        rfc_date = dt_10d.strftime("%a, %d %b %Y %H:%M:%S GMT")
        res = evaluate_recency(rfc_date, cutoff_days=90)
        self.assertTrue(res["aprovado"])
        self.assertEqual(res["status_tempo"], "recentemente_publicado")
        self.assertLessEqual(res["dias_antiguidade"], 11)

    def test_02_noticia_89_dias_aceita(self):
        """Verifica se notícia com 89 dias de publicação é aceita como recente."""
        dt_89d = datetime.now(timezone.utc) - timedelta(days=89)
        rfc_date = dt_89d.strftime("%a, %d %b %Y %H:%M:%S GMT")
        res = evaluate_recency(rfc_date, cutoff_days=90)
        self.assertTrue(res["aprovado"])
        self.assertEqual(res["status_tempo"], "recentemente_publicado")

    def test_03_noticia_91_dias_rejeitada_como_antiga(self):
        """Verifica se notícia com 91 dias de publicação é descartada como antiga."""
        dt_91d = datetime.now(timezone.utc) - timedelta(days=91)
        rfc_date = dt_91d.strftime("%a, %d %b %Y %H:%M:%S GMT")
        res = evaluate_recency(rfc_date, cutoff_days=90)
        self.assertFalse(res["aprovado"])
        self.assertEqual(res["status_tempo"], "descartado_antigo")

    def test_04_noticia_sem_data_colocada_em_revisao(self):
        """Verifica se notícia sem data verificável entra em revisão de data."""
        res = evaluate_recency("", cutoff_days=90)
        self.assertFalse(res["aprovado"])
        self.assertEqual(res["status_tempo"], "em_revisao_data")

    def test_05_noticia_antiga_republicada_descartada(self):
        """Verifica se republicação de notícia de 100 dias é descartada no filtro temporal."""
        dt_100d = datetime.now(timezone.utc) - timedelta(days=100)
        date_str = dt_100d.strftime("%a, %d %b %Y %H:%M:%S GMT")

        res = classify_relevance(
            titulo="Nova republicação sobre agente de IA antigo",
            resumo="Revisitando modelo de automação comercial de 2025",
            date_str=date_str
        )
        self.assertFalse(res["is_relevant"])
        self.assertEqual(res["status_tempo"], "descartado_antigo")

    def test_06_oferta_empresa_coleta_dados_robotica_classe_B(self):
        """Testa oferta verificável de contratação para coleta de dados de robótica (Classe B)."""
        dt_now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        res = classify_relevance(
            titulo="We are paying $50/hr for robot training video collection dataset bounty",
            resumo="Embodied AI startup hiring remote contributors to collect kitchen video dataset",
            date_str=dt_now
        )
        self.assertTrue(res["is_relevant"])
        self.assertEqual(res["classificacao_comercial"], "B")
        self.assertGreater(res["pontuacao_prioridade"], 50.0)

    def test_07_relato_faturamento_nao_comprovado_classe_C(self):
        """Testa relato individual de faturamento em fórum sem prova auditada (Classe C)."""
        dt_now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        res = classify_relevance(
            titulo="Relato: Faturei R$ 5.000 criando bots de vendas com IA",
            resumo="Depoimento pessoal sobre ganhos como freelancer de automação",
            date_str=dt_now
        )
        self.assertTrue(res["is_relevant"])
        self.assertEqual(res["classificacao_comercial"], "C")

    def test_08_conteudo_chines_simplificado(self):
        """Testa filtro de relevância em Chinês Simplificado (zh-CN) para 具身智能 e 数据集付费."""
        dt_now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        res = classify_relevance(
            titulo="具身智能机器人训练：数据集付费采集与标注兼职收益",
            resumo="商业自动化与开源AI工具开发，赚取外汇与首批付费客户",
            date_str=dt_now
        )
        self.assertTrue(res["is_relevant"])
        self.assertIn("具身智能", res["keywords_encontradas"])
        self.assertEqual(res["estruturado"]["pais"], "CN")

    def test_09_restricoes_trabalho_eua_pontuacao_zerada(self):
        """Garante que restrições geográficas (SSN Required) zera o critério de facilidade no BR no score."""
        score, _ = calculate_priority_score(
            dias_antiguidade=5,
            classificacao_comercial="B",
            possibilidade_execucao_br="alta",
            investimento_baixo=True,
            potencial_cliente="alto",
            restricoes_geograficas="US Resident Only / SSN Required"
        )
        self.assertLess(score, 85.0)

    def test_10_oportunidade_sem_evidencia_remuneracao_classe_D(self):
        """Notícia de tendência tecnológica no GitHub sem monetização demonstrada (Classe D)."""
        dt_now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        res = classify_relevance(
            titulo="Novo modelo de linguagem open source lançado no GitHub",
            resumo="Discussão técnica de arquitetura sem proposta comercial",
            date_str=dt_now
        )
        self.assertFalse(res["is_relevant"])
        self.assertEqual(res["classificacao_comercial"], "D")

if __name__ == "__main__":
    unittest.main()
