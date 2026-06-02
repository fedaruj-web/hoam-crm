# Precificacao - racional inicial

Fonte analisada: `Precificacao_v1.pdf`.

## Leitura inicial

O material separa ofertas em blocos de servico, com atividades detalhadas e alguns precos unitarios ou regras abertas. A extracao do PDF indica quatro grupos comerciais principais:

1. Processamento contabil
2. Processamento de fundos/carteiras
3. Implantacao e obrigacoes recorrentes
4. Consultoria, estruturacao, documentos e cobranca

Alguns itens ja possuem preco definido, outros aparecem como `A definir` ou `Verificar com Daruj/Diones`. Portanto, o CRM precisa permitir cadastrar servicos mesmo sem preco fechado.

## Modelo recomendado

Separar `servico` de `preco`.

### Servico

Representa o que a Hoam oferece.

Campos sugeridos:

- Nome
- Categoria
- Descricao
- Escopo/observacoes
- Status ativo/inativo
- Responsavel interno

### Preco

Representa uma condicao comercial daquele servico.

Campos sugeridos:

- Servico vinculado
- Tipo de cobranca: unico, mensal, por documento, por fundo, percentual de sucesso, a definir
- Valor base
- Valor minimo
- Percentual
- Moeda
- Regra textual
- Complexidade: baixa, media, alta, sob analise
- Vigencia inicial/final
- Ativo/inativo

Esse desenho permite alterar precos no futuro sem apagar historico de servicos e sem quebrar propostas antigas.

## Primeira classificacao dos servicos

### BPO / Operacao recorrente

- Processamento contabil
- Precificacao MTM
- Apropriacao de rendimentos
- Suporte na elaboracao de demonstracao financeira
- Atendimento a auditoria interna e externa
- Processamento de fundos/carteiras
- Captura de precos
- Processamento de eventos
- Provisoes de despesas
- Fechamento do PL
- Calculo da cota

### Implantacao / Setup

- Implantacao de fundos/carteiras, cotistas e cedentes
- Cadastro de carteira
- Cadastro de cotistas
- Cadastro de ativos da carteira
- Cadastro de cedentes

### Regulatório / Informes

- Informe diario
- Informe mensal / perfil mensal
- Composicao e diversificacao de carteira (CDA)
- Demonstracoes contabeis anuais e semestrais
- Formulario de informacoes complementares (FIC)
- Lamina de informacoes essenciais
- Ranking ANBIMA
- Formulario de referencia anual

### Consultoria / Estruturacao

- Estruturacao e setup de novos fundos
- Analise de lastro de operacoes
- Emissao de pareceres tecnico-juridicos
- Due diligence e selecao de prestadores
- Elaboracao de documentos de ofertas publicas
- Elaboracao de documentos societarios
- Documentacao CVM
- Credenciamento de gestores e administradores
- Due diligence de cedentes
- Resposta a oficios
- Cobranca extrajudicial e judicial
- Elaboracao/revisao de politicas e manuais

## Precos identificados

- Elaboracao de documentos de ofertas publicas: R$ 1.000,00 por documento
- Elaboracao de documentos societarios: R$ 500,00 por documento
- Documentacao CVM: R$ 500,00 por documento
- Elaboracao/revisao de politicas e manuais: R$ 500,00 por documento
- Cobranca extrajudicial e judicial: 30% do valor executado
- Credenciamento CVM/ANBIMA: R$ 50.000,00, sendo 50% no aceite e 50% no deferimento
- Item recorrente por fundo: R$ 500,00 por fundo
- Item recorrente em sistema do contratante: R$ 500,00
- Acrescimo com sistemas da Hoam: R$ 1.000,00
- Item com minimo: minimo de R$ 1.000,00, conforme complexidade da carteira

## Itens pendentes de validacao

- Quais atividades pertencem exatamente ao pacote `BPO`.
- Se `Processamento contabil` e `Processamento de fundos` sao produtos separados ou pacotes dentro do mesmo BPO.
- Qual item recebe o preco `R$ 500,00 por fundo`.
- Qual item recebe o preco `R$ 500,00 utilizando sistemas do contratante + R$ 1.000,00 com sistemas Hoam`.
- Qual item recebe a regra `minimo de R$ 1.000,00 conforme complexidade`.
- Itens marcados como `A definir` e `Verificar com Diones`.

## Evolucao no CRM

Primeira entrega recomendada:

1. Criar modulo `Servicos`.
2. Criar modulo `Tabela de Precos`.
3. Atualizar `Propostas` para selecionar um servico/preco cadastrado.
4. Manter campos manuais de valor para excecoes comerciais.
5. Exportar proposta com os servicos escolhidos.
