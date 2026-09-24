"""Autenticação compartilhada entre a API do aluno e o painel de admin.

O token vai no cabeçalho `Authorization: Bearer <token>` e o banco guarda
apenas o SHA-256 dele (ver a tabela `sessoes` em schema.sql).
"""

import hashlib
import secrets
from functools import wraps

from flask import g, jsonify, request

from db import get_db, transacao

VALIDADE_ALUNO = "+30 days"   # aluno volta a cada oficina; relogar toda vez irrita
VALIDADE_ADMIN = "+12 hours"  # admin mexe em dado de todo mundo


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def erro(mensagem: str, status: int, **extra):
    return jsonify({"erro": mensagem, **extra}), status


def emitir_token(usuario_id: int, validade: str) -> str:
    token = secrets.token_urlsafe(32)
    with transacao() as db:
        db.execute("DELETE FROM sessoes WHERE expira_em <= datetime('now')")
        db.execute(
            "INSERT INTO sessoes (token_hash, usuario_id, expira_em)"
            " VALUES (?, ?, datetime('now', ?))",
            (hash_token(token), usuario_id, validade),
        )
    return token


def _resolver_usuario():
    cabecalho = request.headers.get("Authorization", "")
    if not cabecalho.startswith("Bearer "):
        return None, erro("Envie o token em Authorization: Bearer <token>.", 401)

    token = cabecalho.removeprefix("Bearer ").strip()
    if not token:
        return None, erro("Token vazio.", 401)

    usuario = get_db().execute(
        """SELECT u.id, u.nome, u.email, u.papel
             FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.token_hash = ?
              AND s.expira_em > datetime('now')
              AND u.ativo = 1""",
        (hash_token(token),),
    ).fetchone()

    if usuario is None:
        return None, erro("Sessão inválida ou expirada. Entre novamente.", 401)

    return usuario, None


def exige_login(funcao):
    """Qualquer usuário autenticado, aluno ou admin."""

    @wraps(funcao)
    def wrapper(*args, **kwargs):
        usuario, falha = _resolver_usuario()
        if falha:
            return falha
        g.usuario = usuario
        return funcao(*args, **kwargs)

    return wrapper


def exige_admin(funcao):
    """Só administrador.

    Responde 403 (e não 404) quando um aluno autenticado tenta acessar: ele já
    provou quem é, então esconder a existência da rota não protege nada e só
    confunde quem está diagnosticando.
    """

    @wraps(funcao)
    def wrapper(*args, **kwargs):
        usuario, falha = _resolver_usuario()
        if falha:
            return falha
        if usuario["papel"] != "admin":
            return erro("Esta área é restrita à coordenação.", 403)
        g.usuario = usuario
        return funcao(*args, **kwargs)

    return wrapper
