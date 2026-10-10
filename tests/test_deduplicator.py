import os
import tempfile
import unittest

from database.db import init_db, add_noticia
from src.deduplicator import (
    normalize_url,
    compute_content_hash,
    calculate_title_similarity,
    is_duplicate_url,
    find_similar_noticia
)

class TestDeduplicatorModule(unittest.TestCase):

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_01_normalizacao_url_remover_tracking(self):
        """Verifica a remoção de parâmetros de rastreamento mantendo parâmetros relevantes."""
        raw_url = "HTTPS://EXEMPLO.COM/artigo-ia?utm_source=twitter&utm_medium=cpc&fbclid=123&id=99#secao1"
        expected = "https://exemplo.com/artigo-ia?id=99"
        normalized = normalize_url(raw_url)
        self.assertEqual(normalized, expected)

    def test_02_hash_conteudo_estavel(self):
        """Testa o cálculo do hash SHA-256 para título e resumo."""
        h1 = compute_content_hash(" Título Teste ", " Resumo da notícia ")
        h2 = compute_content_hash("título teste", "resumo da notícia")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_03_similaridade_titulos(self):
        """Testa o cálculo de similaridade entre títulos em caso de títulos idênticos e semelhantes."""
        t1 = "Como criei um agente de IA para automação de vendas"
        t2 = "Como criei um agente de IA para automação de vendas!"
        t3 = "Notícia totalmente diferente sobre esportes"

        sim_alta = calculate_title_similarity(t1, t2)
        sim_baixa = calculate_title_similarity(t1, t3)

        self.assertGreaterEqual(sim_alta, 0.90)
        self.assertLess(sim_baixa, 0.30)

    def test_04_deteccao_duplicata_url_sqlite(self):
        """Verifica detecção de URL duplicada no banco de dados SQLite."""
        url_norm = "https://blogficticio.com/post-1"
        add_noticia(
            db_path=self.db_path,
            fonte_id=None,
            titulo="Notícia Original Fictícia",
            url_original="https://blogficticio.com/post-1?utm_source=rss",
            url_normalizada=url_norm,
            resumo_bruto="Resumo",
            hash_conteudo="hash123"
        )

        self.assertTrue(is_duplicate_url(self.db_path, url_norm))
        self.assertFalse(is_duplicate_url(self.db_path, "https://blogficticio.com/post-2"))

    def test_05_alerta_titulos_semelhantes(self):
        """Testa identificação de títulos semelhantes cadastrados no banco sem exclusão compulsória."""
        add_noticia(
            db_path=self.db_path,
            fonte_id=None,
            titulo="Faturei R$ 5.000 vendendo bots de atendimento com IA",
            url_original="https://site.com/post1",
            url_normalizada="https://site.com/post1",
            resumo_bruto="Resumo 1",
            hash_conteudo="hash1"
        )

        similar = find_similar_noticia(self.db_path, "Faturei R$ 5.000 vendendo bots de atendimento com IA no WhatsApp")
        self.assertIsNotNone(similar)
        self.assertGreaterEqual(similar["similarity_score"], 0.70)

if __name__ == "__main__":
    unittest.main()
