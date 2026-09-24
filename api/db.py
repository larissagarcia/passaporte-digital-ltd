"""Conexão SQLite do Passaporte Digital.

As regras deste módulo não são preferência de estilo: vêm da ADR-001, seção
3.4, e são o que torna o SQLite seguro no sistema de arquivos em rede do
PythonAnywhere. Alterar qualquer uma delas exige revisitar a ADR.

1. `timeout` alto: o padrão de 5s desiste rápido demais e estoura
   `database is locked` em vez de esperar o lock liberar.
2. Uma conexão por requisição, fechada no teardown. Nada de conexão global
   compartilhada entre threads.
3. `PRAGMA foreign_keys = ON` em toda conexão — o SQLite ignora chave
   estrangeira por padrão.
4. WAL deliberadamente NÃO habilitado: depende de memória compartilhada via
   arquivo `-shm`, que não é confiável em filesystem de rede.
5. O arquivo .db mora fora do diretório do repositório.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

# Regra 1 da ADR. Generoso de propósito: é melhor o aluno esperar do que
# receber erro no meio da oficina.
TIMEOUT_SEGUNDOS = 30

SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def caminho_banco() -> Path:
    """Onde o .db mora.

    Regra 5 da ADR: fora do repositório, para que `git pull` e `git checkout`
    não encostem no banco de produção. O padrão já fica fora em qualquer
    máquina, então esquecer de configurar não viola a regra — apenas usa outro
    diretório. Em produção, aponte PASSAPORTE_DB para /home/<usuário>/data/.
    """
    configurado = os.environ.get("PASSAPORTE_DB")
    if configurado:
        return Path(configurado).expanduser()
    return Path.home() / "data" / "passaporte.db"


def conectar(caminho: Path | None = None) -> sqlite3.Connection:
    """Abre uma conexão já configurada.

    Usada pelo Flask via `get_db()` e diretamente por scripts (seed, backup),
    que não têm contexto de aplicação.
    """
    caminho = caminho or caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)

    conexao = sqlite3.connect(
        caminho,
        timeout=TIMEOUT_SEGUNDOS,  # regra 1
        isolation_level="DEFERRED",
    )
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")  # regra 3
    # Regra 4: nenhum `PRAGMA journal_mode = WAL` aqui. É intencional.
    return conexao


# --- Integração com o Flask -------------------------------------------------


def get_db() -> sqlite3.Connection:
    """A conexão desta requisição, criada sob demanda (regra 2)."""
    if "db" not in g:
        g.db = conectar(Path(current_app.config["DB_PATH"]))
    return g.db


def fechar_db(_exc=None) -> None:
    """Fecha a conexão no fim da requisição, com ou sem erro (regra 2)."""
    conexao = g.pop("db", None)
    if conexao is not None:
        conexao.close()


@contextmanager
def transacao():
    """Agrupa escritas: confirma no sucesso, desfaz em qualquer exceção.

        with transacao() as db:
            db.execute(...)
            db.execute(...)
    """
    conexao = get_db()
    try:
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise


def criar_esquema(conexao: sqlite3.Connection) -> None:
    """Aplica schema.sql numa base vazia. Não é migração: só cria do zero."""
    conexao.executescript(SCHEMA.read_text(encoding="utf-8"))
    conexao.commit()


def init_app(app) -> None:
    """Registra o teardown e resolve o caminho do banco uma vez só."""
    app.config.setdefault("DB_PATH", str(caminho_banco()))
    app.teardown_appcontext(fechar_db)
