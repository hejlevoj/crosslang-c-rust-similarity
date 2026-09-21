# Plano de Revisão e Publicação — arXiv + MSR 2027 (Data and Tool Showcase Track)

**Data do plano:** 2026-09-21
**Alvo primário:** MSR 2027, Data and Tool Showcase Track — Dublin, 26–27 abr 2027
**Alvo secundário:** preprint no arXiv (cs.SE), publicado junto com a submissão

---

## 0. Datas que definem o cronograma

| Marco | Data (AoE) |
|---|---|
| Abstract deadline | **qui, 05/nov/2026** |
| Paper deadline | **ter, 10/nov/2026** |
| Notificação | ter, 05/jan/2027 |
| Camera-ready | dom, 24/jan/2027 |
| Conferência | 26–27/abr/2027, Dublin |

Restrições do track:

- **4 páginas + 1 página de referências**, IEEEtran `\documentclass[10pt,conference]{IEEEtran}` (sem `compsoc`).
- **Single-anonymous** — nomes dos autores aparecem no manuscrito. Consequência prática: **preprint no arXiv antes da submissão é permitido e não quebra anonimato**.
- Na publicação, o dado/ferramenta **precisa estar arquivado com DOI** em repositório persistente não-comercial (Zenodo, OSF, figshare). Regras FAIR.
- Submissão: https://msr2027-data-tool.hotcrp.com/

**Tempo disponível até o paper deadline: ~7 semanas.** É suficiente, mas só se a correção do artefato (Fase 1) começar imediatamente — ela é o caminho crítico, não a escrita.

---

## 1. Auditoria do estado atual (o que encontrei no repositório)

Verifiquei o `dataset/dataset.jsonl` e os três pipelines. O dataset em si está consistente: 1886 linhas, 1886 `problem_id` únicos, schema uniforme (`problem_id`, `problem_description`, `c_code`, `rust_code`, `difficulty`), zero campos vazios, zero duplicatas exatas de código ou descrição, e a normalização do entry-point está 100% aplicada (1886/1886 com `solution(` em C e `fn solution` em Rust). Distribuição de dificuldade: easy 472 / medium 943 / hard 471.

O problema não é o dado — são os scripts e a documentação em volta dele.

### 1.1 Bloqueadores de reprodutibilidade (precisam ser resolvidos antes de submeter)

**B1 — Nenhum dos três pipelines roda sobre o dataset publicado.** Três convenções de campo incompatíveis convivem no repo:

| Script | Espera | Realidade do release |
|---|---|---|
| `dataset/finetune/pipeline/prepare_data.py:17` (e `baseline_eval.py:45`, `finetune_st.py:40`, `finetune_lora.py:52`) | `r["c"]`, `r["rust"]` | campos são `c_code`, `rust_code` |
| `dataset/categorization/categorize.py:25` | arquivo `data/dataset_cleaned.jsonl` | arquivo é `dataset/dataset.jsonl` |
| `dataset/description-similarity/description_similarity_openai.py:37` | campo `origin` | **campo não existe** no release |

Um revisor de Data Showcase testa exatamente isso. Hoje o artefato falha no primeiro comando.

**B2 — O script de categorização não reproduz os rótulos publicados.** `categorize.py:26` usa `microsoft/unixcoder-base`, mas os rótulos `difficulty` do release são baseados em `SFR-Embedding-Code-400M_R` (commit `60c0ab1`). A contagem confirma: o release tem 472/943/471, que bate com a tabela SFR do `dataset/README.md`, e não com a tabela UniXcoder (472/942/472) do `dataset/categorization/README.md`. **O campo `difficulty` publicado é atualmente irreprodutível a partir do código publicado.**

**B3 — `dataset/categorization/README.md` está desatualizado.** Ainda descreve a metodologia UniXcoder inteira, incluindo a justificativa ("pairs where `unixcoder-base` already assigns high cosine similarity are easy"), que foi substituída. Contradiz o `dataset/README.md` na mesma árvore.

