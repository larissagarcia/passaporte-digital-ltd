# API do Passaporte Digital

Flask + SQLite, hospedada no PythonAnywhere — que também serve a página
estática, na **mesma origem**. As decisões de arquitetura e os motivos por trás
das regras deste diretório estão em
[`docs/ADR-001-hospedagem-backend.md`](../docs/ADR-001-hospedagem-backend.md).

## Rotas do frontend

| Método | Rota | O que serve |
| --- | --- | --- |
| `GET` | `/` | `index.html` gerado por `src/generator.py` |
| `GET` | `/src/<path>` | JS e imagens das insígnias |

Em produção, `/src/` é mapeado como estático na aba Web e nem chega a passar
pela aplicação (ver abaixo).

## Rotas da API

Todas sob `/api/v1`. Respostas sempre em JSON, inclusive nos erros.

| Método | Rota | Autenticação | O que faz |
| --- | --- | --- | --- |
| `GET` | `/saude` | não | diagnóstico: banco no ar e origens liberadas |
| `POST` | `/login` | não | e-mail (aluno) ou e-mail + senha (admin) → token |
| `POST` | `/logout` | sim | invalida o token atual |
| `GET` | `/passaporte` | sim | módulos, insígnias e oficinas do aluno |
| `POST` | `/presenca` | sim | registra presença com palavra-chave e avaliação |

Autenticação é por token no cabeçalho. Com origem única, cookie `httpOnly`
passaria a ser possível e seria mais seguro — está registrado como melhoria
futura na ADR-001, seção 3.5:

```
Authorization: Bearer <token>
```

## Painel da coordenação

Em `/admin`. Exige login de administrador (e-mail + senha). Rotas em
`admin.py`, todas sob `/api/v1/admin` e protegidas por `exige_admin`.

| Método | Rota | O que faz |
| --- | --- | --- |
| `GET` | `/resumo` | totais e progresso de cada aluno |
| `GET` | `/modulos` | módulos com suas oficinas e palavras-chave |
| `POST` `PATCH` `DELETE` | `/modulos[/<id>]` | criar, editar e apagar módulo |
| `POST` `PATCH` `DELETE` | `/oficinas[/<id>]` | criar, editar e apagar oficina |
| `GET` | `/feedback` | média de estrelas e comentários por oficina |
| `GET` `POST` `PATCH` | `/usuarios[/<id>]` | listar, criar e editar usuários |
| `POST` `DELETE` | `/presencas` | lançar ou remover presença manualmente |

### Regras que o painel garante

- **Módulo com oficina e oficina com presença não são apagados** (`409`).
  Apagar uma oficina com presenças destruiria o registro de quem esteve lá.
- **Aluno não é apagado, é desativado.** As presenças continuam contando nas
  médias e o histórico da turma não some.
- **Ninguém se tranca para fora:** um admin não pode desativar a própria conta
  nem mudar o próprio papel.
- **Desativar ou rebaixar derruba as sessões abertas** daquela pessoa — sem
  isso ela continuaria entrando com o token que já tinha.
- **A palavra-chave definida no painel sobrevive ao `seed.py`.** O seed só
  define a palavra-chave ao criar a oficina; depois disso quem manda é o
  painel.

### Criar o primeiro administrador

Não há como criar o primeiro pelo painel — é preciso estar logado para usá-lo.
Use o seed, que pede a senha sem deixá-la no histórico do shell:

```bash
python api/seed.py --admin coordenacao@ltd.org
```

Os administradores seguintes podem ser criados pela aba **Usuários**.

### `POST /presenca`

```json
{ "oficina": "Modulo3_SegurancaDigital", "palavra_chave": "cadeado2026",
  "avaliacao": 4, "comentario": "opcional" }
```

Respostas: `201` criada · `400` avaliação fora de 1–5 · `403` palavra-chave
incorreta · `404` oficina inexistente · `409` presença repetida, ou oficina
ainda sem palavra-chave configurada.

## Rodar localmente

```bash
python -m venv .venv && .venv/bin/pip install -r api/requirements.txt
.venv/bin/python src/generator.py         # gera o index.html
.venv/bin/python api/seed.py              # cria ~/data/passaporte.db e popula
.venv/bin/python api/app.py               # página + API em http://localhost:5000
```

Abra `http://localhost:5000`. **Um servidor só**: a página, os arquivos de
`/src/` e a API saem todos da mesma origem, então não há CORS para configurar e
o frontend chama a API por caminho relativo.

Rode `src/generator.py` de novo sempre que mexer em `data/curso.json` ou no
template — o `index.html` é gerado no build, não a cada requisição.

## Variáveis de ambiente

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `PASSAPORTE_DB` | `~/data/passaporte.db` | caminho do banco |
| `PASSAPORTE_CORS_ORIGENS` | vazio (CORS desligado) | só se o frontend for hospedado fora |
| `PASSAPORTE_API_BASE` | vazio (mesma origem) | lido por `src/generator.py`, idem |

No PythonAnywhere o padrão de `PASSAPORTE_DB` já resolve para
`/home/<usuário>/data/passaporte.db`, que é onde a ADR manda o arquivo ficar —
não precisa configurar nada.

## Publicar no PythonAnywhere

```bash
git clone <repo> ~/passaporte-digital-ltd
cd ~/passaporte-digital-ltd && git checkout refactor/pythonanywhere
pip install -r api/requirements.txt          # com o virtualenv 3.13 ativo
python src/generator.py                      # gera o index.html
python api/seed.py                           # cria e popula o banco
```

Na aba **Web**, aponte o arquivo WSGI (*WSGI configuration file*) para a
aplicação:

```python
import sys

CAMINHO = "/home/<usuário>/passaporte-digital-ltd/api"
if CAMINHO not in sys.path:
    sys.path.insert(0, CAMINHO)

from app import app as application  # noqa: E402
```

Ainda na aba **Web**, em **Static files**, mapeie:

| URL | Directory |
| --- | --- |
| `/src/` | `/home/<usuário>/passaporte-digital-ltd/src/` |

Isso faz o servidor do PythonAnywhere entregar JS e imagens direto, sem passar
pela aplicação nem consumir a cota de CPU. As rotas `/src/<path>` em `app.py`
continuam existindo como rede de segurança e para o desenvolvimento local.

Clique em **Reload**. O `mysite/` criado pelo assistente não é mais usado.

### Atualizar depois de um push

```bash
cd ~/passaporte-digital-ltd && git pull
python src/generator.py                      # se o template ou o curso mudou
python api/seed.py                           # se data/curso.json mudou
```

E **Reload** na aba Web — o código só é recarregado aí.

### Backup

Uma tarefa agendada por dia (o que o plano gratuito permite). Nunca use `cp`:
ele pode copiar o arquivo no meio de uma transação.

```bash
sqlite3 /home/<usuário>/data/passaporte.db ".backup /home/<usuário>/data/backup-$(date +%F).db"
```

## Antes da primeira oficina

As palavras-chave nascem como `DEFINIR` em `data/curso.json`, e uma oficina
nesse estado **recusa presença** (`409`) em vez de aceitar qualquer coisa.
Troque-as e rode `python api/seed.py` de novo — ele é idempotente e avisa
quais ainda estão pendentes.
