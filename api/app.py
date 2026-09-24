"""API do Passaporte Digital LTD.

Hospedada no PythonAnywhere; o frontend estático vive no GitHub Pages. Como
são origens diferentes, a autenticação é por token no cabeçalho
`Authorization` — cookie de sessão não funcionaria (ADR-001, seção 3.5).

Rotas, todas sob /api/v1:
    POST /login       e-mail (aluno) ou e-mail + senha (admin) -> token
    GET  /passaporte  módulos, insígnias e oficinas do aluno autenticado
    POST /presenca    registra presença numa oficina com a palavra-chave
    GET  /saude       diagnóstico, sem autenticação
"""

import hashlib
import os
import secrets
import sqlite3
from functools import wraps

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash

from db import get_db, init_app, transacao

# Origem do frontend no GitHub Pages. Sem caminho e sem barra no fim: o
# navegador compara apenas scheme + host, então o `/passaporte-digital-ltd/`
# da URL publicada não entra aqui. Derivada do dono do repositório
# (github.com/larissagarcia/passaporte-digital-ltd); confirme em
# Settings -> Pages se houver domínio próprio. Sobrescreva com
# PASSAPORTE_CORS_ORIGENS sem precisar editar este arquivo.
ORIGENS_PADRAO = "https://larissagarcia.github.io"

VALIDADE_ALUNO = "+30 days"  # aluno volta a cada oficina; relogar toda vez irrita
VALIDADE_ADMIN = "+12 hours"  # admin mexe em dado de todo mundo


# --- Autenticação -----------------------------------------------------------


def _hash(token: str) -> str:
    """O banco guarda só o hash — ver comentário da tabela `sessoes`."""
    return hashlib.sha256(token.encode()).hexdigest()


def erro(mensagem: str, status: int, **extra):
    return jsonify({"erro": mensagem, **extra}), status


def exige_login(funcao):
    """Resolve o token do header e põe o usuário em `g.usuario`."""

    @wraps(funcao)
    def wrapper(*args, **kwargs):
        cabecalho = request.headers.get("Authorization", "")
        if not cabecalho.startswith("Bearer "):
            return erro("Envie o token em Authorization: Bearer <token>.", 401)

        token = cabecalho.removeprefix("Bearer ").strip()
        if not token:
            return erro("Token vazio.", 401)

        usuario = get_db().execute(
            """SELECT u.id, u.nome, u.email, u.papel
                 FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id
                WHERE s.token_hash = ?
                  AND s.expira_em > datetime('now')
                  AND u.ativo = 1""",
            (_hash(token),),
        ).fetchone()

        if usuario is None:
            return erro("Sessão inválida ou expirada. Entre novamente.", 401)

        g.usuario = usuario
        return funcao(*args, **kwargs)

    return wrapper


def emitir_token(usuario_id: int, validade: str) -> str:
    token = secrets.token_urlsafe(32)
    with transacao() as db:
        db.execute("DELETE FROM sessoes WHERE expira_em <= datetime('now')")
        db.execute(
            "INSERT INTO sessoes (token_hash, usuario_id, expira_em)"
            " VALUES (?, ?, datetime('now', ?))",
            (_hash(token), usuario_id, validade),
        )
    return token


# --- Aplicação --------------------------------------------------------------