**B4 — Números conflitantes de resultado.** `dataset/README.md` diz "LoRA achieves MRR@10=0.729"; `dataset/finetune/README.md` diz LoRA 0.725 e full finetune 0.770. Escolher a fonte de verdade e propagar.

**B5 — Proveniência ausente no dado.** Não há `origin`, nem URL/ID da submissão original, nem campo de licença por entrada. O `dataset/README.md` reporta a quebra por fonte (XcodeEval ~1018, CodeNet ~839, common-algorithms 29) mas **essa informação não está no arquivo distribuído** — não dá para reconstruí-la nem para auditar a origem de um par. Para o Data Showcase isso é ponto de rejeição: rastreabilidade e licenciamento são critério explícito.

**B6 — Splits não publicados, e os resultados publicados não correspondem a este dataset.** `prepare_data.py` regenerava train/val/test com `random.seed(42)` **mais** um filtro de tamanho (`len(c) <= 10000 and len(rust) <= 5000`). Reproduzindo esse split sobre o dataset publicado: 1885 pares sobrevivem ao filtro, e `n_test = min(300, 1885 - 1500 - 200)` = **185**.

Mas os dois READMEs reportam "300-pair test set". Como MRR@10 e R@k dependem do tamanho do pool de candidatos, isso não é erro de redação: **os números publicados foram produzidos sobre outro input** — quase certamente o dataset de 2013 pares pré-limpeza, único grande o bastante para o split 1500/200/300. Nenhum resultado atualmente no repositório é comparável a um resultado calculado sobre o release. Reexecutar os baselines (item 11) deixou de ser higiene e virou pré-requisito.

### 1.2 Fraquezas de conteúdo (não bloqueiam, mas viram crítica de revisor)

**F1 — Formato de descrição inconsistente.** 839 entradas (exatamente o bloco CodeNet/AtCoder) carregam HTML bruto (`<span class="lang-en">`, `<var>`, `<section>`); as outras 1047 são texto plano. Um consumidor do dataset precisa detectar o formato sozinho.

**F2 — Equivalência semântica não é verificada por execução.** Não há casos de teste nem I/O esperado. A equivalência funcional dos pares é *herdada* da proveniência ("ambas as submissões foram aceitas"), não verificada. Agravante: a normalização reescreveu `main` → `solution`, então o código distribuído **não compila como programa standalone**. Isso precisa estar explícito no paper, não escondido.

**F3 — Falta LICENSE e CITATION.cff no repositório.** Não existe arquivo de licença. Sem isso o dataset não é legalmente reusável e falha o "R" de FAIR.

**F4 — O dataset não tem nome.** Um dataset paper precisa de um nome citável. Sugestão: **CRUSTPairs** (C–RUST Pairs). Decidir na semana 1 e propagar em tudo.

---

## 2. Fase 1 — Consertar o artefato (semanas 1–3, caminho crítico)

Ordem importa: nada aqui depende de escrever o paper, e escrever o paper depende de quase tudo aqui.

### Semana 1 — Proveniência e schema

1. **Decidir o nome do dataset** e aplicar em README, paper, Zenodo, HF.
2. **Reconstruir e reinserir a proveniência** por entrada. Schema alvo (v1.0):

   ```
   problem_id, dataset_name, origin, origin_problem_id, origin_url,
   problem_description, problem_description_format ("html"|"text"),
   c_code, rust_code, difficulty, difficulty_score, split
   ```

   - `origin` ∈ {`xcodeeval`, `codenet`, `common-algorithms`} — recuperar dos dados de origem, não reinventar.
   - `origin_url` / `origin_problem_id`: rastreabilidade de volta ao problema original.
   - `difficulty_score`: a similaridade SFR bruta, não só o bin. Permite que outros re-binem.
   - `split`: congelar train/val/test **no arquivo**, não no seed.
3. **Normalizar as descrições** (F1): ou converter tudo para texto plano, ou manter o HTML e adicionar `problem_description_format` + um `problem_description_text` derivado. Recomendo a segunda — preserva o original e é imediatamente usável.
4. **Adicionar LICENSE** ao repositório e **verificar a licença de cada fonte upstream** (CodeNet, xCodeEval, common-algorithms) antes de escolher. Confirmar os termos na fonte — não assumir. Documentar a licença por `origin` numa tabela do paper.
5. **Adicionar CITATION.cff.**

