# ADR-001 — Hospedagem: PythonAnywhere

- **Status:** aceito, com a emenda de 2026-09-24 abaixo
- **Data:** 2026-09-24
- **Branch:** `refactor/pythonanywhere`
- **Decisão:** adotar PythonAnywhere (free tier) para a API, o banco **e o
  frontend**, tudo na mesma origem.

---

## Emenda de 2026-09-24 — origem única

A decisão original mantinha o frontend no GitHub Pages e a API no
PythonAnywhere, e a seção 3.5 **rejeitava** explicitamente servir os dois do
mesmo lugar. Essa rejeição foi revertida: o frontend passa a ser servido pelo
PythonAnywhere junto com a API.

**O que motivou a troca:** os custos que a rejeição original citava — perder o
CDN e gastar cota de CPU com arquivo estático — são menores do que pareciam. O
PythonAnywhere serve arquivo estático por mapeamento na aba Web, sem passar
pelo processo da aplicação, então a cota de CPU praticamente não é afetada. Em
troca, desaparecem de uma vez o CORS, o descompasso de versão entre dois
deploys e a necessidade de configurar a URL da API.

**O que piora, e é preciso aceitar com clareza:** a renovação trimestral
obrigatória do free tier (seção 3.3, item 1) passa a derrubar **o site
inteiro**, não apenas a API. Antes, uma API fora do ar ainda deixava a página
carregar; agora é ponto único de falha. Somam-se a perda do CDN e do domínio
próprio gratuito que o Pages oferecia.

**O que muda na prática:**

| | Antes | Agora |
| --- | --- | --- |
| Frontend | GitHub Pages | PythonAnywhere, mesma origem da API |
| CORS | obrigatório, travado na origem do Pages | desligado por padrão |
| Deploys | dois, sem atomicidade | um |
| URL da API no frontend | configurada no build | caminho relativo |
| GitHub Actions | publicava no Pages | só valida que o build roda |

As seções 2, 3.1 e 3.5 abaixo foram atualizadas. O restante da ADR — banco,
autenticação em fases, riscos do free tier — segue valendo sem alteração.

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
| Frontend estático | PythonAnywhere | HTML, CSS, JS, imagens das insígnias |
| Build do frontend | PythonAnywhere, no deploy | `src/generator.py` gera `index.html` |
| API | PythonAnywhere | login, presença, feedback, progresso |
| Banco | PythonAnywhere | alunos, presenças, avaliações |
| GitHub Actions | CI | apenas valida que o build roda; não publica |

O `index.html` continua sendo gerado no deploy, e não renderizado a cada
requisição: render por requisição gastaria cota de CPU à toa, e o conteúdo da
casca só muda quando `data/curso.json` muda.

O ponto central: **`data/alunos.json` deixa de conter e-mails**. O build passa a
gerar apenas a casca da página (layout, módulos, imagens), e todo dado de aluno
passa a ser buscado da API após autenticação.

---

## 3. Tradeoffs

### 3.1 GitHub Pages + Actions — por que saiu da hospedagem

**O que perdemos ao sair do Pages** (o preço da emenda de 2026-09-24)

- CDN global e HTTPS automático sem manutenção de servidor.
- Domínio próprio gratuito — no PythonAnywhere ele exige plano pago.
- Deploy por `git push`, reversível por `git revert`, com histórico.
- Independência entre as camadas: com o Pages, a página continuava no ar
  mesmo com a API fora.

**O que já não nos servia** (limites que forçavam o backend de todo jeito)

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

### 3.5 Origem única — decisão revista

**Decisão atual:** página e API são servidas pelo mesmo domínio do
PythonAnywhere. O frontend chama a API por caminho relativo (`/api/v1/...`) e
nada precisa ser configurado.

Consequências diretas, todas a favor:

- **CORS deixa de existir.** Some uma classe inteira de bug que só aparecia em
  produção e só no console do navegador. A aplicação mantém suporte a CORS
  desligado por padrão, ligado apenas se `PASSAPORTE_CORS_ORIGENS` for definida
  — para o caso de algum dia o frontend sair daqui.
- **Um deploy só.** Acaba o descampaso de versão entre frontend e API que
  obrigava a versionar a API desde o primeiro commit. O `/api/v1/` fica assim
  mesmo: custa nada e protege se um dia houver um consumidor externo.
- **Arquivo estático não pesa na cota.** No PythonAnywhere, `/src/` é mapeado
  como estático na aba Web e servido sem passar pelo processo da aplicação. As
  rotas `/` e `/src/<path>` em `api/app.py` são o caminho de desenvolvimento e
  a rede de segurança se o mapeamento faltar.

#### Autenticação: o token continua, mas por outro motivo

A decisão original era token no cabeçalho `Authorization` porque **cookie de
sessão não funciona entre origens diferentes** — viraria cookie de terceiro,
bloqueado por padrão em Safari e Firefox. Com origem única essa razão some:
cookie passa a funcionar normalmente.

