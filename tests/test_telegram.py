"""
Suíte de testes automatizados para a integração com a API do Telegram.
Valida autenticação segura via .env, formatação de mensagens, controle de fila no SQLite,
prevenção de duplicatas e fluxo de aprovação usando simulações (mocks) sem envios reais.
"""

import os
import tempfile
import unittest
from datetime import datetime, timezone

from database.db import init_db, get_connection, add_fonte, add_noticia, add_oportunidade
from src.telegram_bot import (
    load_env_file,
    mask_secret,
    format_telegram_message,
    send_telegram_message,
    check_telegram_connection,
    preparar_fila_publicacao,
    get_publicacoes_pendentes,
    get_publicacoes_aprovadas,
    aprovar_publicacao,
    rejeitar_publicacao,
    publicar_oportunidades_aprovadas
)

class TestTelegramBotIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp_file.name
        self.tmp_file.close()
        init_db(self.db_path)
        self.fonte_id = add_fonte(self.db_path, "Fonte Teste", "https://example.com/rss")

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_mask_secret(self):
        """1. Teste de mascaramento de credenciais nos logs."""
        self.assertEqual(mask_secret(""), "***")
        self.assertEqual(mask_secret(None), "***")
        self.assertEqual(mask_secret("12345"), "***")
        self.assertEqual(mask_secret("1234567890abcdef"), "1234...cdef")

    def test_getme_missing_token_returns_graceful_error(self):
        """2. Teste de getMe com token ausente ou inválido."""
        res = check_telegram_connection(token="seu_bot_token_aqui")
        self.assertFalse(res["ok"])
        self.assertIn("TELEGRAM_BOT_TOKEN não configurado", res["erro"])

    def test_format_telegram_message_class_b(self):
        """3. Teste de formatação de mensagem para Classe B."""
        opp = {
            "titulo": "Scale AI dataset bounty for robot training video collection",
            "url_original": "https://example.com/bounty",
            "data_publicacao": "2026-10-10T12:00:00Z",
            "quem_paga": "Scale AI",
            "servico_atividade": "Robot video collection",
            "pais": "US",
            "valor_orcamento_anunciado": "$50/hr",
            "valor_pagamento_comprovado": "Não informado",
            "evidencia_pagamento": "Anúncio de vaga com orçamento",
            "status_verificacao": "orcamento_anunciado_nao_comprovado",
            "forma_pagamento": "Wise / PayPal",
            "possibilidade_execucao_br": "alta",
            "restricoes_geograficas": "Atende Brasileiros",
            "requisitos_tecnicos": "Python / Automação / IA",
            "tipo_oportunidade": "oferta_contratacao",
            "classificacao_comercial": "B",
            "pontuacao_prioridade": 85.0
        }

        msg = format_telegram_message(opp)
        self.assertIn("RADAR RENDA IA", msg)
        self.assertIn("Scale AI", msg)
        self.assertIn("$50/hr", msg)
        self.assertIn("Classe [B]", msg)

    def test_send_telegram_message_mock(self):
        """4. Teste de envio com mock (zero requisições HTTP reais)."""
        res = send_telegram_message("Mensagem de teste unitário", mock=True)
        self.assertTrue(res["ok"])
        self.assertTrue(res.get("mocked"))
        self.assertEqual(res["result"]["message_id"], 999001)

    def test_sqlite_queue_and_duplicate_prevention(self):
        """5. Teste de enfileiramento no SQLite e prevenção de duplicatas."""
        # Adiciona notícia Classe B
        nid = add_noticia(
            db_path=self.db_path,
            fonte_id=self.fonte_id,
            titulo="Contratando desenvolvedor de agente de IA",
            url_original="https://example.com/job1",
            url_normalizada="https://example.com/job1",
            resumo_bruto="Vaga aberta",
            hash_conteudo="hash123",
            data_publicacao="2026-10-10T12:00:00Z",
            status="coletado",
            classificacao_comercial="B",
            pontuacao_prioridade=85.0
        )
        add_oportunidade(
            db_path=self.db_path,
            noticia_id=nid,
            modelo_negocio="oferta_contratacao",
            quem_paga="Empresa X",
            valor_orcamento_anunciado="$1,000",
            valor_pagamento_comprovado="Não informado",
            evidencia_pagamento="Anúncio ativo",
            status_verificacao="orcamento_anunciado_nao_comprovado"
        )

        # Prepara fila
        novos = preparar_fila_publicacao(self.db_path, min_prioridade=70.0)
        self.assertEqual(novos, 1, "Deve adicionar exatamente 1 item à fila de publicação.")

        # Tenta enfileirar novamente (Prevenção de duplicatas)
        novos_dup = preparar_fila_publicacao(self.db_path, min_prioridade=70.0)
        self.assertEqual(novos_dup, 0, "Idempotência: não deve reinserir item já enfileirado.")

        pendentes = get_publicacoes_pendentes(self.db_path)
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0]["noticia_id"], nid)
        self.assertEqual(pendentes[0]["status_aprovacao"], "pendente")

    def test_approval_and_publishing_flow(self):
        """6. Teste de fluxo completo de aprovação e publicação simulada."""
        nid = add_noticia(
            db_path=self.db_path,
            fonte_id=self.fonte_id,
            titulo="Bounty de Dataset para Treinamento de Robôs",
            url_original="https://example.com/bounty_robot",
            url_normalizada="https://example.com/bounty_robot",
            resumo_bruto="Paying $500 for dataset",
            hash_conteudo="hash456",
            data_publicacao="2026-10-10T12:00:00Z",
            status="coletado",
            classificacao_comercial="B",
            pontuacao_prioridade=90.0
        )
        add_oportunidade(
            db_path=self.db_path,
            noticia_id=nid,
            modelo_negocio="programa_remuneracao",
            quem_paga="Scale AI",
            valor_orcamento_anunciado="$500",
            valor_pagamento_comprovado="Não informado",
            evidencia_pagamento="Anúncio de vaga",
            status_verificacao="orcamento_anunciado_nao_comprovado"
        )

        preparar_fila_publicacao(self.db_path)
        pendentes = get_publicacoes_pendentes(self.db_path)
        pub_id = pendentes[0]["publicacao_id"]

        # Aprova publicação
        ok_aprov = aprovar_publicacao(self.db_path, pub_id)
        self.assertTrue(ok_aprov)

        aprovadas = get_publicacoes_aprovadas(self.db_path)
        self.assertEqual(len(aprovadas), 1)

        # Publica oportunidades aprovadas em MODO SIMULADO
        res_pub = publicar_oportunidades_aprovadas(
            self.db_path,
            token="fake_token",
            chat_id="fake_chat_id",
            mock=True
        )

        self.assertEqual(res_pub["total_aprovadas"], 1)
        self.assertEqual(res_pub["enviadas_sucesso"], 1)
        self.assertEqual(res_pub["falhas_envio"], 0)

        # Verifica alteração de status no SQLite
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status_aprovacao FROM publicacoes WHERE id = ?", (pub_id,))
            st_pub = cursor.fetchone()[0]
            cursor.execute("SELECT status FROM noticias WHERE id = ?", (nid,))
            st_not = cursor.fetchone()[0]

        self.assertEqual(st_pub, "publicado")
        self.assertEqual(st_not, "publicado")

if __name__ == "__main__":
    unittest.main()
