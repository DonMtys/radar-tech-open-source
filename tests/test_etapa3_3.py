"""
Suíte de testes de unidade para a Etapa 3.3 — Descoberta de Compradores e Demanda Comercial.
Valida reconciliação de métricas, catálogo de fontes comerciais, evidência estrita e categorização.
"""

import unittest
import tempfile
import os
from datetime import datetime, timezone, timedelta

from database.db import init_db
from src.collector import run_coleta
from src.commercial_sources import (
    get_candidate_commercial_sources,
    search_candidate_sources_by_country,
    search_candidate_sources_by_theme,
    COMMERCIAL_SEARCH_THEMES
)
from src.relevance_filter import (
    classify_relevance,
    determine_commercial_classification,
    categorize_record_type,
    evaluate_recency
)

class TestEtapa33CommercialDiscovery(unittest.TestCase):

    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp_file.name
        self.tmp_file.close()
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_metrics_reconciliation_math(self):
        """1. Teste de Reconciliação Matemática de Métricas de Coleta."""
        dt_recent = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        dt_old = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%a, %d %b %Y %H:%M:%S GMT")

        xml_mock = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Mock Feed Reconciliação</title>
                <!-- Item 1: Relevante recente -->
                <item>
                    <title>Scale AI dataset bounty for robot training video collection</title>
                    <link>https://example.com/item1</link>
                    <description>We are paying $50 for egocentric video collection.</description>
                    <pubDate>{dt_recent}</pubDate>
                </item>
                <!-- Item 2: Relevante recente relato -->
                <item>
                    <title>Relato: Faturei R$ 5.000 com agentes de IA e automação commercial</title>
                    <link>https://example.com/item2</link>
                    <description>Primeiros clientes conquistados no Brasil.</description>
                    <pubDate>{dt_recent}</pubDate>
                </item>
                <!-- Item 3: Antigo (>90d) -->
                <item>
                    <title>Robot training dataset bounty released long ago</title>
                    <link>https://example.com/item3</link>
                    <description>Old dataset release</description>
                    <pubDate>{dt_old}</pubDate>
                </item>
                <!-- Item 4: Tópico Irrelevante recente -->
                <item>
                    <title>Sam Altman testifies at congress about semiconductor factories</title>
                    <link>https://example.com/item4</link>
                    <description>Bipartisan bill discussed</description>
                    <pubDate>{dt_recent}</pubDate>
                </item>
                <!-- Item 5: Duplicata de URL -->
                <item>
                    <title>Scale AI dataset bounty for robot training video collection</title>
                    <link>https://example.com/item1?utm_source=rss</link>
                    <description>We are paying $50 for egocentric video collection.</description>
                    <pubDate>{dt_recent}</pubDate>
                </item>
            </channel>
        </rss>"""

        fontes = [{"nome": "Fonte Teste", "url_feed": "https://example.com/feed.xml"}]
        summary = run_coleta(self.db_path, fontes, mock_feeds={"https://example.com/feed.xml": xml_mock})

        total = summary["total_noticias_analisadas"]
        relevantes = summary["noticias_relevantes"]
        antigos = summary["descartados_antigos"]
        topico = summary["descartados_topico"]
        duplicatas = summary["duplicatas_detectadas"]
        revisao = summary["em_revisao_data"]

        # Reconciliação exata: Total == Relevantes + Antigos + Tópico Irrelevante + Duplicatas + Revisão
        soma_subtotais = relevantes + antigos + topico + duplicatas + revisao
        self.assertEqual(total, 5, "Total de itens lidos deve ser exatamente 5.")
        self.assertEqual(soma_subtotais, total, f"Reconciliação falhou: {soma_subtotais} != {total}")
        self.assertEqual(relevantes, 2)
        self.assertEqual(antigos, 1)
        self.assertEqual(topico, 1)
        self.assertEqual(duplicatas, 1)

    def test_candidate_commercial_sources_catalog(self):
        """2. Teste do Módulo de Fontes Comerciais Candidatas."""
        sources = get_candidate_commercial_sources()
        self.assertGreaterEqual(len(sources), 4, "Deve catalogar pelo menos 4 fontes comerciais candidatas.")

        for s in sources:
            self.assertIn("id", s)
            self.assertIn("nome", s)
            self.assertIn("pais", s)
            self.assertIn("categoria", s)
            self.assertIn("url", s)
            self.assertIn("metodo_acesso", s)
            self.assertIn("justificativa_comercial", s)
            self.assertIn("restricao_brasileiros", s)
            self.assertFalse(s["autenticacao_necessaria"], "Todas as fontes candidatas devem ser públicas sem login.")

        # Teste de busca por tema e país
        us_sources = search_candidate_sources_by_country("US")
        cn_sources = search_candidate_sources_by_country("CN")
        self.assertTrue(any(s["pais"] == "US" for s in us_sources))
        self.assertTrue(any(s["pais"] == "CN" for s in cn_sources))

        robot_sources = search_candidate_sources_by_theme("Robot training video collection paid")
        self.assertTrue(len(robot_sources) > 0)

        chinese_robot_sources = search_candidate_sources_by_theme("具身智能 数据采集 招募")
        self.assertTrue(len(chinese_robot_sources) > 0)

    def test_strict_commercial_evidence_rule7(self):
        """3. Teste de Rigor na Evidência Comercial (Regra 7)."""
        # Frase genérica sem comprador nem link verificado -> Deve ser C ou D, NÃO Classe B
        class_fake = determine_commercial_classification("we are paying $100 for random tasks", tem_link_original=False)
        self.assertIn(class_fake, ["C", "D"], "Anúncio sem comprador ou link legítimo não pode ser Classe B.")

        # Anúncio verificado com comprador conhecido (Scale AI / V2EX) -> Classe B
        class_real = determine_commercial_classification(
            "Scale AI dataset bounty: hiring contributors for robot training video collection",
            url_fonte="https://scale.com/jobs",
            tem_link_original=True
        )
        self.assertEqual(class_real, "B", "Oferta com comprador ativo conhecido e link original deve ser Classe B.")

    def test_fine_grained_record_type_categorization(self):
        """4. Teste de Categorização dos 6 Tipos de Registro."""
        # 1. noticia_tecnologica
        t1 = categorize_record_type("Nvidia lança novo chip para inteligência artificial", "D")
        self.assertEqual(t1, "noticia_tecnologica")

        # 2. oferta_contratacao
        t2 = categorize_record_type("Hiring bounty: contratando desenvolvedor de agente de IA", "B")
        self.assertEqual(t2, "oferta_contratacao")

        # 3. programa_remuneracao
        t3 = categorize_record_type("Scale AI video collection dataset bounty remunerado", "B")
        self.assertEqual(t3, "programa_remuneracao")

        # 4. relato_pessoal_faturamento
        t4 = categorize_record_type("Relato: Faturei R$ 10.000 em um mês com automação", "C")
        self.assertEqual(t4, "relato_pessoal_faturamento")

        # 5. servico_comprador_identificado
        t5 = categorize_record_type("Conquistei meu primeiro cliente corporativo vendendo bot de IA", "C")
        self.assertEqual(t5, "servico_comprador_identificado")

        # 6. hipotese_comercial
        t6 = categorize_record_type("Ideia de Micro-SaaS e como monetizar com IA", "D")
        self.assertEqual(t6, "hipotese_comercial")

    def test_geographic_restrictions_for_brazilians(self):
        """5. Teste de Restrições Geográficas para Brasileiros."""
        res_ssn = classify_relevance(
            "US Resident Only - SSN Required for AI video collection paid project",
            "We are paying $100/hr for dataset collection but SSN required."
        )
        self.assertEqual(res_ssn["estruturado"]["possibilidade_execucao_br"], "baixa")
        self.assertIn("US Only", res_ssn["estruturado"]["restricoes_geograficas"])

        res_global = classify_relevance(
            "Global remote dataset bounty for robot training video collection",
            "Paying via Wise / PayPal to global contributors."
        )
        self.assertEqual(res_global["estruturado"]["possibilidade_execucao_br"], "alta")

    def test_old_opportunity_rejection(self):
        """6. Teste de Rejeição de Oportunidades Antigas (>90 dias)."""
        date_100d = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        res_old = classify_relevance(
            "Scale AI dataset bounty for robot training video collection",
            "We are paying $50 for video collection.",
            date_str=date_100d
        )
        self.assertFalse(res_old["is_relevant"])
        self.assertEqual(res_old["status_tempo"], "descartado_antigo")

if __name__ == "__main__":
    unittest.main()
