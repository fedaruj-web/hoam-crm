# Hoam Capital CRM Comercial

CRM comercial local em Streamlit, SQLite e Pandas, com identidade visual Hoam Capital.

## Como rodar

Abra o terminal dentro da pasta e execute:

```bash
python iniciar_crm.py
```

O script instala/valida dependencias e abre o Streamlit.

## Modulos

- Dashboard com metricas reais, pipeline ponderado e funil visual.
- Leads com filtros, edicao, responsavel, prioridade HOAM, CNPJ, historico e conversao em cliente.
- Atividades e oportunidades vinculadas a leads.
- Propostas comerciais com status, validade, fee setup, fee recorrente e valor total estimado.
- Agenda de follow-ups.
- Importacao/exportacao CSV ou Excel.
- Cadastro de usuarios/comerciais.
- Clientes convertidos.
- Perfis de acesso: Administrador, Gestor, Comercial e Backoffice.
- Qualidade de dados com deteccao de duplicados, mesclagem segura e padronizacao de CNPJ, telefone, e-mail e Cidade/UF.
- Enriquecimento ANBIMA com classificacao `Gestor`, `Administrador` ou ambos, alem de AuM.

## Arquitetura

- `app.py`: inicializacao, login, sidebar e roteamento.
- `database.py`: schema SQLite/Postgres, migracoes idempotentes e repositorio de dados.
- `services.py`: metricas, funil, importacao/exportacao e DataFrames.
- `ui/styles.py`: tema visual Hoam Capital.
- `ui/pages.py`: telas Streamlit.

O CRM roda com SQLite local por padrao. Se a variavel `DATABASE_URL` estiver configurada, usa Postgres/Supabase automaticamente.

## Publicacao com Supabase

1. Crie um projeto no Supabase.
2. Copie a connection string Postgres em modo pooler/session ou direct connection.
3. Migre a base local:

```bash
python -m pip install -r requirements.txt
python migrar_sqlite_para_supabase.py --database-url "postgresql://..."
```

4. No Streamlit Cloud ou Render, configure o secret/variavel:

```toml
DATABASE_URL = "postgresql://..."
```

5. Publique usando `app.py` como entrypoint.

Localmente, o comando continua o mesmo:

```bash
python iniciar_crm.py
```

## Perfis

- `Administrador`: acesso completo, usuarios, importacao/exportacao e exclusao.
- `Gestor`: visao gerencial, importacao/exportacao e exclusao de leads.
- `Comercial`: operacao comercial, leads, atividades, oportunidades, propostas e follow-ups.
- `Backoffice`: leads, propostas, clientes e follow-ups.

## Propostas

O modulo de propostas permite registrar propostas por lead com status:

- `Rascunho`
- `Enviada`
- `Em negociacao`
- `Aprovada`
- `Recusada`
- `Expirada`

Ao marcar uma proposta como enviada, em negociacao, aprovada ou recusada, o CRM atualiza o status do lead e registra uma atividade no historico. Propostas aprovadas tambem convertem o lead em cliente.

## Qualidade de Dados

O modulo `Qualidade de Dados` esta disponivel para `Administrador` e `Gestor`.

Ele identifica duplicados por:

- CNPJ igual
- E-mail igual
- Nome normalizado igual
- Nome parecido

A mesclagem transfere atividades, oportunidades, propostas e cliente para o lead principal antes de excluir o duplicado. A padronizacao em lote ajusta CNPJ, telefone, e-mail e Cidade/UF sem alterar status, prioridade, responsavel ou historico.

## Enriquecimento ANBIMA

As bases `Ranking_de_Administrador` e `Ranking_de_Gestao` podem ser cruzadas com os leads por nome normalizado. O CRM grava:

- `Tipo ANBIMA`: `Gestor`, `Administrador` ou `Administrador e Gestor`
- `AuM`: patrimonio do ranking ANBIMA, armazenado em R$ milhoes e exibido em reais na interface

Relatorios de auditoria gerados:

- `anbima_matches.csv`
- `anbima_nao_encontrados.csv`

## Importacao HOAM/CVM

Arquivos como `HOAM_Gestoras_Administradoras_COMPLETO.xlsx` sao detectados automaticamente pela aba `CRM - Prospeccao HOAM`.
O importador mapeia `Razao Social`, `CNPJ`, `Cidade/UF`, `Telefone`, `E-mail`, `Contato Principal`, `Prioridade` e `Status`.

Regra de prioridade automatica:

- `Media`: leads ainda sem contato.
- `Alta`: leads em `Contato iniciado` ou qualquer etapa posterior do funil.
