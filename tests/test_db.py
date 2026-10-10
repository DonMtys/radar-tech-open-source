import os
import tempfile
import unittest
import sqlite3

from database.db import (
    init_db,
    get_connection,
    add_fonte,
    get_fontes,
    add_noticia,
    get_noticia_by_id,
    add_evidencia,
    get_evidencias_by_noticia,
    add_publicacao,
    update_publicacao_status,
    get_publicacao_by_id
)

class TestDatabaseModule(unittest.TestCase):

    def setUp(self):
        # Cria um arquivo temporário de banco de dados para isolar cada teste
        self.temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_01_criacao_banco(self):
        """Verifica se o banco é criado e se as tabelas existem."""
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tabelas = [row[0] for row in cursor.fetchall()]
        
        tabelas_esperadas = ["fontes", "noticias", "evidencias", "oportunidades", "publicacoes", "execucoes"]
        for tabela in tabelas_esperadas:
            self.assertIn(tabela, tabelas)

    def test_02_inicializacao_repetida_idempotente(self):
        """Verifica se rodar init_db múltiplas vezes não causa erros nem apaga dados."""
        add_fonte(self.db_path, "Fonte Fictícia Teste", "https://exemplo-ficticio.com/rss.xml")
        
        # Executa inicialização repetida
        init_db(self.db_path)
        init_db(self.db_path)

        fontes = get_fontes(self.db_path)
        self.assertEqual(len(fontes), 1)
        self.assertEqual(fontes[0]["nome"], "Fonte Fictícia Teste")

    def test_03_insercao_fonte(self):
        """Testa inserção e recuperação de uma fonte."""
        fonte_id = add_fonte(self.db_path, "Blog Tech Exemplo (Fictício)", "https://blogficticio.com/feed", "tecnologia")
        self.assertGreater(fonte_id, 0)
        
        fontes = get_fontes(self.db_path)
        self.assertEqual(len(fontes), 1)
        self.assertEqual(fontes[0]["url_feed"], "https://blogficticio.com/feed")

    def test_04_insercao_noticia(self):
        """Testa inserção de uma notícia relacionada a uma fonte."""
        fonte_id = add_fonte(self.db_path, "Portal Fictício", "https://portal.ficticio.com/rss")
        noticia_id = add_noticia(
            db_path=self.db_path,
            fonte_id=fonte_id,
            titulo="Estudo de Caso Fictício: Criando Bot de Atendimento com IA",
            url_original="https://portal.ficticio.com/artigo-1?ref=rss",
            url_normalizada="https://portal.ficticio.com/artigo-1",
            resumo_bruto="Desenvolvedor fictício relata uso de IA para automatizar tarefas.",
            hash_conteudo="hash_ficticio_123456"
        )
        self.assertGreater(noticia_id, 0)
        
        noticia = get_noticia_by_id(self.db_path, noticia_id)
        self.assertIsNotNone(noticia)
        self.assertEqual(noticia["titulo"], "Estudo de Caso Fictício: Criando Bot de Atendimento com IA")

    def test_05_bloqueio_url_duplicada(self):
        """Verifica se URLs normalizadas duplicadas geram exceção SQLite (Constraint)."""
        add_noticia(
            db_path=self.db_path,
            fonte_id=None,
            titulo="Notícia A",
            url_original="https://siteficticio.com/post1",
            url_normalizada="https://siteficticio.com/post1",
            resumo_bruto="Resumo",
            hash_conteudo="hash1"
        )
        
        with self.assertRaises(sqlite3.IntegrityError):
            add_noticia(
                db_path=self.db_path,
                fonte_id=None,
                titulo="Notícia B Duplicada",
                url_original="https://siteficticio.com/post1?tracking=abc",
                url_normalizada="https://siteficticio.com/post1", # Mesma URL normalizada
                resumo_bruto="Outro resumo",
                hash_conteudo="hash2"
            )

    def test_06_integridade_chaves_estrangeiras(self):
        """Garante que violar FK (noticia_id inexistente) impede inserção."""
        noticia_id_inexistente = 99999
        with self.assertRaises(sqlite3.IntegrityError):
            add_evidencia(
                db_path=self.db_path,
                noticia_id=noticia_id_inexistente,
                alegacao_financeira="Faturou R$ 5.000",
                fonte_alegacao="Depoimento em fórum fictício",
                justificativa="Relato não auditável",
                moeda="BRL",
                valor=5000.0,
                nivel_comprovacao="relato"
            )

    def test_07_armazenamento_evidencias_e_classificacao(self):
        """Testa inserção de evidência e validação da classificação de veracidade."""
        fonte_id = add_fonte(self.db_path, "Revista Fictícia", "https://revista.ficticia.com/rss")
        noticia_id = add_noticia(
            db_path=self.db_path,
            fonte_id=fonte_id,
            titulo="Relato de Automação de E-commerce com IA",
            url_original="https://revista.ficticia.com/post-ecommerce",
            url_normalizada="https://revista.ficticia.com/post-ecommerce",
            resumo_bruto="Usuário alega ganho de R$ 3.000 com agentes de IA.",
            hash_conteudo="hash_ecom_789"
        )
        
        evidencia_id = add_evidencia(
            db_path=self.db_path,
            noticia_id=noticia_id,
            alegacao_financeira="Faturamento bruto de R$ 3.000,00 no primeiro mês",
            moeda="BRL",
            valor=3000.0,
            periodo="mensal",
            tipo_valor="faturamento",
            fonte_alegacao="Print de dashboard em fórum de discussão fictício",
            justificativa="Prints de tela e depoimentos em texto não configuram prova auditável nem validação independente.",
            nivel_comprovacao="relato",
            link_evidencia="https://forum.ficticio.com/print/123"
        )
        self.assertGreater(evidencia_id, 0)

        evidencias = get_evidencias_by_noticia(self.db_path, noticia_id)
        self.assertEqual(len(evidencias), 1)
        self.assertEqual(evidencias[0]["nivel_comprovacao"], "relato")
        self.assertIn("não configuram prova auditável", evidencias[0]["justificativa"])

    def test_08_atualizacao_status_publicacao(self):
        """Testa o ciclo de vida da publicação: pendente -> aprovado."""
        noticia_id = add_noticia(
            db_path=self.db_path,
            fonte_id=None,
            titulo="Oportunidade Fictícia em Agentes IA",
            url_original="https://site.ficticio.com/opp1",
            url_normalizada="https://site.ficticio.com/opp1",
            resumo_bruto="Resumo oportunidade",
            hash_conteudo="hash_opp1"
        )

        pub_id = add_publicacao(
            db_path=self.db_path,
            noticia_id=noticia_id,
            texto_preparado="🎯 RADAR RENDA IA #001\nModelo: Agente de Suporte",
            status_aprovacao="pendente"
        )
        
        pub_inicial = get_publicacao_by_id(self.db_path, pub_id)
        self.assertEqual(pub_inicial["status_aprovacao"], "pendente")

        # Atualiza para APROVADO
        sucesso = update_publicacao_status(
            db_path=self.db_path,
            publicacao_id=pub_id,
            status_aprovacao="aprovado",
            data_aprovacao="2026-10-09T20:00:00Z"
        )
        self.assertTrue(sucesso)

        pub_atualizado = get_publicacao_by_id(self.db_path, pub_id)
        self.assertEqual(pub_atualizado["status_aprovacao"], "aprovado")
        self.assertEqual(pub_atualizado["data_aprovacao"], "2026-10-09T20:00:00Z")

if __name__ == "__main__":
    unittest.main()
