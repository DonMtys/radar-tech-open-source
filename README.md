# RADAR RENDA IA — MVP

O **RADAR RENDA IA** é uma solução inteligente para identificar, analisar, auditar e curar oportunidades reais de geração de renda na internet utilizando Inteligência Artificial.

## 🎯 Objetivo Comercial
Identificar modelos de negócio viáveis baseados em relatos e evidências de renda extra (R$ 1.000 a R$ 10.000/mês), gerando um fluxo de curadoria para atrair leitores e clientes de serviços de automação e agentes de IA, visando atingir os primeiros R$ 1.000 em receita.

---

## 🏗️ Estrutura do Projeto

```text
radar-renda-ia/
├── README.md                  # Visão geral e instruções
├── .gitignore                 # Arquivos ignorados pelo Git
├── .env.example               # Exemplo de variáveis de ambiente
├── database/
│   ├── schema.sql             # Estrutura SQL das tabelas do SQLite
│   ├── db.py                  # Métodos CRUD com PRAGMA foreign_keys = ON
│   └── __init__.py
├── src/
│   └── __init__.py            # Módulos principais (Ingestor, Analisador, Publicador)
└── tests/
    ├── test_db.py             # Testes unitários com unittest da biblioteca padrão
    └── __init__.py
```

---

## 🔒 Diretrizes de Integridade Financeira
1. **Veracidade Estrita:** Depoimentos em redes sociais e prints de dashboards **NÃO** são tratados como validação independente.
2. **Níveis de Comprovação:**
   - `relato`: Depoimentos ou prints não auditáveis.
   - `evidencia_documental`: Código público, contratos ou relatórios financeiros com fontes primárias.
   - `validacao_independente`: Verificação realizada por terceiros auditáveis.
   - `nao_comprovada`: Alegações genéricas ou sem indícios práticos.

---

## 🧪 Como Executar os Testes Unitários

Execução com a biblioteca padrão do Python (sem dependências externas):

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```