def create_app() -> Flask:
    app = Flask(__name__)
    init_app(app)

    origens = [
        o.strip()
        for o in os.environ.get("PASSAPORTE_CORS_ORIGENS", ORIGENS_PADRAO).split(",")
        if o.strip()
    ]
    # Só /api/*, só as origens listadas. Nunca "*": com Authorization no header
    # isso libera a API para qualquer site.
    CORS(app, resources={r"/api/*": {"origins": origens}},
         allow_headers=["Content-Type", "Authorization"], max_age=3600)

    @app.get("/api/v1/saude")
    def saude():
        try:
            oficinas = get_db().execute("SELECT COUNT(*) c FROM oficinas").fetchone()["c"]
        except sqlite3.Error as e:
            return erro(f"Banco indisponível: {e}", 503)
        return jsonify({"ok": True, "oficinas": oficinas, "origens_liberadas": origens})

    @app.post("/api/v1/login")
    def login():
        dados = request.get_json(silent=True) or {}
        email = (dados.get("email") or "").strip().lower()
        senha = dados.get("senha") or ""

        if not email:
            return erro("Informe o e-mail.", 400)

        usuario = get_db().execute(
            "SELECT id, nome, email, papel, senha_hash FROM usuarios"
            " WHERE email = ? AND ativo = 1",
            (email,),
        ).fetchone()

        # Mensagem propositalmente igual para admin e aluno: não revela papel.
        if usuario is None:
            return erro("E-mail não encontrado. Confira com a coordenação do LTD.", 404)

        if usuario["papel"] == "admin":
            if not senha or not check_password_hash(usuario["senha_hash"], senha):
                return erro("Credenciais inválidas.", 401)
            validade = VALIDADE_ADMIN
        else:
            # FASE 1: nenhum segredo é verificado — basta o e-mail existir.
            # Fraqueza conhecida e aceita; ver ADR-001, seção 3.5. A fase 2
            # exige aqui um código de 6 dígitos e nada mais muda.
            validade = VALIDADE_ALUNO

        token = emitir_token(usuario["id"], validade)
        return jsonify({
            "token": token,
            "usuario": {"nome": usuario["nome"], "email": usuario["email"],
                        "papel": usuario["papel"]},
        })

    @app.post("/api/v1/logout")
    @exige_login
    def logout():
        token = request.headers["Authorization"].removeprefix("Bearer ").strip()
        with transacao() as db:
            db.execute("DELETE FROM sessoes WHERE token_hash = ?", (_hash(token),))
        return jsonify({"ok": True})

    @app.get("/api/v1/passaporte")
    @exige_login
    def passaporte():
        db = get_db()
        usuario_id = g.usuario["id"]

        insignias = db.execute(
            """SELECT modulo_id, modulo_numero, modulo_nome, oficinas_total,
                      oficinas_concluidas, conquistada, imagem, conquistada_em
                 FROM insignias WHERE usuario_id = ? ORDER BY modulo_numero""",
            (usuario_id,),
        ).fetchall()

        oficinas = db.execute(
            """SELECT o.id, o.modulo_id, o.slug, o.ordem, o.nome, o.data,
                      p.id IS NOT NULL AS presente,
                      p.avaliacao, p.registrada_em
                 FROM oficinas o
                 LEFT JOIN presencas p
                        ON p.oficina_id = o.id AND p.usuario_id = ?
                ORDER BY o.modulo_id, o.ordem""",
            (usuario_id,),
        ).fetchall()

        por_modulo: dict[int, list] = {}
        for o in oficinas:
            por_modulo.setdefault(o["modulo_id"], []).append({
                "slug": o["slug"],
                "ordem": o["ordem"],
                "nome": o["nome"],
                "data": o["data"],
                "presente": bool(o["presente"]),
                "avaliacao": o["avaliacao"],
                "registrada_em": o["registrada_em"],
            })

        conquistadas = sum(i["conquistada"] for i in insignias)
        total = len(insignias)

        return jsonify({
            "aluno": {"nome": g.usuario["nome"], "email": g.usuario["email"]},
            "progresso": {
                "conquistadas": conquistadas,
                "total": total,
                "percentual": round(conquistadas / total * 100) if total else 0,
            },
            "modulos": [{
                "numero": i["modulo_numero"],
                "nome": i["modulo_nome"],
                "imagem": i["imagem"],
                "status": "conquistada" if i["conquistada"] else "bloqueado",
                "oficinas_concluidas": i["oficinas_concluidas"],
                "oficinas_total": i["oficinas_total"],
                "conquistada_em": i["conquistada_em"],
                "oficinas": por_modulo.get(i["modulo_id"], []),
            } for i in insignias],
        })

    @app.post("/api/v1/presenca")
    @exige_login
    def registrar_presenca():
        dados = request.get_json(silent=True) or {}
        slug = (dados.get("oficina") or "").strip()
        palavra = (dados.get("palavra_chave") or "").strip()
        avaliacao = dados.get("avaliacao")
        comentario = (dados.get("comentario") or "").strip() or None

        if not slug:
            return erro("Informe a oficina.", 400)
        if not palavra:
            return erro("Informe a palavra-chave da oficina.", 400)
        if not isinstance(avaliacao, int) or not 1 <= avaliacao <= 5:
            return erro("A avaliação deve ser um número inteiro de 1 a 5.", 400)

        db = get_db()
        oficina = db.execute(
            "SELECT id, modulo_id, nome, palavra_chave FROM oficinas WHERE slug = ?",
            (slug,),
        ).fetchone()
        if oficina is None:
            return erro("Oficina não encontrada.", 404)

        # Oficina não configurada não pode validar presença: 'DEFINIR' é o valor
        # que o seed deixa, e aceitá-lo liberaria presença para qualquer um.
        if oficina["palavra_chave"].upper() == "DEFINIR":
            return erro(
                "Esta oficina ainda não teve a palavra-chave configurada. "
                "Avise a coordenação do LTD.", 409)

        # COLLATE NOCASE na coluna já torna a comparação insensível a maiúscula.
        confere = db.execute(
            "SELECT 1 FROM oficinas WHERE id = ? AND palavra_chave = ?",
            (oficina["id"], palavra),
        ).fetchone()
        if confere is None:
            return erro("Palavra-chave incorreta.", 403)

        try:
            with transacao() as conexao:
                conexao.execute(
                    "INSERT INTO presencas (usuario_id, oficina_id, avaliacao, comentario)"
                    " VALUES (?, ?, ?, ?)",
                    (g.usuario["id"], oficina["id"], avaliacao, comentario),
                )
        except sqlite3.IntegrityError:
            return erro("Sua presença nesta oficina já foi registrada.", 409)

        # Devolve o estado do módulo para a tela acender a insígnia na hora.
        insignia = db.execute(
            """SELECT modulo_numero, modulo_nome, oficinas_concluidas,
                      oficinas_total, conquistada, imagem
                 FROM insignias WHERE usuario_id = ? AND modulo_id = ?""",
            (g.usuario["id"], oficina["modulo_id"]),
        ).fetchone()

        return jsonify({
            "ok": True,
            "oficina": oficina["nome"],
            "modulo": {
                "numero": insignia["modulo_numero"],
                "nome": insignia["modulo_nome"],
                "imagem": insignia["imagem"],
                "oficinas_concluidas": insignia["oficinas_concluidas"],
                "oficinas_total": insignia["oficinas_total"],
                "insignia_conquistada": bool(insignia["conquistada"]),
            },
        }), 201

    # Erros em JSON: o frontend consome sempre JSON, inclusive no caminho ruim.
    @app.errorhandler(404)
    def nao_encontrado(_e):
        return erro("Rota não encontrada.", 404)

    @app.errorhandler(405)
    def metodo_invalido(_e):
        return erro("Método não permitido para esta rota.", 405)

    @app.errorhandler(500)
    def erro_interno(_e):
        return erro("Erro interno. Tente novamente.", 500)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
