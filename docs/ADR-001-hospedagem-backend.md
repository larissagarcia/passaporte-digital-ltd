# ADR-001 — Hospedagem: PythonAnywhere (backend) + GitHub Pages (frontend)

- **Status:** proposto
- **Data:** 2026-09-24
- **Branch:** `refactor/pythonanywhere`
- **Decisão:** adotar PythonAnywhere (free tier) para a API e o banco, mantendo
  o frontend estático no GitHub Pages publicado via GitHub Actions.

---

## 1. Contexto

Hoje o Passaporte Digital **não tem backend**. A arquitetura é um gerador de
site estático:

```text
data/alunos.json ──► src/generator.py ──► src/templates/index.html ──► index.html ──► GitHub Pages
```

Esse modelo resolveu a publicação, mas três limitações do estado atual do
código motivam esta decisão:

### 1.1 Os dados pessoais dos alunos são públicos

`src/generator.py` renderiza a lista completa de alunos no template, e o
template a serializa dentro da página:

```jinja
window.passaporteData = {{ {"alunos": alunos}|tojson }};
```

— `src/templates/index.html:456`

O `index.html` publicado no GitHub Pages contém, em texto puro, o nome e o
e-mail dos 12 alunos de `data/alunos.json`. O repositório é público. Se houver
menor de idade entre os participantes, isso caracteriza exposição de dado
pessoal sob a LGPD, não apenas um problema de higiene.

### 1.2 O controle de acesso é decorativo

O formulário de acesso é resolvido inteiramente no navegador:

```js
const student = students.find(item => item.email.trim().toLowerCase() === email);
```

— `src/js/script.js`, handler de `accessForm`

Como a lista de e-mails está na própria página, qualquer visitante digita o
e-mail de outro aluno e visualiza o passaporte dele. Não há segredo a ser
verificado.

### 1.3 Presença e feedback não são persistidos

O botão de resgate marca o módulo como conquistado apenas em memória e grava
em `localStorage` sob a chave `ltd-modulos-<email>`. As estrelas de avaliação
(`selectedRating`) não são gravadas em lugar nenhum — nem localmente. Trocar de
navegador, limpar o cache ou usar outro aparelho zera o progresso, e o LTD
nunca recebe os feedbacks das oficinas.

**Conclusão do contexto:** o que falta não é migrar um backend, é criar o
primeiro. A questão desta ADR é onde ele mora.

---

## 2. A divisão proposta

| Camada | Onde | Responsabilidade |
| --- | --- | --- |
| Frontend estático | GitHub Pages | HTML, CSS, JS, imagens das insígnias |
| Build do frontend | GitHub Actions | roda `src/generator.py` e publica |
| API | PythonAnywhere | login, presença, feedback, progresso |
| Banco | PythonAnywhere | alunos, presenças, avaliações |

O ponto central: **`data/alunos.json` deixa de conter e-mails**. O build passa a
gerar apenas a casca da página (layout, módulos, imagens), e todo dado de aluno
passa a ser buscado da API após autenticação.

---

## 3. Tradeoffs

### 3.1 GitHub Pages + Actions — o que ganhamos e o que perdemos

**A favor (e por isso fica)**

- Custo zero, CDN global, HTTPS automático, sem manutenção de servidor.
- O pipeline de build já existe e já é entendido pela equipe.
- Domínio próprio é gratuito no Pages (o do PythonAnywhere é pago).
- Deploy é `git push`: reversível por `git revert`, com histórico.

**Contra (limites que forçam o backend)**

- **Só serve arquivo estático.** Não executa código no servidor, não tem banco,
  não guarda estado entre visitas. Qualquer escrita precisa de outro lugar.
- **Tudo que é publicado é público.** Não existe conteúdo protegido por login
  no Pages; segredo embutido em build é segredo vazado.
- **Actions não é backend.** É build sob evento, não atende requisição de
  usuário. Usar `workflow_dispatch` como se fosse API dá latência de minutos e
  consome cota de Actions.
- Repositório público implica Pages público — não há como restringir no free.

### 3.2 PythonAnywhere (free tier) — a favor

- **Disco persistente de verdade.** É a diferença decisiva contra Render, Fly e
  Railway no free tier, onde o container é efêmero e o banco desaparece no
  redeploy. Aqui o arquivo fica.
- **Sem cold start.** O free do Render hiberna e leva dezenas de segundos para
  acordar. Numa oficina, com o aluno esperando na tela, isso é inaceitável.