### Semana 2 — Código reprodutível

6. **Unificar os nomes de campo** em todos os scripts para o schema v1.0 (resolve B1). Um único módulo de carregamento (`dataset/common/load.py`) que os três pipelines importam.
7. **Consertar `categorize.py` para usar SFR** (resolve B2) e reexecutar para confirmar que regenera exatamente os 472/943/471 publicados. Publicar `difficulty_score` junto. Se os números não baterem, o release é que está errado — investigar antes de seguir.
8. **Atualizar `dataset/categorization/README.md`** para SFR (resolve B3); reconciliar os números de MRR (B4) com os `outputs/results_*.json` reais como fonte de verdade.
9. **Congelar e versionar os splits** (resolve B6). Documentar o filtro de tamanho e o N efetivo, ou removê-lo e reexecutar os baselines.
10. **Teste de fumaça end-to-end**: um script `make reproduce` (ou `scripts/smoke_test.sh`) que, a partir de um clone limpo, roda carregamento → categorização → baseline zero-shot em um subconjunto pequeno. É isso que um revisor vai rodar.

### Semana 3 — Empacotamento

11. **Reexecutar os baselines** com os splits congelados e registrar: zero-shot, LoRA, full finetune — MRR@10, R@1, R@5, **quebrados por tier de dificuldade** (easy/medium/hard). Esse corte por tier é o argumento que justifica a existência dos tiers; sem ele o campo `difficulty` fica decorativo.
12. **Depositar no Zenodo** → obter DOI (exigência do camera-ready; fazer já para citar no preprint).
13. **Publicar no Hugging Face Datasets** com dataset card. Opcional para o MSR, mas é o que gera uso real e citação.
14. **Tag `v1.0` no Git**, com o DOI do Zenodo apontando para o tag.

---

## 3. Fase 2 — Escrever o paper (semanas 3–5, sobrepõe a Fase 1)

**Enquadramento crítico:** no Data and Tool Showcase, a contribuição é **o dataset**, não o finetuning. Os resultados de UniXcoder/LoRA entram como *demonstração de utilidade e baseline de referência* — em uma seção curta. Papers desse track são rejeitados por tentarem ser papers técnicos comprimidos em 4 páginas.

### Estrutura proposta (4 páginas + 1 de referências)

| Seção | Páginas | Conteúdo |
|---|---|---|
| I. Introdução | 0.5 | Por que C↔Rust. Migração C→Rust é agenda ativa (segurança de memória, iniciativas governamentais); falta benchmark pareado. Contribuição em 3 bullets. |
| II. Datasets relacionados | 0.5 | CodeNet, xCodeEval, XLCoST, CoST, AVATAR, POJ-104. Tabela de posicionamento com uma coluna "cobre Rust?" — o gap é o argumento central. |
| III. Construção | 0.75 | Fontes → pareamento → pipeline de normalização (`code-evaluator`) → limpeza (dedup por embedding de descrição; 127 removidos de 2013) → tiers de dificuldade via SFR. Diagrama de fluxo com contagens em cada etapa. |
| IV. Descrição do dataset | 0.75 | Schema (tabela), estatísticas descritivas, distribuição de similaridade SFR, quebra por origem e por tier. Média de tamanho: C 617 chars, Rust 848, descrição 1437. |
| V. Utilidade / baselines | 0.5 | Zero-shot 0.136 → LoRA → full finetune, com a quebra por tier. Uma tabela. |
| VI. Casos de uso e potencial | 0.25 | Busca cross-language, avaliação de tradutores C→Rust (c2rust, LLMs), detecção de clones tipo-4 cross-language, correção automatizada. |
| VII. Limitações e ameaças | 0.25 | **Escrever com honestidade**: equivalência não verificada por execução (F2); código não compilável por causa da normalização do entry-point; viés de programação competitiva (não é código de produção); dificuldade é proxy de similaridade de embedding, não de dificuldade algorítmica; overlap possível com corpora de pré-treino dos modelos avaliados. |
| VIII. Disponibilidade e ética | 0.25 | DOI Zenodo, licença por fonte, link HF, termos de uso das plataformas de origem. |

