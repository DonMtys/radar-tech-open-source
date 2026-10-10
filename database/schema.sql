-- Schema para o Banco de Dados SQLite do RADAR RENDA IA (Etapa 3.1 & 3.5)
PRAGMA foreign_keys = ON;

-- 1. Fontes de Notícias / RSS
CREATE TABLE IF NOT EXISTS fontes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    url_feed TEXT NOT NULL UNIQUE,
    categoria TEXT DEFAULT 'geral',
    status TEXT DEFAULT 'ativo' CHECK (status IN ('ativo', 'inativo', 'erro')),
    ultima_consulta DATETIME
);

-- 2. Notícias Coletadas
CREATE TABLE IF NOT EXISTS noticias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte_id INTEGER,
    titulo TEXT NOT NULL,
    url_original TEXT NOT NULL,
    url_normalizada TEXT NOT NULL UNIQUE,
    data_publicacao DATETIME,
    data_acontecimento DATETIME,
    data_coleta DATETIME DEFAULT CURRENT_TIMESTAMP,
    resumo_bruto TEXT,
    hash_conteudo TEXT NOT NULL,
    status TEXT DEFAULT 'coletado' CHECK (status IN ('coletado', 'analisado', 'aprovado', 'rejeitado', 'descartado_antigo', 'em_revisao_data', 'publicado', 'erro')),
    status_novidade_br TEXT DEFAULT 'novidade_no_brasil_nao_verificada',
    classificacao_comercial TEXT DEFAULT 'D' CHECK (classificacao_comercial IN ('A', 'B', 'C', 'D', 'desconhecido')),
    pontuacao_prioridade REAL DEFAULT 0.0,
    telegram_sent INTEGER DEFAULT 0,
    telegram_sent_at DATETIME,
    telegram_message_id INTEGER,
    FOREIGN KEY (fonte_id) REFERENCES fontes(id) ON DELETE SET NULL
);

-- 3. Evidências Financeiras e Auditoria de Alegações
CREATE TABLE IF NOT EXISTS evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    noticia_id INTEGER NOT NULL,
    alegacao_financeira TEXT NOT NULL,
    moeda TEXT DEFAULT 'BRL',
    valor REAL,
    periodo TEXT DEFAULT 'nao_especificado' CHECK (periodo IN ('mensal', 'diario', 'anual', 'unico', 'nao_especificado')),
    tipo_valor TEXT DEFAULT 'nao_especificado' CHECK (tipo_valor IN ('faturamento', 'lucro', 'nao_especificado')),
    fonte_alegacao TEXT NOT NULL,
    justificativa TEXT NOT NULL,
    nivel_comprovacao TEXT DEFAULT 'relato' CHECK (nivel_comprovacao IN ('relato', 'evidencia_documental', 'validacao_independente', 'nao_comprovada')),
    link_evidencia TEXT,
    data_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (noticia_id) REFERENCES noticias(id) ON DELETE CASCADE
);

-- 4. Oportunidades Identificadas (Estruturadas Etapa 3.1)
CREATE TABLE IF NOT EXISTS oportunidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    noticia_id INTEGER NOT NULL,
    modelo_negocio TEXT NOT NULL,
    ferramentas TEXT,
    publico_alvo TEXT,
    dificuldade_estimada TEXT CHECK (dificuldade_estimada IN ('baixa', 'media', 'alta', 'desconhecida')),
    custo_estimado REAL DEFAULT 0.0,
    potencial_venda REAL,
    pais TEXT DEFAULT 'GL',
    empresa_pessoa TEXT,
    servico_atividade TEXT,
    quem_paga TEXT,
    valor_alegado TEXT,
    tipo_evidencia TEXT,
    possibilidade_execucao_br TEXT,
    restricoes_geograficas TEXT,
    investimento_necessario TEXT,
    hipotese_monetizacao TEXT,
    proximo_passo_validacao TEXT,
    forma_pagamento TEXT,
    requisitos_tecnicos TEXT,
    tipo_oportunidade TEXT,
    evidencia_existencia TEXT,
    valor_orcamento_anunciado TEXT,
    valor_pagamento_comprovado TEXT,
    evidencia_pagamento TEXT,
    status_verificacao TEXT,
    FOREIGN KEY (noticia_id) REFERENCES noticias(id) ON DELETE CASCADE
);

-- 5. Fila de Publicações / Moderação para o Telegram
CREATE TABLE IF NOT EXISTS publicacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    noticia_id INTEGER NOT NULL UNIQUE,
    texto_preparado TEXT NOT NULL,
    status_aprovacao TEXT DEFAULT 'pendente' CHECK (status_aprovacao IN ('pendente', 'aprovado', 'rejeitado', 'publicado')),
    data_aprovacao DATETIME,
    data_envio DATETIME,
    telegram_message_id INTEGER,
    FOREIGN KEY (noticia_id) REFERENCES noticias(id) ON DELETE CASCADE
);

-- 6. Histórico de Execuções e Processos
CREATE TABLE IF NOT EXISTS execucoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operacao TEXT NOT NULL,
    inicio DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fim DATETIME,
    resultado TEXT CHECK (resultado IN ('sucesso', 'falha', 'em_andamento')),
    erro TEXT
);

-- 7. Métricas Reais do Canal para Futura Monetização
CREATE TABLE IF NOT EXISTS metricas_canal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    categoria TEXT NOT NULL,
    total_analisados INTEGER DEFAULT 0,
    total_aprovados INTEGER DEFAULT 0,
    total_publicados INTEGER DEFAULT 0,
    cliques_estimados INTEGER DEFAULT 0,
    engajamento_score REAL DEFAULT 0.0
);

-- Índices de Performance e Desduplicação
CREATE INDEX IF NOT EXISTS idx_noticias_url_norm ON noticias(url_normalizada);
CREATE INDEX IF NOT EXISTS idx_noticias_hash ON noticias(hash_conteudo);
CREATE INDEX IF NOT EXISTS idx_noticias_status ON noticias(status);
CREATE INDEX IF NOT EXISTS idx_noticias_prioridade ON noticias(pontuacao_prioridade);
CREATE INDEX IF NOT EXISTS idx_evidencias_noticia ON evidencias(noticia_id);
CREATE INDEX IF NOT EXISTS idx_publicacoes_status ON publicacoes(status_aprovacao);
CREATE INDEX IF NOT EXISTS idx_metricas_categoria ON metricas_canal(categoria);
