import os
import unittest
import tempfile
from database.db import init_db, add_noticia, add_oportunidade, get_connection
from src.github_trending import fetch_github_trending_repos, traduzir_e_explicar_repositorio
from src.telegram_bot import run_telegram_pipeline_round, format_open_source_telegram_message

class TestOpenSourcePipeline(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_traduzir_e_explicar_repositorio(self):
        repo_sample = {
            "nome_completo": "browserbase/stagehand",
            "nome": "stagehand",
            "descricao_original": "An AI web browsing framework built for automation",
            "linguagem": "TypeScript",
            "estrelas": 1250,
            "topicos": ["ai", "automation", "browser"],
            "url_original": "https://github.com/browserbase/stagehand"
        }
        res = traduzir_e_explicar_repositorio(repo_sample)
        self.assertIn("stagehand", res["titulo_pt"])
        self.assertIn("TypeScript", res["resumo_pt"])
        self.assertIn("automatizadas", res["aplicacao_pratica"])

    def test_format_open_source_telegram_message(self):
        dict_sample = {
            "titulo": "browserbase/stagehand",
            "fonte_nome": "GitHub Trending",
            "pais": "US",
            "estrelas": 1250,
            "requisitos_tecnicos": "TypeScript, Node.js",
            "servico_atividade": "Framework de navegação para automação de IA",
            "hipotese_monetizacao": "Automação de processos web corporativos",
            "data_publicacao": "2026-10-09",
            "url_original": "https://github.com/browserbase/stagehand"
        }
        msg = format_open_source_telegram_message(dict_sample, is_test=True)
        self.assertIn("🧪 TESTE DO PIPELINE", msg)
        self.assertIn("🔥 OPEN SOURCE & TECH", msg)
        self.assertIn("browserbase/stagehand", msg)
        self.assertIn("1250 ⭐", msg)
        self.assertIn("TypeScript", msg)

    def test_simulated_container_restart_deduplication(self):
        """
        Simula a reinicialização do ambiente (ex: nova execução no GitHub Actions com o mesmo SQLite).
        Garante que notícias já processadas e enviadas no Round 1 sejam completamente ignoradas no Round 2.
        """
        # --- ROUND 1 (Primeira execução) ---
        id_1 = add_noticia(
            self.db_path, None, "Repo Open Source 1",
            "https://github.com/org/repo1", "https://github.com/org/repo1",
            "resumo repo 1", "hash_repo_1",
            classificacao_comercial="A", pontuacao_prioridade=95.0
        )
        add_oportunidade(self.db_path, id_1, "open_source", quem_paga="Org 1")

        # Executa round 1 com mock
        res1 = run_telegram_pipeline_round(self.db_path, min_prioridade=0.0, modo_real=False, mock_telegram=True)
        self.assertGreaterEqual(res1["enviados"], 1)

        # --- SIMULAÇÃO DE REINICIALIZAÇÃO DO RUNNER / PROCESSO ---
        # Fecha a conexão, recarrega o DB SQLite do disco para simular restart
        init_db(self.db_path)

        # --- ROUND 2 (Segunda execução) ---
        res2 = run_telegram_pipeline_round(self.db_path, min_prioridade=0.0, modo_real=False, mock_telegram=True)
        
        # Nenhuma mensagem repetida deve ser enviada no Round 2
        self.assertEqual(res2["enviados"], 0)
        self.assertGreaterEqual(res2["ignorados_duplicidade"], 1)

if __name__ == "__main__":
    unittest.main()