### Figuras (máximo 3, o espaço é apertado)

- Fig. 1 — pipeline de construção com contagens (2013 → 1886).
- Fig. 2 — histograma da similaridade SFR com as linhas de corte dos tiers.
- Fig. 3 — um par C/Rust lado a lado (exemplo "hard"), mostrando divergência estrutural. É a figura que vende o dataset.

### Tarefas de escrita

- Semana 3: outline + Seções III e IV (são as que dependem da Fase 1 e as mais fáceis de escrever a partir dos READMEs existentes).
- Semana 4: Seções I, II, V. Levantamento bibliográfico sério para a II — é onde revisores de MSR cobram.
- Semana 5: Seções VI–VIII, abstract, passe de corte para caber em 4 páginas (vai estourar; planeje cortar).

---

## 4. Fase 3 — arXiv (semana 6)

- **Categoria primária:** `cs.SE`. **Cross-list:** `cs.LG` (e opcionalmente `cs.CL`).
- **Licença do preprint:** CC BY 4.0. Vale para o *texto do paper*, que é obra sua. **Não** vale para o dataset, que é não-comercial — ver Seção 8.
- **Atenção:** se for a primeira submissão sua em `cs.SE`, o arXiv pode exigir **endorsement**. Verificar isso na **semana 4**, não na 6 — resolver endorsement leva dias e é o erro clássico que atrasa preprint.
- **Momento:** publicar o preprint **no dia da submissão ao MSR ou depois**. O track é single-anonymous, então não há conflito; mas publicar antes não traz benefício e expõe uma versão que ainda pode mudar.
- Incluir no preprint: DOI do Zenodo, link do repositório, link do HF.
- A versão arXiv pode ser mais longa que as 4 páginas do MSR — considere uma versão estendida com as tabelas completas por tier e detalhes de hiperparâmetros que não cabem no paper. Referencie-a no paper como "extended version".

---

## 5. Fase 4 — Submissão ao MSR (semanas 6–7)

| Data | Ação |
|---|---|
| até 29/out | Draft completo, revisão interna com orientador/coautores |
| 02–04/nov | Passe final de formatação IEEEtran, checagem de página |
| **05/nov** | **Registrar abstract no HotCRP** (não perder — sem abstract não se submete o paper) |
| 06–09/nov | Últimos cortes, checagem de links/DOI, teste do artefato em clone limpo |
| **10/nov** | **Submeter o paper** |
| 10–11/nov | Publicar preprint no arXiv |

### Checklist pré-submissão

- [ ] 4 páginas + no máximo 1 de referências, IEEEtran 10pt conference, sem `compsoc`
- [ ] Nomes e afiliações dos autores no manuscrito (single-anonymous)
- [ ] DOI do Zenodo citado no paper
- [ ] Repositório público, clone limpo roda o smoke test
- [ ] README do repositório alinhado com o paper (mesmos números, mesmo nome)
- [ ] LICENSE presente e compatível com as licenças upstream
- [ ] Seção de limitações escrita de forma honesta (F2 explícito)
- [ ] Todos os números do paper conferem com os `outputs/*.json` regenerados

---

## 6. Riscos

| Risco | Mitigação |
|---|---|
| Proveniência (B5) não é recuperável — dados de origem perdidos | Verificar **na semana 1**. Se irrecuperável, o paper precisa declarar isso, e a quebra por fonte no README tem que sair ou virar estimativa declarada. Descobrir isso na semana 5 seria fatal. |
| `categorize.py` com SFR não reproduz os 472/943/471 publicados | Investigar imediatamente; pode indicar que o release foi rotulado com um script/threshold que não está versionado. |
| Reexecução dos baselines é cara (full finetune ~18h em CPU) | Começar na semana 2, rodar em background. Considerar GPU. |
| Paper não cabe em 4 páginas | Planejar corte desde o início; a versão estendida vai para o arXiv. |
| Endorsement do arXiv em cs.SE | Checar na semana 4. |
| Revisor pede verificação por execução (F2) | Não dá para resolver em 7 semanas. Declarar como limitação e como trabalho futuro explícito — é uma posição defensável se estiver escrita. |

