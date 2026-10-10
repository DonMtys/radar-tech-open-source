import os
import sqlite3
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Generator

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")

@contextmanager
def get_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager que abre uma conexão SQLite, habilita PRAGMA foreign_keys = ON,
    garante commit automático e SEMPRE fecha a conexão no final.
    """
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _run_migrations(conn: sqlite3.Connection) -> None:
    """
    Executa migrações de esquema seguras para adicionar novas colunas a tabelas existentes sem perda de dados.
    """
    cursor = conn.cursor()

    # Novas colunas em 'noticias'
    cursor.execute("PRAGMA table_info(noticias);")
    cols_noticias = [row["name"] for row in cursor.fetchall()]

    migracao_noticias = [
        ("data_acontecimento", "DATETIME"),
        ("status_novidade_br", "TEXT DEFAULT 'novidade_no_brasil_nao_verificada'"),
        ("classificacao_comercial", "TEXT DEFAULT 'D'"),
        ("pontuacao_prioridade", "REAL DEFAULT 0.0"),
        ("telegram_sent", "INTEGER DEFAULT 0"),
        ("telegram_sent_at", "DATETIME"),
        ("telegram_message_id", "INTEGER")
    ]
    for col_name, col_type in migracao_noticias:
        if col_name not in cols_noticias:
            cursor.execute(f"ALTER TABLE noticias ADD COLUMN {col_name} {col_type};")

    # Novas colunas em 'oportunidades'
    cursor.execute("PRAGMA table_info(oportunidades);")
    cols_oportunidades = [row["name"] for row in cursor.fetchall()]

    migracao_oportunidades = [
        ("pais", "TEXT DEFAULT 'GL'"),
        ("empresa_pessoa", "TEXT"),
        ("servico_atividade", "TEXT"),
        ("quem_paga", "TEXT"),
        ("valor_alegado", "TEXT"),
        ("tipo_evidencia", "TEXT"),
        ("possibilidade_execucao_br", "TEXT"),
        ("restricoes_geograficas", "TEXT"),
        ("investimento_necessario", "TEXT"),
        ("hipotese_monetizacao", "TEXT"),
        ("proximo_passo_validacao", "TEXT"),
        ("forma_pagamento", "TEXT"),
        ("requisitos_tecnicos", "TEXT"),
        ("tipo_oportunidade", "TEXT"),
        ("evidencia_existencia", "TEXT"),
        ("valor_orcamento_anunciado", "TEXT"),
        ("valor_pagamento_comprovado", "TEXT"),
        ("evidencia_pagamento", "TEXT"),
        ("status_verificacao", "TEXT")
    ]
    for col_name, col_type in migracao_oportunidades:
        if col_name not in cols_oportunidades:
            cursor.execute(f"ALTER TABLE oportunidades ADD COLUMN {col_name} {col_type};")

def init_db(db_path: str, schema_file: str = SCHEMA_FILE) -> None:
    """
    Inicializa o banco de dados SQLite de forma idempotente a partir do schema.sql e executa migrações seguras.
    """
    if not os.path.exists(schema_file):
        raise FileNotFoundError(f"Arquivo de schema SQL não encontrado: {schema_file}")

    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with get_connection(db_path) as conn:
        conn.executescript(schema_sql)
        _run_migrations(conn)

# --- MÉTODOS CRUD DE FONTES ---

def add_fonte(db_path: str, nome: str, url_feed: str, categoria: str = "geral") -> int:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO fontes (nome, url_feed, categoria) VALUES (?, ?, ?)",
            (nome, url_feed, categoria)
        )
        return cursor.lastrowid

def get_fontes(db_path: str) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fontes ORDER BY id ASC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

# --- MÉTODOS CRUD DE NOTÍCIAS ---

def add_noticia(
    db_path: str,
    fonte_id: Optional[int],
    titulo: str,
    url_original: str,
    url_normalizada: str,
    resumo_bruto: str,
    hash_conteudo: str,
    data_publicacao: Optional[str] = None,
    data_acontecimento: Optional[str] = None,
    status: str = "coletado",
    status_novidade_br: str = "novidade_no_brasil_nao_verificada",
    classificacao_comercial: str = "D",
    pontuacao_prioridade: float = 0.0
) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO noticias (
                fonte_id, titulo, url_original, url_normalizada, resumo_bruto, hash_conteudo,
                data_publicacao, data_acontecimento, status, status_novidade_br,
                classificacao_comercial, pontuacao_prioridade
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fonte_id, titulo, url_original, url_normalizada, resumo_bruto, hash_conteudo,
                data_publicacao, data_acontecimento, status, status_novidade_br,
                classificacao_comercial, pontuacao_prioridade
            )
        )
        return cursor.lastrowid

def get_noticia_by_id(db_path: str, noticia_id: int) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM noticias WHERE id = ?", (noticia_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

# --- MÉTODOS CRUD DE EVIDÊNCIAS ---

def add_evidencia(
    db_path: str,
    noticia_id: int,
    alegacao_financeira: str,
    fonte_alegacao: str,
    justificativa: str,
    moeda: str = "BRL",
    valor: Optional[float] = None,
    periodo: str = "nao_especificado",
    tipo_valor: str = "nao_especificado",
    nivel_comprovacao: str = "relato",
    link_evidencia: Optional[str] = None
) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO evidencias (
                noticia_id, alegacao_financeira, moeda, valor, periodo, tipo_valor,
                fonte_alegacao, justificativa, nivel_comprovacao, link_evidencia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                noticia_id, alegacao_financeira, moeda, valor, periodo, tipo_valor,
                fonte_alegacao, justificativa, nivel_comprovacao, link_evidencia
            )
        )
        return cursor.lastrowid

def get_evidencias_by_noticia(db_path: str, noticia_id: int) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM evidencias WHERE noticia_id = ?", (noticia_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

# --- MÉTODOS CRUD DE OPORTUNIDADES ---

def add_oportunidade(
    db_path: str,
    noticia_id: int,
    modelo_negocio: str,
    ferramentas: Optional[str] = None,
    publico_alvo: Optional[str] = None,
    dificuldade_estimada: str = "media",
    custo_estimado: float = 0.0,
    potencial_venda: Optional[float] = None,
    pais: str = "GL",
    empresa_pessoa: Optional[str] = None,
    servico_atividade: Optional[str] = None,
    quem_paga: Optional[str] = None,
    valor_alegado: Optional[str] = None,
    tipo_evidencia: Optional[str] = None,
    possibilidade_execucao_br: Optional[str] = None,
    restricoes_geograficas: Optional[str] = None,
    investimento_necessario: Optional[str] = None,
    hipotese_monetizacao: Optional[str] = None,
    proximo_passo_validacao: Optional[str] = None,
    forma_pagamento: Optional[str] = None,
    requisitos_tecnicos: Optional[str] = None,
    tipo_oportunidade: Optional[str] = None,
    evidencia_existencia: Optional[str] = None,
    valor_orcamento_anunciado: Optional[str] = None,
    valor_pagamento_comprovado: Optional[str] = None,
    evidencia_pagamento: Optional[str] = None,
    status_verificacao: Optional[str] = None
) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO oportunidades (
                noticia_id, modelo_negocio, ferramentas, publico_alvo,
                dificuldade_estimada, custo_estimado, potencial_venda,
                pais, empresa_pessoa, servico_atividade, quem_paga, valor_alegado,
                tipo_evidencia, possibilidade_execucao_br, restricoes_geograficas,
                investimento_necessario, hipotese_monetizacao, proximo_passo_validacao,
                forma_pagamento, requisitos_tecnicos, tipo_oportunidade, evidencia_existencia,
                valor_orcamento_anunciado, valor_pagamento_comprovado, evidencia_pagamento, status_verificacao
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                noticia_id, modelo_negocio, ferramentas, publico_alvo,
                dificuldade_estimada, custo_estimado, potencial_venda,
                pais, empresa_pessoa, servico_atividade, quem_paga, valor_alegado,
                tipo_evidencia, possibilidade_execucao_br, restricoes_geograficas,
                investimento_necessario, hipotese_monetizacao, proximo_passo_validacao,
                forma_pagamento, requisitos_tecnicos, tipo_oportunidade, evidencia_existencia,
                valor_orcamento_anunciado, valor_pagamento_comprovado, evidencia_pagamento, status_verificacao
            )
        )
        return cursor.lastrowid

# --- MÉTODOS CRUD DE PUBLICAÇÕES ---

def add_publicacao(
    db_path: str,
    noticia_id: int,
    texto_preparado: str,
    status_aprovacao: str = "pendente"
) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO publicacoes (noticia_id, texto_preparado, status_aprovacao) VALUES (?, ?, ?)",
            (noticia_id, texto_preparado, status_aprovacao)
        )
        return cursor.lastrowid

def update_publicacao_status(
    db_path: str,
    publicacao_id: int,
    status_aprovacao: str,
    data_aprovacao: Optional[str] = None,
    data_envio: Optional[str] = None,
    telegram_message_id: Optional[int] = None
) -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE publicacoes
            SET status_aprovacao = ?,
                data_aprovacao = COALESCE(?, data_aprovacao),
                data_envio = COALESCE(?, data_envio),
                telegram_message_id = COALESCE(?, telegram_message_id)
            WHERE id = ?
            """,
            (status_aprovacao, data_aprovacao, data_envio, telegram_message_id, publicacao_id)
        )
        return cursor.rowcount > 0

def get_publicacao_by_id(db_path: str, publicacao_id: int) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM publicacoes WHERE id = ?", (publicacao_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

# --- MÉTODOS DE MÉTRICAS E MONETIZAÇÃO AUDITÁVEL ---

def get_publicados_count_24h(db_path: str) -> int:
    """Retorna a quantidade de notícias publicadas no Telegram nas últimas 24 horas."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) as qtd
            FROM noticias
            WHERE status = 'publicado'
              AND telegram_sent_at >= datetime('now', '-24 hours')
            """
        )
        row = cursor.fetchone()
        return row["qtd"] if row else 0

def registrar_metrica_canal(
    db_path: str,
    categoria: str,
    total_analisados: int,
    total_aprovados: int,
    total_publicados: int,
    cliques_estimados: int = 0,
    engajamento_score: float = 0.0
) -> int:
    """Registra métricas reais e transparentes da operação para futura monetização do canal."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO metricas_canal (
                categoria, total_analisados, total_aprovados, total_publicados,
                cliques_estimados, engajamento_score
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (categoria, total_analisados, total_aprovados, total_publicados, cliques_estimados, engajamento_score)
        )
        return cursor.lastrowid

