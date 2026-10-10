import os
import unittest
import tempfile
from database.db import init_db, add_noticia, add_oportunidade, get_connection
from src.telegram_bot import (
    format_telegram_pipeline_message,
    run_telegram_pipeline_round,
    run_telegram_pipeline_forced_test
)

class TestTelegramPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_format_telegram_pipeline_message_defaults(self):
        dict_incompleto = {
            "titulo": None,
            "quem_paga": None,
            "servico_atividade": None,
            "url_original": None,
            "data_publicacao": None,
            "valor_orcamento_anunciado": None,
            "classificacao_comercial": "B",
            "pontuacao_prioridade": 50.0
        }
        msg = format_telegram_pipeline_message(dict_incompleto, is_test=False)
        self.assertIn("🚨 NOVA OPORTUNIDADE — RADAR RENDA IA", msg)
        self.assertIn("📌 Título:\nNão informado", msg)
        self.assertIn("🏢 Contratante:\nNão informado", msg)
        self.assertIn("💼 Serviço:\nNão informado", msg)
        self.assertIn("💰 Remuneração:\nNão informado", msg)
        self.assertIn("📅 Publicado:\nNão informado", msg)
        self.assertIn("🔗 Link:\nNão informado", msg)

    def test_pipeline_sends_class_a_b_and_ignores_c_d(self):
        # Inserir Notícias A, B, C, D
        id_a = add_noticia(self.db_path, None, "Op A", "https://ex.com/a", "https://ex.com/a", "resumo a", "h1", classificacao_comercial="A", pontuacao_prioridade=90.0)
        add_oportunidade(self.db_path, id_a, "mod A", quem_paga="Empresa A", servico_atividade="Servico A", valor_orcamento_anunciado="$1000")

        id_b = add_noticia(self.db_path, None, "Op B", "https://ex.com/b", "https://ex.com/b", "resumo b", "h2", classificacao_comercial="B", pontuacao_prioridade=80.0)
        add_oportunidade(self.db_path, id_b, "mod B", quem_paga="Empresa B", servico_atividade="Servico B", valor_orcamento_anunciado="$500")

        id_c = add_noticia(self.db_path, None, "Op C", "https://ex.com/c", "https://ex.com/c", "resumo c", "h3", classificacao_comercial="C", pontuacao_prioridade=70.0)
        add_oportunidade(self.db_path, id_c, "mod C")

        id_d = add_noticia(self.db_path, None, "Op D", "https://ex.com/d", "https://ex.com/d", "resumo d", "h4", classificacao_comercial="D", pontuacao_prioridade=10.0)

        # Executar rodada com mock_telegram=True e modo_real=False (usa mock de coleta)
        res = run_telegram_pipeline_round(self.db_path, min_prioridade=0.0, modo_real=False, mock_telegram=True)

        self.assertGreaterEqual(res["enviados"], 2)
        
        # Verificar no SQLite que A e B foram marcadas como telegram_sent = 1
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, telegram_sent, status FROM noticias WHERE classificacao_comercial IN ('A', 'B')")
            rows = cursor.fetchall()
            for r in rows:
                self.assertEqual(r["telegram_sent"], 1)
                self.assertEqual(r["status"], "publicado")

            cursor.execute("SELECT id, telegram_sent FROM noticias WHERE classificacao_comercial IN ('C', 'D')")
            rows_cd = cursor.fetchall()
            for r in rows_cd:
                self.assertEqual(r["telegram_sent"], 0)

    def test_pipeline_deduplication(self):
        id_a = add_noticia(self.db_path, None, "Op A", "https://ex.com/a", "https://ex.com/a", "resumo a", "h1", classificacao_comercial="A", pontuacao_prioridade=90.0)
        add_oportunidade(self.db_path, id_a, "mod A", quem_paga="Empresa A")

        # Marcar como já enviada
        with get_connection(self.db_path) as conn:
            conn.execute("UPDATE noticias SET telegram_sent = 1 WHERE id = ?", (id_a,))

        res = run_telegram_pipeline_round(self.db_path, min_prioridade=0.0, modo_real=False, mock_telegram=True)
        self.assertEqual(res["enviados"], 0)
        self.assertGreaterEqual(res["ignorados_duplicidade"], 1)

    def test_telegram_failure_does_not_mark_sent(self):
        id_a = add_noticia(self.db_path, None, "Op A Fail", "https://ex.com/afail", "https://ex.com/afail", "resumo", "hfail", classificacao_comercial="A", pontuacao_prioridade=90.0)
        add_oportunidade(self.db_path, id_a, "mod A")

        # Configura token inválido no ambiente para forçar erro de envio sem fazer chamada real
        old_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        os.environ["TELEGRAM_BOT_TOKEN"] = "INVALID_TOKEN_FOR_TEST_FALHA"
        try:
            res = run_telegram_pipeline_round(self.db_path, min_prioridade=0.0, modo_real=False, mock_telegram=False)
        finally:
            if old_token:
                os.environ["TELEGRAM_BOT_TOKEN"] = old_token
            else:
                os.environ.pop("TELEGRAM_BOT_TOKEN", None)

        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_sent FROM noticias WHERE id = ?", (id_a,))
            row = cursor.fetchone()
            self.assertEqual(row["telegram_sent"], 0)

if __name__ == "__main__":
    unittest.main()
