"""
Suíte de testes obrigatória para a Etapa 3.4.1 — Validação Semântica de Demanda.
Garante a rejeição estrita de candidaturas/ofertas de vendedores e classificação precisa A/B/C/D.
"""

import unittest
from src.relevance_filter import (
    analyze_semantic_demand,
    determine_commercial_classification,
    classify_relevance
)

class TestEtapa341SemanticDemandValidation(unittest.TestCase):

    def test_chinese_job_seeker_post(self):
        """1. Teste do falso positivo crítico: '后端工程师求职' (Engenheiro backend procurando emprego)."""
        titulo = "后端工程师求职"
        resumo = "5年Python经验，寻找远程或全职工作机会"
        
        info = analyze_semantic_demand(titulo, resumo)
        self.assertTrue(info["candidate_post"], "Postagem com '求职' deve ser identificada como candidate_post = True")
        self.assertFalse(info["buyer_present"], "Postagem de candidato não possui comprador/contratante (buyer_present = False)")
        self.assertFalse(info["hiring_intent"], "Postagem de candidato não possui intenção de contratação (hiring_intent = False)")

        res = classify_relevance(titulo, resumo)
        self.assertFalse(res["is_relevant"], "Postagem de candidato deve ser rejeitada pelo filtro (is_relevant = False)")
        self.assertEqual(res["classificacao_comercial"], "D", "Postagem de candidato deve ser classificada estritamente como Classe D")

    def test_english_job_seeker_post(self):
        """2. Teste de candidatura em inglês: 'Looking for work as an AI engineer' -> Classe D."""
        titulo = "Looking for work as an AI engineer"
        resumo = "Experienced Python developer available for full-time or contract roles."

        info = analyze_semantic_demand(titulo, resumo)
        self.assertTrue(info["candidate_post"])
        self.assertFalse(info["buyer_present"])
        self.assertFalse(info["hiring_intent"])

        res = classify_relevance(titulo, resumo)
        self.assertFalse(res["is_relevant"])
        self.assertEqual(res["classificacao_comercial"], "D")

    def test_freelance_offer_post(self):
        """3. Teste de oferta de freelancer: 'Available for freelance AI automation projects' -> Classe D."""
        titulo = "Available for freelance AI automation projects"
        resumo = "I build n8n workflows and custom LLM bots for businesses."

        info = analyze_semantic_demand(titulo, resumo)
        self.assertTrue(info["candidate_post"] or info["seller_present"])
        self.assertFalse(info["buyer_present"])
        self.assertFalse(info["hiring_intent"])

        res = classify_relevance(titulo, resumo)
        self.assertFalse(res["is_relevant"])
        self.assertEqual(res["classificacao_comercial"], "D")

    def test_buyer_hiring_post_b(self):
        """4. Teste de contratante legítimo sem preço explícito: 'Hiring a Python developer to build an AI agent' -> Classe B."""
        titulo = "Hiring a Python developer to build an AI agent"
        resumo = "Scale AI startup looking for an engineer to build custom automation agents."

        info = analyze_semantic_demand(titulo, resumo, url_fonte="https://scale.com/jobs")
        self.assertFalse(info["candidate_post"])
        self.assertTrue(info["buyer_present"])
        self.assertTrue(info["hiring_intent"])

        res = classify_relevance(titulo, resumo)
        self.assertTrue(res["is_relevant"])
        self.assertEqual(res["classificacao_comercial"], "B")

    def test_buyer_hiring_post_budget_is_class_b(self):
        """5. Anúncio com orçamento anunciado: 'Looking for someone to automate support. Budget $500' -> Classe B."""
        titulo = "Looking for someone to automate our customer support. Budget $500"
        resumo = "We are hiring a freelancer to connect ChatGPT to our CRM. Paying $500 upon completion."

        info = analyze_semantic_demand(titulo, resumo)
        self.assertFalse(info["candidate_post"])
        self.assertTrue(info["buyer_present"])
        self.assertTrue(info["hiring_intent"])
        self.assertNotEqual(info["payment_explicit"], "Não informado")
        self.assertIn("$500", info["payment_explicit"])

        res = classify_relevance(titulo, resumo)
        self.assertTrue(res["is_relevant"])
        self.assertEqual(res["classificacao_comercial"], "B", "Orçamento anunciado em anúncio não comprova pagamento realizado, devendo ser Classe B.")
        self.assertEqual(res["estruturado"]["valor_orcamento_anunciado"], "$500")
        self.assertEqual(res["estruturado"]["valor_pagamento_comprovado"], "Não informado")

    def test_buyer_audited_payout_class_a(self):
        """6. Pagamento efetivamente comprovado/auditado -> Classe A."""
        titulo = "Scale AI audited report: $5,000 payout confirmed for robot dataset bounty"
        resumo = "Contrato público auditado confirmando o pagamento de $5,000 aos colaboradores."

        res = classify_relevance(titulo, resumo)
        self.assertTrue(res["is_relevant"])
        self.assertEqual(res["classificacao_comercial"], "A", "Pagamento auditado/comprovado deve ser Classe A.")
        self.assertEqual(res["estruturado"]["valor_pagamento_comprovado"], "$5,000")

    def test_non_inferred_fields_default_to_nao_informado(self):
        """6. Teste de Proibição de Inferências: Campos omitidos devem ser 'Não informado'."""
        titulo = "Hiring a Python developer to build an AI agent"
        resumo = "Looking for an engineer."

        info = analyze_semantic_demand(titulo, resumo)
        self.assertEqual(info["payment_explicit"], "Não informado")
        self.assertEqual(info["remote_explicit"], "Não informado")
        self.assertEqual(info["brazil_eligible_explicit"], "Não informado")

if __name__ == "__main__":
    unittest.main()