**Mantemos o token mesmo assim**, por ora: ele já está implementado e testado,
e trocar agora seria churn sem ganho imediato de funcionalidade.

Fica registrado, porém, que **cookie `httpOnly` seria mais seguro**: hoje o
token vive em `localStorage`, legível por qualquer JavaScript da página, então
uma falha de XSS entrega a sessão. Um cookie `httpOnly` não é legível por
script. Migrar exige tratar CSRF (que o token no header dispensava). Vale como
melhoria futura, não como bloqueio.

Enquanto o token estiver em `localStorage`, continua obrigatório **não injetar
no DOM HTML de origem não confiável**.

#### Como o token é emitido — entrega em duas fases

**Fase 1 (atual):** o aluno informa o e-mail e, se ele existir na base, recebe
o token. **Não há segredo verificado do lado do aluno** — quem souber o e-mail
de um colega entra como ele. É uma fraqueza conhecida e deliberadamente aceita,
para não travar a primeira entrega num fluxo de envio de e-mail.

A aceitação vale sob **uma condição inegociável**: os e-mails precisam sair do
`index.html` publicado na mesma entrega. Hoje a lista está no HTML público
(seção 1.1), então "saber o e-mail do colega" é copiar e colar da página. Sem
remover a lista, a fase 1 não representa ganho nenhum de segurança sobre o
estado atual — apenas move o mesmo problema para o servidor.

O que a fase 1 resolve mesmo assim: a lista deixa de ser publicada, o progresso
passa a ser persistido e o feedback das oficinas passa a ser coletado.

**Fase 2:** exigir um código de 6 dígitos enviado ao e-mail antes de emitir o
token. A mudança fica contida no endpoint de login — a tabela `sessoes`, o
formato do token e todas as rotas autenticadas continuam iguais. É por isso que
a sessão já nasce como tabela própria em vez de derivar do e-mail.

**Pré-requisito da fase 2:** envio de e-mail depende da whitelist de saída do
PythonAnywhere (seção 3.3, item 2). Verificar antes de planejar a fase.
#### O que se perde com a origem única

- **Ponto único de falha.** A renovação trimestral do free tier (seção 3.3,
  item 1) agora derruba o site inteiro, não só a API. É o custo mais caro desta
  emenda e o motivo de o lembrete de renovação ter dois responsáveis.
- **Sem CDN** e **sem domínio próprio gratuito**.
- A cota de CPU passa a cobrir também o tráfego da página — mitigado pelo
  mapeamento estático, que não passa pela aplicação.

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
- O e-mail deixa de ser um dado público e passa a ser algo que a pessoa precisa
  saber de antemão. Na fase 1 isso ainda **não** é autenticação de verdade (ver
  3.5) — é redução de exposição, não controle de acesso.
- Presença e feedback passam a ser persistidos e ficam disponíveis para o LTD
  analisar a reação às oficinas.
- O progresso segue o aluno entre aparelhos.

**Negativas / dívidas assumidas**

- Passa a existir um serviço para operar, com renovação trimestral obrigatória
  — e, com a origem única, essa renovação derruba o site inteiro se falhar.
- Token em `localStorage` amplia a consequência de uma falha de XSS. Com origem
  única, cookie `httpOnly` passa a ser uma alternativa viável (seção 3.5).
- **Na fase 1 o acesso continua sendo apenas o e-mail**, sem segredo
  verificado. Dívida assumida com data para quitar na fase 2 (seção 3.5).
- Perda do CDN e do domínio próprio gratuito que o GitHub Pages dava.

**Plano de saída:** se o PythonAnywhere se mostrar inviável, a API em Flask, o
esquema relacional e a pasta estática migram juntos para qualquer hospedagem
Python com disco — é uma aplicação só. O frontend usa caminho relativo, então
nada nele precisa ser reconfigurado; `PASSAPORTE_API_BASE` existe apenas para o
caso de as camadas voltarem a ser separadas.

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
- [ ] Reescrever `.github/workflows/deploy.yml`. Ele **hoje está com YAML
      inválido** — o step de notificação do Telegram não está indentado dentro
      da lista de steps (a partir da linha 56), além de `$ {{ secrets... }}` com
      espaço e `parse_mode=Markdonw`. Com a emenda de origem única ele deixa de
      publicar no Pages e passa a ser só CI: roda `src/generator.py` e falha se
      o build quebrar. Deixou de ser urgente, já que o deploy não depende mais
      dele.
- [ ] Mapear `/src/` como arquivo estático na aba Web do PythonAnywhere, para
      que a página não gaste cota de CPU (seção 3.5).
- [ ] **Remover os e-mails de `data/alunos.json` e do build estático como parte
      da mesma entrega que sobe a API** — não antes (quebra o acesso atual), não
      depois (mantém a exposição). Com o login por e-mail apenas da fase 1, este
      item deixa de ser higiene e passa a ser a condição que sustenta a decisão
      da seção 3.5. Se ele não for feito, a fase 1 não entrega segurança alguma.