---

## 7. Progresso

### Concluído (2026-09-21)

- **B5 — parcialmente resolvido.** Os dados de origem **não existem** em nenhuma versão do git nem em nenhum arquivo local (verificado). Mas `origin` é recuperável do próprio release: `common-algorithms` são os 29 títulos de algoritmo sem enunciado, `codenet` são os enunciados AtCoder em HTML, `xcodeeval` é o resto (Codeforces, delimitadores `$$$`). O classificador em `dataset/scripts/build_dataset_v1.py` reproduz **839 / 1018 / 29 — exatamente** a quebra documentada, o que é validação independente. **Ainda perdidos:** `origin_problem_id` e `origin_url`, que exigiriam casamento contra os corpora públicos CodeNet/xCodeEval.
- **Schema v1.0 gerado.** `dataset.jsonl` agora tem `origin`, `problem_description_format` e `split`. Script de construção versionado e auditável.
- **B1 resolvido.** `dataset/common/load.py` é o ponto único de leitura; os três pipelines foram migrados para ele. Não há mais três convenções de campo.
- **B6 resolvido (parte do split).** Split congelado no arquivo. `prepare_data.py` virou relatório e mostra a quebra por tier e por origem — material direto para as Seções IV e V.
- **B2 — script corrigido, validação pendente.** `categorize.py` agora usa SFR e tem `--verify`, que compara os rótulos regenerados contra os do release e falha alto se divergirem. **Falta rodar** (precisa baixar o modelo).
- **B3, B4 resolvidos.** READMEs reconciliados; a correção 300→185 está registrada no `finetune/README.md`.
- **F1 resolvido** via `problem_description_format` (839 html / 1047 text), preservando o original.
- **Smoke test** em `dataset/scripts/smoke_test.py` — 13 checagens, segundos, sem download. Passa.

### Concluído (2026-09-21, segunda rodada)

- **Split refeito.** Estratificado por (origem × dificuldade) a 80/10/10 sobre os 1886 pares: **1508 / 187 / 191**. O test set espelha o dataset com drift máximo de 0.6pp por origem e 0.7pp por tier — pré-requisito para reportar MRR@10 por tier na Seção V. O filtro de tamanho foi removido: excluía exatamente 1 par (problema `0257`, 16460 chars de C) enquanto o filtro de Rust não excluía nenhum, e os modelos truncam em 512 tokens de qualquer forma.
- **Licenciamento avaliado e materializado** — ver Seção 8, que é o achado mais consequente desta rodada.

---

## 8. Licenciamento (avaliado em 2026-09-21)

As três fontes **não compartilham licença**, e a combinação é mais restritiva do que este plano supunha na primeira versão.

| Fonte | Pares | Licença dos dados | Verificado em |
|---|---|---|---|
| xCodeEval (Codeforces) | 1018 (54%) | **CC BY-NC 4.0** | README do `ntunlp/xCodeEval` |
| CodeNet (AtCoder) | 839 (44.5%) | **CDLA-Permissive-2.0** | IBM / Linux Foundation |
| common-algorithms | 29 (1.5%) | **GPL-3.0** (lado C) e **MIT** (lado Rust) | `TheAlgorithms/C` e `TheAlgorithms/Rust` |

Identifiquei a fonte do `common-algorithms` pelo código: os 29 pares são do projeto TheAlgorithms, cujos repositórios por linguagem têm licenças diferentes — C é GPL-3.0, Rust é MIT.

**Três consequências que mudam decisões do plano:**

