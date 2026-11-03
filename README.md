# Empório da Música: agente de atendimento

Agente de mensagens de texto que atende clientes da Empório da Música, loja fictícia de instrumentos musicais em Campo Grande/MS. O Tom, persona do agente, consulta catálogo e pedidos, aplica as políticas da loja, registra reclamações e reconhece o que está fora de escopo.

```
Cliente ─▶ CLI ─▶ Agent.reply(sessão, texto)
                     │
                     ├─ LLMClient ─▶ Claude ou Gemini (mesma interface)
                     ├─ ToolRegistry ─▶ services ─▶ CSVs e manual em PDF
                     ├─ Guardrail: todo valor em R$ precisa ter origem conhecida
                     └─ SessionStore: histórico em SQLite
```

## Como rodar

Requer Python 3.11 ou superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

No `.env`, escolha o provedor e preencha a chave correspondente:

| Provedor | Variáveis | Modelo padrão |
| --- | --- | --- |
| Claude | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY` | `claude-opus-5-5` |
| Gemini | `LLM_PROVIDER=gemini`, `GEMINI_API_KEY` | `gemini-3.8-flash` |

`LLM_MODEL` troca o modelo padrão.

```bash
emporio-agent                     # nova conversa
emporio-agent --session maria     # cria ou retoma a conversa "maria"
emporio-agent --debug             # mostra tools chamadas e consumo de tokens
pytest                            # testes, sem rede e sem custo
python -m evals.run               # avaliação com o modelo real (consome créditos)
python scripts/generate_examples.py  # regenera examples/ (consome créditos)
```

## Decisões técnicas

### Abordagem: function calling híbrido, com loop próprio

Dados estruturados vêm de tools determinísticas, e políticas vêm de consulta por seção. O LLM decide o que consultar e redige a resposta, mas não faz contas nem aplica prazos.

- **Por que não agente de SQL:** SQL gerado pelo modelo teria acesso à tabela de clientes sem controle por linha. Com tools fechadas, uma injeção de prompt não alcança dados de outro cliente, porque nenhuma tool os devolve sem verificação.
- **Por que não LangChain ou LangGraph:** o fluxo é um único laço de chamar modelo, executar tools e validar. Um loop de cerca de 100 linhas é mais fácil de testar, depurar e explicar.
- **Regras de negócio em código:** PIX, faixas de parcelamento, promoção, disponibilidade e prazos ficam nos `services`. Pelo manual, informação incorreta pode configurar propaganda enganosa (§7.1), então esses cálculos não podem depender do modelo.

### Retrieval: por sumário, sem banco vetorial

O manual tem 8 páginas e 28 seções. A ingestão separa as seções pela tipografia do PDF, preserva tabelas em markdown, e o modelo recebe o sumário na própria definição da tool. Ele escolhe a seção e lê o texto inteiro.

- Não há embeddings, download de modelo nem índice para manter.
- Nenhuma regra é cortada no meio de um chunk, o que é importante em um texto cheio de exceções.
- A separação usa a fonte, não só o texto: um regex confundiria a lista "1. Saudação" do §7.2 com capítulos.
- `PolicyRetriever` é uma interface. Se o corpus crescer, dá para trocar por busca vetorial sem mexer no agente.

### Modelo e provedor

Claude e Gemini ficam atrás da interface `LLMClient`, com um adaptador para cada um. O histórico é guardado no formato nativo do provedor e reenviado sem alteração, porque blocos de raciocínio e assinaturas precisam voltar intactos. Por isso, uma sessão fica presa ao provedor em que começou.

- **Claude:** `claude-opus-5-5` com `effort: low`, adequado a chat. O `system` e o histórico usam prompt caching. A opção `fallbacks: "default"` (beta) repete no servidor pedidos recusados por classificadores de segurança, e `stop_reason: "refusal"` é tratado antes de ler a resposta.
- **Gemini:** alternativa para quem quiser testar com o tier gratuito do Google AI Studio. Limites de requisição podem atrapalhar os evals.
- **Cache:** data e hora vão na mensagem do turno, não no system prompt, para não invalidar o cache.

### Estratégia de prompt

O prompt (`prompts/system.md`) é versionado separado do código e cobre persona, roteamento de tools, regras de apresentação, identidade e escopo. O tom e o fluxo vêm do §7 do manual.

As proteções importantes não dependem do prompt:

| Risco | Proteção em código |
| --- | --- |
| Inventar preço | Guardrail rejeita valores em R$ sem origem em tools ou na fala do cliente: uma nova tentativa e, depois, encaminhamento à equipe |
| Vazar dados de cliente | Tools exigem número do pedido + contato e devolvem só o primeiro nome |
| Descobrir pedidos por tentativa | Mesma resposta para pedido inexistente e contato errado, com bloqueio após 3 falhas |
| Cliente se passar pelo sistema | A tag de contexto é removida do texto do cliente |

### Interface e persistência

- **CLI:** o foco do desafio é o agente. `Agent.reply()` é desacoplado da interface, então um webhook de WhatsApp só precisaria chamar esse método.
- **SQLite:** clientes voltam à conversa em mensagens, então o histórico sobrevive a reinícios. Em produção, a chave da sessão seria o telefone. Tickets e contagem de falhas de verificação ficam no mesmo banco.

### Tratamento de dados

Telefones são normalizados para dígitos, e-mails para minúsculas, dinheiro usa `Decimal` e a busca ignora acentos, plural simples e pequenos erros de digitação. Inconsistências da base são preservadas e tratadas nas regras, em vez de corrigidas silenciosamente.

## Suposições

O enunciado pede para documentar interpretações. Estas merecem validação com a loja:

| Situação | Decisão |
| --- | --- |
| Pedidos terminam em março/2026 | `AGENT_NOW=2026-03-25T10:30` no `.env.example`, para que prazos e atrasos façam sentido. Remova para usar o relógio real |
| WhatsApp: (67) 3341-4444 no §1.2 e (67) 3321-4500 no §7 | Vale 3341-4444, que coincide com a capa (errata em `policies/errata.py`) |
| E-mail com e sem acento no domínio | Vale a versão sem acento, da capa |
| Parcela mínima: R$ 100 na tabela do §3 e faixas no §3.1 | Vale o §3.1, mais específico. Em 2x e 3x, o mínimo é R$ 50; em 1x, não há mínimo |
| Base sem data de recebimento | Prazos usam `estimated_delivery`, e o agente avisa o cliente |
| Base sem canal de venda | O agente pergunta, pois o arrependimento (§4.1) vale para compras online |
| §4.3 não define o início dos 7 dias | Conta a partir do recebimento, a leitura mais favorável ao cliente |
| Troca por defeito (30 dias, §4.2) e garantia legal (90 dias, §8.1) | A tool devolve as duas janelas, e a loja oferece intermediação |
| Cancelamento antes da entrega não consta no manual | Não promete: abre ticket |
| Status `pending` e `confirmed` não são definidos | Lidos como "aguardando confirmação" e "ainda não despachado" |
| Produto `active` sem estoque, `discontinued` com saldo e `coming_soon` com saldo | Só `active` com estoque é vendável |
| Sopro e cordas orquestrais: citados no manual, sem produtos no CSV | Diz que não há modelos no sistema agora e oferece encaminhar. O catálogo tem 65 itens, não os "300+" do manual |
| "Lojas parceiras" sem lista | Não cita nomes |
| Frete com pedido de exatamente R$ 500 | Não definido pelo manual. Nenhum produto custa esse valor |

Inconsistências da base, sem efeito no atendimento além de `total_brl` ser a fonte de verdade:

- Total diferente da soma dos itens nos pedidos 3 (R$ 3.450 e R$ 3.498) e 20 (R$ 1.400 e R$ 1.488).
- Parcelas abaixo do mínimo nos pedidos 9, 16 e 18.
- Itens `coming_soon` vendidos nos pedidos 3 e 14.
- E-mail repetido nos clientes 11 e 43: por isso, e-mail sozinho não basta para listar pedidos.

## Exemplos e avaliação

**Pendente de execução ao vivo.** As conversas de `examples/` e o relatório de `evals/results/` são gerados apenas por execuções reais do modelo. Rode os comandos abaixo antes da entrega e substitua este parágrafo pelo resultado.

```bash
python scripts/generate_examples.py
python -m evals.run --output evals/results/anthropic.md
```

Cenários preparados em `scripts/generate_examples.py`:

1. Catálogo e preço, com PIX e parcelamento.
2. Promoção ativa sem PIX acumulado e Black Friday vencida.
3. Devolução: verificação de identidade, prazo vencido e garantia (situação não trivial).
4. Produto sem estoque, descontinuado com saldo, acessórios e assunto fora de escopo.
5. Pedido atrasado, reclamação com protocolo e recusa de dados de outro cliente.

`evals/cases.py` traz 21 casos com checagens determinísticas de tools chamadas e fatos da resposta, sem LLM juiz, para serem baratos e reproduzíveis. `pytest` cobre as regras e o loop com um LLM roteirizado e os adaptadores com tipos reais dos SDKs, mas não substitui os evals.

## Limitações conhecidas

- Os dados ficam em memória, lidos dos CSVs ao iniciar. Alterações nos arquivos exigem reiniciar.
- O agente só consulta e registra tickets. Não fecha vendas, não cancela e não reembolsa.
- Tickets ficam no SQLite local, sem integração com a equipe.
- Verificar identidade com telefone ou e-mail é fraco para produção. O caminho seria usar o número de origem do WhatsApp ou um código de confirmação.
- O histórico guarda dados informados pelo cliente, sem política de retenção. Em produção, isso precisaria de tratamento conforme a LGPD (§9).
- O guardrail só reconhece valores no formato `R$`, não por extenso.
- Feriados cobrem o calendário nacional e o de MS, não os municipais de Campo Grande.
- Não há cálculo de frete: depende de CEP, peso e dimensões, que não estão na base.
- A busca lexical não entende intenção como "algo parecido com o som de um Martin". Essa parte fica a cargo do modelo.

## O que eu faria com mais tempo

1. Webhook de WhatsApp com autenticação pelo número de origem.
2. Integração dos tickets com a ferramenta da equipe e handoff com o resumo da conversa.
3. Observabilidade: traces por turno, custo por conversa e taxa de encaminhamento.
4. Comparação medida entre o retrieval por sumário e uma busca BM25 ou vetorial.
5. Eval set maior, formado a partir de conversas reais, rodando em CI.
6. Correção das inconsistências do manual e da base junto com a loja.

## Uso de assistentes de código

> **Rascunho: revise e ajuste para refletir o seu workflow real antes de entregar.**

Usei o **Claude Code** (modelo Claude Opus 5.5) como par de programação. Eu defini o objetivo e tomei as decisões de provedor e de publicação do repositório. O Claude Code leu o enunciado, o manual e os CSVs, levantou as inconsistências da base, propôs o plano que aprovei e implementou o código e os testes em commits incrementais, que trazem `Co-Authored-By`.

O que ajudou a manter a qualidade: plano revisado antes do código, auditoria dos dados antes de modelar as regras e testes escritos a partir das armadilhas encontradas. Um deles pegou um bug real, em que a busca por "violões" trazia ukuleles. As conversas de exemplo são geradas por script, para não haver texto escrito à mão.

## Estrutura

```
src/emporio_agent/
  config.py      configuração e relógio injetável
  cli.py         interface de linha de comando
  domain/        entidades e dinheiro
  data/          leitura dos CSVs e repositório
  policies/      ingestão do PDF, errata e retriever
  services/      preço, disponibilidade, busca, pedidos, devolução, horário, tickets
  tools/         definição das tools sobre os services
  llm/           interface comum e adaptadores de Claude e Gemini
  agent/         loop, prompt e guardrail
  memory/        sessões em SQLite
prompts/system.md   persona e regras do agente
evals/              casos e executor da avaliação
scripts/            gerador das conversas de exemplo
tests/              testes sem rede
```
