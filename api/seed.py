"""Popula o banco a partir dos arquivos em data/.

    python api/seed.py                      # cria o esquema se faltar e popula
    python api/seed.py --admin ana@ltd.org  # cria/atualiza um administrador

Fontes:
  data/curso.json   -> modulos + oficinas
  data/alunos.json  -> usuarios + presencas (dos slugs já registrados no campo
                       `insignias`, que na prática sempre foram oficinas)

É idempotente: rodar de novo atualiza o que mudou e não duplica nada. A senha
do admin nunca vem por argumento — seria gravada no histórico do shell.
"""

import argparse
import getpass
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import caminho_banco, conectar, criar_esquema  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CURSO = RAIZ / "data" / "curso.json"
ALUNOS = RAIZ / "data" / "alunos.json"


def carregar_curso(conexao: sqlite3.Connection) -> dict[str, int]:
    """Insere ou atualiza módulos e oficinas. Devolve slug -> oficina_id."""
    curso = json.loads(CURSO.read_text(encoding="utf-8"))
    ids_por_slug: dict[str, int] = {}

    for modulo in curso["modulos"]:
        conexao.execute(
            """INSERT INTO modulos (numero, nome, descricao, imagem_conquistada, imagem_pendente)
                    VALUES (:numero, :nome, :descricao, :imagem_conquistada, :imagem_pendente)
               ON CONFLICT (numero) DO UPDATE SET
                    nome = excluded.nome,
                    descricao = excluded.descricao,
                    imagem_conquistada = excluded.imagem_conquistada,
                    imagem_pendente = excluded.imagem_pendente""",
            modulo,
        )
        modulo_id = conexao.execute(
            "SELECT id FROM modulos WHERE numero = ?", (modulo["numero"],)
        ).fetchone()["id"]

        for oficina in modulo["oficinas"]:
            conexao.execute(
                """INSERT INTO oficinas (modulo_id, slug, ordem, nome, descricao, data, palavra_chave)
                        VALUES (:modulo_id, :slug, :ordem, :nome, :descricao, :data, :palavra_chave)
                   ON CONFLICT (slug) DO UPDATE SET
                        modulo_id = excluded.modulo_id,
                        ordem = excluded.ordem,
                        nome = excluded.nome,
                        descricao = excluded.descricao,
                        data = excluded.data,
                        palavra_chave = excluded.palavra_chave""",
                {**oficina, "modulo_id": modulo_id},
            )
            ids_por_slug[oficina["slug"]] = conexao.execute(
                "SELECT id FROM oficinas WHERE slug = ?", (oficina["slug"],)
            ).fetchone()["id"]

    return ids_por_slug


def carregar_alunos(conexao: sqlite3.Connection, ids_por_slug: dict[str, int]) -> list[str]:
    """Insere alunos e converte os slugs de `insignias` em presenças.

    Devolve os slugs que não existem em curso.json, se houver.
    """
    alunos = json.loads(ALUNOS.read_text(encoding="utf-8"))
    desconhecidos: list[str] = []

    for aluno in alunos:
        email = aluno["email"].strip().lower()
        conexao.execute(
            """INSERT INTO usuarios (nome, email) VALUES (?, ?)
               ON CONFLICT (email) DO UPDATE SET nome = excluded.nome""",
            (aluno["nome"].strip(), email),
        )
        usuario_id = conexao.execute(
            "SELECT id FROM usuarios WHERE email = ?", (email,)
        ).fetchone()["id"]

        for slug in aluno.get("insignias", []):
            oficina_id = ids_por_slug.get(slug)
            if oficina_id is None:
                desconhecidos.append(f"{email}: {slug}")
                continue
            # Sem avaliação: esses registros são anteriores ao backend e não
            # temos as estrelas. NULL é honesto; zero seria inventar dado.
            conexao.execute(
                """INSERT INTO presencas (usuario_id, oficina_id) VALUES (?, ?)
                   ON CONFLICT (usuario_id, oficina_id) DO NOTHING""",
                (usuario_id, oficina_id),
            )

    return desconhecidos


def criar_admin(conexao: sqlite3.Connection, email: str) -> None:
    from werkzeug.security import generate_password_hash

    email = email.strip().lower()
    existente = conexao.execute(
        "SELECT papel FROM usuarios WHERE email = ?", (email,)
    ).fetchone()
    if existente and existente["papel"] == "aluno":
        sys.exit(f"erro: {email} já existe como aluno. Use outro e-mail para o admin.")

    nome = input("Nome do administrador: ").strip()
    senha = getpass.getpass("Senha: ")
    if len(senha) < 8:
        sys.exit("erro: use pelo menos 8 caracteres.")
    if senha != getpass.getpass("Repita a senha: "):
        sys.exit("erro: as senhas não conferem.")

    conexao.execute(
        """INSERT INTO usuarios (nome, email, papel, senha_hash) VALUES (?, ?, 'admin', ?)
           ON CONFLICT (email) DO UPDATE SET nome = excluded.nome, senha_hash = excluded.senha_hash""",
        (nome, email, generate_password_hash(senha)),
    )
    print(f"admin: {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Popula o banco do Passaporte Digital.")
    parser.add_argument("--admin", metavar="EMAIL", help="cria ou atualiza um administrador")
    args = parser.parse_args()

    caminho = caminho_banco()
    novo = not caminho.exists()
    conexao = conectar(caminho)

    if novo:
        criar_esquema(conexao)

    with conexao:  # commit no sucesso, rollback em exceção
        ids_por_slug = carregar_curso(conexao)
        desconhecidos = carregar_alunos(conexao, ids_por_slug)
        if args.admin:
            criar_admin(conexao, args.admin)

    def contar(tabela: str) -> int:
        return conexao.execute(f"SELECT COUNT(*) c FROM {tabela}").fetchone()["c"]
    print(f"banco: {caminho}{' (criado agora)' if novo else ''}")
    print(f"  módulos:   {contar('modulos')}")
    print(f"  oficinas:  {contar('oficinas')}")
    print(f"  alunos:    {contar('usuarios')}")
    print(f"  presenças: {contar('presencas')}")

    if desconhecidos:
        print("\nAVISO: slugs em alunos.json que não existem em curso.json:")
        for item in desconhecidos:
            print(f"  {item}")

    pendentes = conexao.execute(
        "SELECT slug FROM oficinas WHERE palavra_chave = 'DEFINIR' ORDER BY id"
    ).fetchall()
    if pendentes:
        print(f"\nAVISO: {len(pendentes)} oficina(s) ainda com palavra-chave 'DEFINIR'.")
        print("Troque em data/curso.json antes da oficina acontecer:")
        for linha in pendentes:
            print(f"  {linha['slug']}")

    conexao.close()


if __name__ == "__main__":
    main()