1. **O dataset agregado é não-comercial.** 54% é CC BY-NC 4.0, então o conjunto não pode ser relicenciado como CC BY 4.0, MIT, Apache-2.0 ou CDLA. A recomendação original de CC BY 4.0 para o dataset estava errada e foi corrigida — ela continua valendo só para o texto do preprint.
2. **GPL-3.0 e CC BY-NC 4.0 não se fundem numa obra só.** A GPL exige liberdade de redistribuição comercial; a CC BY-NC proíbe exatamente isso. Os arquivos convivem como *coleção* (mera agregação), cada registro com seus próprios termos.
3. **Atenção a uma contradição na fonte.** O mirror do xCodeEval no Hugging Face está marcado `cc-by-4.0`, contradizendo o README do repositório, que diz CC BY-NC 4.0. Segui o README — é a declaração dos próprios autores e a mais restritiva. Se você precisar da leitura permissiva, obtenha confirmação por escrito dos autores; não se apoie na tag do HF.

**Entregue:** campo `license` por registro (expressão SPDX); [`DATA_LICENSES.md`](DATA_LICENSES.md) com a análise completa; `LICENSES/CDLA-Permissive-2.0.txt` incluído porque a seção 2.1 dessa licença obriga a distribuir o texto junto; `LICENSE` (MIT) cobrindo **apenas o código próprio** do repositório, com aviso explícito de que não cobre os dados. O smoke test valida tudo isso.

**Os 29 pares `common-algorithms` foram removidos** (decisão do autor, 2026-09-21). O dataset passou de 1886 para **1857 pares**, agregado limpo de duas licenças: CC BY-NC 4.0 (1018) + CDLA-Permissive-2.0 (839), sem copyleft e sem registros com metades sob licenças diferentes. A exclusão está implementada como `DROPPED_ORIGINS` em `build_dataset_v1.py` — documentada e reversível, não uma deleção pontual. Split re-estratificado: **1485 / 185 / 187**.

Efeito colateral esperado: os tiers de dificuldade eram quantis sobre 1886 e ficaram desbalanceados em 458/931/468 ao serem aplicados a 1857. Isso se resolve re-rotulando — ver Seção 9.

**Ainda pendente:** a CC BY-NC 4.0 exige atribuição ao criador, e como os identificadores upstream se perderam (B5), a atribuição hoje só é possível no nível do corpus, não do problema. Esse é o argumento prático mais forte para recuperar a proveniência por problema.

---

## 9. Re-rotulagem de dificuldade (em execução)

`categorize.py --write-labels` está rodando sobre os 1857 pares. Ele recalcula a similaridade SFR, re-binariza em quantis 25/50/25 sobre a população atual, grava `difficulty` e adiciona `difficulty_score` (a similaridade bruta, para que terceiros possam re-binarizar com outros cortes).

Note que `--verify` deixou de ser um teste limpo do B2 depois da remoção dos 29: os rótulos antigos eram quantis sobre 1886, então alguma discordância de fronteira é **esperada** e não indica defeito. Por isso o script agora sempre reporta a taxa de concordância e a matriz de migração (`easy -> medium`, etc.) de forma informativa, e `--verify` só é fatal quando você quer o teste estrito sobre a mesma população.

**O que olhar no resultado:**

- **Concordância alta (> ~95%), migrações só de fronteira** — os rótulos publicados eram reprodutíveis; B2 fechado. A discordância residual é o efeito da mudança de população.
- **Concordância baixa, ou migrações `easy -> hard`** — o release foi rotulado por um script ou pooling que não está versionado. Nesse caso os números de dificuldade do paper têm que vir da nova rodada, e vale registrar isso como ameaça à validade.

Depois que terminar:

1. `python dataset/scripts/build_dataset_v1.py --write` — re-estratifica o split contra os tiers novos.
2. Atualizar a tabela de thresholds em `dataset/README.md` (está marcada como pendente).
3. `python dataset/scripts/smoke_test.py` — o aviso de tiers desbalanceados deve sumir.

---

## 10. Próximo passo depois disso

Reexecutar os baselines (item 11 da Semana 3) sobre o split novo, reportando MRR@10 / R@1 / R@5 **por tier** além do global. É o último número que falta para a Seção V, e os atuais não servem.