- HTTPS pronto em `*.pythonanywhere.com`, sem configuração.
- Flask/Django são o caminho batido da plataforma; a stack já é Python.
- Console e editor no navegador — dá para socorrer o sistema durante a oficina
  sem máquina de desenvolvimento por perto.

### 3.3 PythonAnywhere (free tier) — contra

Em ordem de gravidade para este projeto:

1. **Renovação manual a cada 3 meses.** Chega um e-mail, alguém precisa clicar
   para manter o app ativo; sem isso ele é desativado. *É o maior risco
   operacional do plano:* se a renovação cair nas férias, o passaporte sai do ar
   no meio do curso. Mitigação: lembrete no calendário do LTD com dois
   responsáveis, não um.
2. **Saída para a internet restrita por whitelist.** No free tier, chamadas HTTP
   de saída passam por um proxy que só permite domínios listados.
   **Verificar antes de depender:** API do Telegram (notificação de deploy),
   Tally, Google Sheets. Descobrir isso em produção é o pior cenário.
3. **Cota de CPU** (na faixa de 100 segundos por dia no free; confirmar o valor
   corrente) e **um único worker**. Suficiente para 12 alunos; apertado se o LTD
   rodar turmas simultâneas.
4. **Domínio próprio exige plano pago** (~US$5/mês). A API fica em
   `usuario.pythonanywhere.com`.
5. **Sem WebSocket e sem tarefa agendada frequente** no free. Um painel ao vivo
   para o instrutor não cabe nessa plataforma.

### 3.4 Banco: SQLite — decidido

**Decisão: SQLite.** O MySQL não está disponível no plano gratuito no momento da
criação da conta, o que elimina a alternativa que esta ADR recomendava
originalmente.

A ressalva que motivava aquela recomendação continua válida e precisa ser
mitigada: o armazenamento do PythonAnywhere é em rede, e a documentação deles
desaconselha SQLite para aplicações web por causa de travamento de arquivo
(`database is locked`).

O que reduz o risco no nosso caso concreto:

- O free tier roda **um único worker**. Escrita concorrente entre processos, que
  é a origem clássica do problema, praticamente não acontece. A concorrência
  real se limita a threads do mesmo worker e a acessos feitos por console ou
  tarefa agendada enquanto o app está no ar.
- O volume é de 12 alunos, com escrita concentrada em poucos minutos por
  oficina.

O que ganhamos de volta: `sqlite3` é biblioteca padrão — nenhum driver no
`requirements.txt`, nenhuma credencial de banco para gerenciar — e o backup é um
arquivo só, o que também simplifica a migração prevista na seção 5.

**Regras de implementação obrigatórias** (o risco só é aceitável com elas):

1. `timeout` alto no `connect` (o padrão de 5s falha rápido demais); com ele o
   SQLite espera o lock liberar em vez de estourar `database is locked`.
2. **Uma conexão por requisição**, fechada ao final. Nada de conexão global
   compartilhada entre threads.
3. `PRAGMA foreign_keys = ON` em toda conexão — o SQLite ignora chave
   estrangeira por padrão.
4. **Não** habilitar `journal_mode = WAL`. O WAL depende de memória
   compartilhada via arquivo `-shm`, que é justamente o que não funciona de
   forma confiável em sistema de arquivos de rede. O journal padrão é o
   comportamento seguro aqui.
5. O arquivo `.db` mora **fora do diretório do repositório** (ex.:
   `/home/<usuário>/data/`), para não ser tocado por `git pull` nem arriscar ir
   para o controle de versão.
6. Backup por `conn.backup()` ou `sqlite3 .backup` — **nunca `cp`**, que pode
   copiar o arquivo no meio de uma transação. O free tier permite uma tarefa
   agendada diária, suficiente para isso.

**Gatilho de revisão:** se `database is locked` aparecer em produção mesmo com o
`timeout`, ou se o LTD passar a rodar turmas simultâneas, reavaliar — as saídas
são o MySQL de um plano pago ou um Postgres gerenciado externo.

### 3.5 O custo de dividir em duas origens

`gaia28.github.io` e `usuario.pythonanywhere.com` são sites distintos. Isso cria
problemas que não existiriam num deploy único:

- **Cookie de sessão não serve.** Vira cookie de terceiro: exige
  `SameSite=None; Secure` e, ainda assim, Safari e Firefox bloqueiam por padrão.
  **Decisão:** autenticação por token no cabeçalho `Authorization`, guardado em
  `localStorage`. O contraponto é exposição a XSS — o que torna obrigatório não
  injetar HTML de origem não confiável no DOM.
- **CORS** precisa ser configurado liberando exclusivamente a origem do Pages,
  nunca `*`. Requisições com `Authorization` disparam preflight `OPTIONS`.
- **Dois deploys sem atomicidade.** Mudou o contrato da API e o frontend no
  Pages ainda é o antigo por alguns minutos. **Decisão:** versionar a API em
  `/api/v1/` desde o primeiro commit.

**Alternativa considerada:** servir o frontend também pelo PythonAnywhere. Isso
elimina CORS e o problema de cookie de uma vez, ao custo de perder o CDN, o
domínio próprio gratuito e o pipeline de build já pronto — além de gastar a
escassa cota de CPU servindo arquivo estático. **Rejeitada** por isso.

---

## 4. Alternativas avaliadas

| Opção | Por que não |
| --- | --- |
| **Manter 100% estático com Tally/Google Forms** (o que o README descreve hoje) | Custo e manutenção zero, mas não resolve nenhum dos três problemas da seção 1: os e-mails seguem públicos, o acesso segue aberto e o aluno não vê a insígnia acender na hora. Só vale se abandonarmos a ideia de login. |
| **Cloudflare Workers + Turso** (SQLite gerenciado) | Free tier generoso, sem renovação manual, sem cold start. Mas implica reescrever a API em JavaScript e aprender duas plataformas novas, para atender 12 alunos. Custo de aprendizado desproporcional. |
| **Render / Railway (free)** | Cold start de dezenas de segundos ou crédito que expira, e disco efêmero. Estritamente pior que PythonAnywhere neste caso. |
| **Fly.io** | Volume persistente existe, mas exige cartão cadastrado e a operação é mais complexa. Desproporcional ao porte. |
| **VPS própria** | Controle total, mas custo mensal e responsabilidade de patching de sistema operacional que o LTD não tem quem assuma. |

---

## 5. Consequências

**Positivas**

- E-mails dos alunos saem do repositório e do HTML público.
- O acesso passa a verificar um segredo de verdade (código enviado por e-mail),
  e não a mera posse de um endereço que está publicado.
- Presença e feedback passam a ser persistidos e ficam disponíveis para o LTD
  analisar a reação às oficinas.
- O progresso segue o aluno entre aparelhos.

**Negativas / dívidas assumidas**

- Passa a existir um serviço para operar, com renovação trimestral obrigatória.
- Duas superfícies de deploy para manter em sintonia.
- Token em `localStorage` amplia a consequência de uma falha de XSS.
- Surge uma classe nova de bug (CORS/preflight) que só aparece em produção.

**Plano de saída:** se o PythonAnywhere se mostrar inviável, a API em Flask e o
esquema relacional migram para qualquer hospedagem Python com disco. O frontend
no Pages não muda — só a URL base da API. É o motivo de manter essa URL em um
único ponto de configuração do frontend.

---

## 6. Pendências antes de implementar

- [ ] Confirmar na whitelist do PythonAnywhere os domínios de saída necessários
      (API do Telegram, e o que mais o backend for chamar).
- [ ] Confirmar a cota corrente de CPU do free tier.
- [x] Decidir MySQL vs SQLite — **SQLite** (MySQL indisponível no free tier).
      Ver seção 3.4, incluindo as regras de implementação obrigatórias.
- [x] Web app criado no PythonAnywhere com **Python 3.13** e Flask, respondendo.
      Versão escolhida no maior número disponível porque o PythonAnywhere não
      permite trocar a versão de um web app existente e o free tier dá direito a
      apenas um.
- [ ] Corrigir `.github/workflows/deploy.yml`, que **hoje está com YAML
      inválido** — o step de notificação do Telegram não está indentado dentro
      da lista de steps (a partir da linha 56), além de `$ {{ secrets... }}` com
      espaço e `parse_mode=Markdonw`. O workflow não executa no estado atual, e
      este plano depende do Pages continuar publicando automaticamente.
- [ ] Remover os e-mails de `data/alunos.json` e do build estático como parte da
      mesma entrega que sobe a API — não antes (quebra o acesso atual), não
      depois (mantém a exposição).
