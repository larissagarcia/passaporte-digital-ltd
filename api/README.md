# API do Passaporte Digital

Flask + SQLite, hospedada no PythonAnywhere. As decisões de arquitetura e os
motivos por trás das regras deste diretório estão em
[`docs/ADR-001-hospedagem-backend.md`](../docs/ADR-001-hospedagem-backend.md).

## Rotas

Todas sob `/api/v1`. Respostas sempre em JSON, inclusive nos erros.

| Método | Rota | Autenticação | O que faz |
| --- | --- | --- | --- |
| `GET` | `/saude` | não | diagnóstico: banco no ar e origens liberadas |
| `POST` | `/login` | não | e-mail (aluno) ou e-mail + senha (admin) → token |
| `POST` | `/logout` | sim | invalida o token atual |
| `GET` | `/passaporte` | sim | módulos, insígnias e oficinas do aluno |
| `POST` | `/presenca` | sim | registra presença com palavra-chave e avaliação |

Autenticação é por cabeçalho, não por cookie (ADR-001, seção 3.5):

```
Authorization: Bearer <token>
```

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
.venv/bin/python api/seed.py                 # cria ~/data/passaporte.db e popula
.venv/bin/python api/app.py                  # http://localhost:5000
```

Para liberar um frontend local no CORS:

```bash
export PASSAPORTE_CORS_ORIGENS="http://localhost:8000,https://gaia28.github.io"
```

## Variáveis de ambiente

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `PASSAPORTE_DB` | `~/data/passaporte.db` | caminho do banco |
| `PASSAPORTE_CORS_ORIGENS` | `https://gaia28.github.io` | origens liberadas, separadas por vírgula |

No PythonAnywhere o padrão de `PASSAPORTE_DB` já resolve para
`/home/<usuário>/data/passaporte.db`, que é onde a ADR manda o arquivo ficar —
não precisa configurar.

## Publicar no PythonAnywhere

```bash
git clone <repo> ~/passaporte-digital-ltd
cd ~/passaporte-digital-ltd && git checkout refactor/pythonanywhere
pip install -r api/requirements.txt          # com o virtualenv 3.13 ativo
python api/seed.py
```

Depois aponte o arquivo WSGI (aba **Web** → *WSGI configuration file*) para a
aplicação e clique em **Reload**:

```python
import sys

CAMINHO = "/home/<usuário>/passaporte-digital-ltd/api"
if CAMINHO not in sys.path:
    sys.path.insert(0, CAMINHO)

from app import app as application  # noqa: E402
```

O `mysite/` criado pelo assistente não é mais usado.

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
