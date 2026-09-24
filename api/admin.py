"""Rotas do painel da coordenação, todas sob /api/v1/admin e só para admin.

Regras que valem para o arquivo inteiro:

- Módulo e oficina só podem ser apagados se nada depender deles. Apagar uma
  oficina com presenças destruiria o registro de quem esteve lá, então a
  resposta é 409 explicando o motivo em vez de um erro de banco.
- Aluno não é apagado, é desativado: as presenças dele continuam contando nas
  médias das oficinas, e o histórico da turma não some.
- Senha só existe para admin, e é gravada como hash. O CHECK do schema impede
  aluno com senha e admin sem senha; aqui a validação acontece antes, para o
  erro chegar legível na tela.
"""

import re
import sqlite3

from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from auth import erro, exige_admin
from db import get_db, transacao

admin = Blueprint("admin", __name__, url_prefix="/api/v1/admin")

SENHA_MINIMA = 8
FORMATO_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FORMATO_SLUG = re.compile(r"^[A-Za-z0-9_-]{3,80}$")


def corpo():
    return request.get_json(silent=True) or {}


def texto(dados, campo, obrigatorio=False, maximo=200):
    valor = (dados.get(campo) or "").strip()
    if obrigatorio and not valor:
        raise ValueError(f"Informe {campo.replace('_', ' ')}.")
    if len(valor) > maximo:
        raise ValueError(f"O campo {campo.replace('_', ' ')} é longo demais.")
    return valor


# --- Visão geral ------------------------------------------------------------


@admin.get("/resumo")
@exige_admin
def resumo():
    """Números que a coordenação olha primeiro."""
    db = get_db()

    alunos = db.execute(
        """SELECT u.id, u.nome, u.email, u.ativo,
                  COALESCE(SUM(i.conquistada), 0) AS insignias,
                  COALESCE(SUM(i.oficinas_concluidas), 0) AS oficinas_feitas
             FROM usuarios u
             LEFT JOIN insignias i ON i.usuario_id = u.id
            WHERE u.papel = 'aluno'
            GROUP BY u.id
            ORDER BY insignias DESC, u.nome"""
    ).fetchall()

    total_oficinas = db.execute("SELECT COUNT(*) c FROM oficinas").fetchone()["c"]
    total_modulos = db.execute("SELECT COUNT(*) c FROM modulos").fetchone()["c"]
    sem_chave = db.execute(
        "SELECT COUNT(*) c FROM oficinas WHERE palavra_chave = 'DEFINIR'"
    ).fetchone()["c"]

    return jsonify({
        "totais": {
            "alunos": len([a for a in alunos if a["ativo"]]),
            "alunos_inativos": len([a for a in alunos if not a["ativo"]]),
            "modulos": total_modulos,
            "oficinas": total_oficinas,
            "oficinas_sem_palavra_chave": sem_chave,
        },
        "alunos": [{
            "id": a["id"],
            "nome": a["nome"],
            "email": a["email"],
            "ativo": bool(a["ativo"]),
            "insignias": a["insignias"],
            "oficinas_feitas": a["oficinas_feitas"],
            "insignias_total": total_modulos,
            "oficinas_total": total_oficinas,
        } for a in alunos],
    })


# --- Módulos ----------------------------------------------------------------


@admin.get("/modulos")
@exige_admin
def listar_modulos():
    db = get_db()
    modulos = db.execute("SELECT * FROM modulos ORDER BY numero").fetchall()
    oficinas = db.execute(
        """SELECT o.*, COUNT(p.id) AS presencas
             FROM oficinas o LEFT JOIN presencas p ON p.oficina_id = o.id
            GROUP BY o.id ORDER BY o.modulo_id, o.ordem"""
    ).fetchall()

    por_modulo = {}
    for o in oficinas:
        por_modulo.setdefault(o["modulo_id"], []).append({
            "id": o["id"],
            "slug": o["slug"],
            "ordem": o["ordem"],
            "nome": o["nome"],
            "descricao": o["descricao"],
            "data": o["data"],
            "palavra_chave": o["palavra_chave"],
            "configurada": o["palavra_chave"].upper() != "DEFINIR",
            "presencas": o["presencas"],
        })

    return jsonify({"modulos": [{
        "id": m["id"],
        "numero": m["numero"],
        "nome": m["nome"],
        "descricao": m["descricao"],
        "imagem_conquistada": m["imagem_conquistada"],
        "imagem_pendente": m["imagem_pendente"],
        "oficinas": por_modulo.get(m["id"], []),
    } for m in modulos]})


@admin.post("/modulos")
@exige_admin
def criar_modulo():
    dados = corpo()
    try:
        nome = texto(dados, "nome", obrigatorio=True)
        descricao = texto(dados, "descricao", maximo=1000)
        numero = dados.get("numero")
        if not isinstance(numero, int) or numero < 1:
            return erro("O número do módulo deve ser um inteiro a partir de 1.", 400)
        conquistada = texto(dados, "imagem_conquistada", obrigatorio=True, maximo=300)
        pendente = texto(dados, "imagem_pendente", obrigatorio=True, maximo=300)
    except ValueError as e:
        return erro(str(e), 400)

    try:
        with transacao() as db:
            cur = db.execute(
                """INSERT INTO modulos (numero, nome, descricao, imagem_conquistada, imagem_pendente)
                   VALUES (?, ?, ?, ?, ?)""",
                (numero, nome, descricao, conquistada, pendente),
            )
    except sqlite3.IntegrityError:
        return erro(f"Já existe um módulo com o número {numero}.", 409)

    return jsonify({"ok": True, "id": cur.lastrowid}), 201


@admin.patch("/modulos/<int:modulo_id>")
@exige_admin
def editar_modulo(modulo_id):
    dados = corpo()
    db = get_db()
    if db.execute("SELECT 1 FROM modulos WHERE id = ?", (modulo_id,)).fetchone() is None:
        return erro("Módulo não encontrado.", 404)

    campos, valores = [], []
    for campo in ("nome", "descricao", "imagem_conquistada", "imagem_pendente"):
        if campo in dados:
            try:
                valor = texto(dados, campo, obrigatorio=(campo == "nome"), maximo=1000)
            except ValueError as e:
                return erro(str(e), 400)
            campos.append(f"{campo} = ?")
            valores.append(valor)

    if "numero" in dados:
        if not isinstance(dados["numero"], int) or dados["numero"] < 1:
            return erro("O número do módulo deve ser um inteiro a partir de 1.", 400)
        campos.append("numero = ?")
        valores.append(dados["numero"])

    if not campos:
        return erro("Nada para alterar.", 400)

    try:
        with transacao() as conexao:
            conexao.execute(
                f"UPDATE modulos SET {', '.join(campos)} WHERE id = ?",
                (*valores, modulo_id),
            )
    except sqlite3.IntegrityError:
        return erro("Já existe outro módulo com esse número.", 409)

    return jsonify({"ok": True})


@admin.delete("/modulos/<int:modulo_id>")
@exige_admin
def apagar_modulo(modulo_id):
    db = get_db()
    if db.execute("SELECT 1 FROM modulos WHERE id = ?", (modulo_id,)).fetchone() is None:
        return erro("Módulo não encontrado.", 404)

    oficinas = db.execute(
        "SELECT COUNT(*) c FROM oficinas WHERE modulo_id = ?", (modulo_id,)
    ).fetchone()["c"]
    if oficinas:
        return erro(
            f"Este módulo tem {oficinas} oficina(s). Apague ou mova as oficinas antes.",
            409)

    with transacao() as conexao:
        conexao.execute("DELETE FROM modulos WHERE id = ?", (modulo_id,))
    return jsonify({"ok": True})


# --- Oficinas ---------------------------------------------------------------


def _validar_oficina(dados, criando):
    campos = {}

    if criando or "slug" in dados:
        slug = texto(dados, "slug", obrigatorio=criando, maximo=80)
        if slug and not FORMATO_SLUG.match(slug):
            raise ValueError("O identificador aceita letras, números, hífen e "
                             "sublinhado, com 3 a 80 caracteres.")
        if slug:
            campos["slug"] = slug

    if criando or "nome" in dados:
        campos["nome"] = texto(dados, "nome", obrigatorio=criando)

    if "descricao" in dados:
        campos["descricao"] = texto(dados, "descricao", maximo=1000)

    if criando or "palavra_chave" in dados:
        chave = texto(dados, "palavra_chave", obrigatorio=criando, maximo=100)
        if chave:
            campos["palavra_chave"] = chave

    if "data" in dados:
        data = (dados.get("data") or "").strip()
        if data and not FORMATO_DATA.match(data):
            raise ValueError("A data deve estar no formato AAAA-MM-DD.")
        campos["data"] = data or None

    if criando or "ordem" in dados:
        ordem = dados.get("ordem", 1)
        if not isinstance(ordem, int) or ordem < 1:
            raise ValueError("A ordem deve ser um inteiro a partir de 1.")
        campos["ordem"] = ordem

    return campos


@admin.post("/oficinas")
@exige_admin
def criar_oficina():
    dados = corpo()
    modulo_id = dados.get("modulo_id")
    if not isinstance(modulo_id, int):
        return erro("Informe o módulo da oficina.", 400)

    db = get_db()
    if db.execute("SELECT 1 FROM modulos WHERE id = ?", (modulo_id,)).fetchone() is None:
        return erro("Módulo não encontrado.", 404)

    try:
        campos = _validar_oficina(dados, criando=True)
    except ValueError as e:
        return erro(str(e), 400)

    campos["modulo_id"] = modulo_id
    colunas = ", ".join(campos)
    marcadores = ", ".join("?" for _ in campos)

    try:
        with transacao() as conexao:
            cur = conexao.execute(
                f"INSERT INTO oficinas ({colunas}) VALUES ({marcadores})",
                tuple(campos.values()),
            )
    except sqlite3.IntegrityError as e:
        if "slug" in str(e):
            return erro("Já existe uma oficina com esse identificador.", 409)
        return erro("Já existe uma oficina com essa ordem neste módulo.", 409)

    return jsonify({"ok": True, "id": cur.lastrowid}), 201


@admin.patch("/oficinas/<int:oficina_id>")
@exige_admin
def editar_oficina(oficina_id):
    """Onde a palavra-chave do dia é definida."""
    dados = corpo()
    db = get_db()
    if db.execute("SELECT 1 FROM oficinas WHERE id = ?", (oficina_id,)).fetchone() is None:
        return erro("Oficina não encontrada.", 404)

    try:
        campos = _validar_oficina(dados, criando=False)
    except ValueError as e:
        return erro(str(e), 400)

    if "modulo_id" in dados:
        if db.execute("SELECT 1 FROM modulos WHERE id = ?",
                      (dados["modulo_id"],)).fetchone() is None:
            return erro("Módulo não encontrado.", 404)
        campos["modulo_id"] = dados["modulo_id"]

    if not campos:
        return erro("Nada para alterar.", 400)

    atribuicoes = ", ".join(f"{c} = ?" for c in campos)
    try:
        with transacao() as conexao:
            conexao.execute(
                f"UPDATE oficinas SET {atribuicoes} WHERE id = ?",
                (*campos.values(), oficina_id),
            )
    except sqlite3.IntegrityError:
        return erro("Identificador ou ordem já usados por outra oficina.", 409)

    return jsonify({"ok": True})


@admin.delete("/oficinas/<int:oficina_id>")
@exige_admin
def apagar_oficina(oficina_id):
    db = get_db()
    if db.execute("SELECT 1 FROM oficinas WHERE id = ?", (oficina_id,)).fetchone() is None:
        return erro("Oficina não encontrada.", 404)

    presencas = db.execute(
        "SELECT COUNT(*) c FROM presencas WHERE oficina_id = ?", (oficina_id,)
    ).fetchone()["c"]
    if presencas:
        return erro(
            f"Esta oficina tem {presencas} presença(s) registrada(s). "
            "Apagá-la destruiria esse histórico.", 409)

    with transacao() as conexao:
        conexao.execute("DELETE FROM oficinas WHERE id = ?", (oficina_id,))
    return jsonify({"ok": True})


# --- Feedback ---------------------------------------------------------------


@admin.get("/feedback")
@exige_admin
def feedback():
    """Média de estrelas e comentários, por oficina."""
    db = get_db()

    resumos = db.execute(
        """SELECT o.id, o.nome, m.numero AS modulo_numero,
                  COUNT(p.id) AS presencas,
                  COUNT(p.avaliacao) AS avaliacoes,
                  ROUND(AVG(p.avaliacao), 2) AS media
             FROM oficinas o
             JOIN modulos m ON m.id = o.modulo_id
             LEFT JOIN presencas p ON p.oficina_id = o.id
            GROUP BY o.id ORDER BY m.numero, o.ordem"""
    ).fetchall()

    comentarios = db.execute(
        """SELECT o.id AS oficina_id, u.nome, p.avaliacao, p.comentario, p.registrada_em
             FROM presencas p
             JOIN oficinas o ON o.id = p.oficina_id
             JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.comentario IS NOT NULL AND TRIM(p.comentario) <> ''
            ORDER BY p.registrada_em DESC"""
    ).fetchall()

    por_oficina = {}
    for c in comentarios:
        por_oficina.setdefault(c["oficina_id"], []).append({
            "aluno": c["nome"],
            "avaliacao": c["avaliacao"],
            "comentario": c["comentario"],
            "em": c["registrada_em"],
        })

    return jsonify({"oficinas": [{
        "id": r["id"],
        "nome": r["nome"],
        "modulo_numero": r["modulo_numero"],
        "presencas": r["presencas"],
        "avaliacoes": r["avaliacoes"],
        "media": r["media"],
        "comentarios": por_oficina.get(r["id"], []),
    } for r in resumos]})


# --- Usuários ---------------------------------------------------------------


@admin.get("/usuarios")
@exige_admin
def listar_usuarios():
    usuarios = get_db().execute(
        "SELECT id, nome, email, papel, ativo, criado_em FROM usuarios ORDER BY papel, nome"
    ).fetchall()
    return jsonify({"usuarios": [{
        "id": u["id"], "nome": u["nome"], "email": u["email"],
        "papel": u["papel"], "ativo": bool(u["ativo"]), "criado_em": u["criado_em"],
    } for u in usuarios]})


@admin.post("/usuarios")
@exige_admin
def criar_usuario():
    """Cria aluno (sem senha) ou administrador (com senha)."""
    dados = corpo()
    try:
        nome = texto(dados, "nome", obrigatorio=True)
        email = texto(dados, "email", obrigatorio=True).lower()
    except ValueError as e:
        return erro(str(e), 400)

    if "@" not in email or "." not in email.split("@")[-1]:
        return erro("E-mail inválido.", 400)

    papel = (dados.get("papel") or "aluno").strip()
    if papel not in ("aluno", "admin"):
        return erro("O papel deve ser 'aluno' ou 'admin'.", 400)

    senha_hash = None
    if papel == "admin":
        senha = dados.get("senha") or ""
        if len(senha) < SENHA_MINIMA:
            return erro(f"A senha do administrador precisa de pelo menos "
                        f"{SENHA_MINIMA} caracteres.", 400)
        senha_hash = generate_password_hash(senha)
    elif dados.get("senha"):
        return erro("Aluno não tem senha: o acesso dele é pelo e-mail.", 400)

    try:
        with transacao() as db:
            cur = db.execute(
                "INSERT INTO usuarios (nome, email, papel, senha_hash) VALUES (?, ?, ?, ?)",
                (nome, email, papel, senha_hash),
            )
    except sqlite3.IntegrityError:
        return erro("Já existe um usuário com esse e-mail.", 409)

    return jsonify({"ok": True, "id": cur.lastrowid}), 201


@admin.patch("/usuarios/<int:usuario_id>")
@exige_admin
def editar_usuario(usuario_id):
    dados = corpo()
    db = get_db()
    usuario = db.execute(
        "SELECT id, papel, ativo FROM usuarios WHERE id = ?", (usuario_id,)
    ).fetchone()
    if usuario is None:
        return erro("Usuário não encontrado.", 404)

    papel_novo = (dados.get("papel") or usuario["papel"]).strip()
    if papel_novo not in ("aluno", "admin"):
        return erro("O papel deve ser 'aluno' ou 'admin'.", 400)

    # Um admin não pode se desativar nem se rebaixar: ficaria trancado para fora
    # do próprio painel, e se for o último admin ninguém mais entra.
    if usuario_id == g.usuario["id"]:
        if dados.get("ativo") is False:
            return erro("Você não pode desativar a própria conta.", 409)
        if papel_novo != usuario["papel"]:
            return erro("Você não pode mudar o próprio papel.", 409)

    if usuario["papel"] == "admin" and (papel_novo == "aluno" or dados.get("ativo") is False):
        restantes = db.execute(
            "SELECT COUNT(*) c FROM usuarios WHERE papel = 'admin' AND ativo = 1 AND id <> ?",
            (usuario_id,),
        ).fetchone()["c"]
        if restantes == 0:
            return erro("Este é o último administrador ativo. "
                        "Crie outro antes de alterar este.", 409)

    campos, valores = [], []

    if "nome" in dados:
        try:
            campos.append("nome = ?")
            valores.append(texto(dados, "nome", obrigatorio=True))
        except ValueError as e:
            return erro(str(e), 400)

    if "ativo" in dados:
        if not isinstance(dados["ativo"], bool):
            return erro("O campo ativo deve ser verdadeiro ou falso.", 400)
        campos.append("ativo = ?")
        valores.append(1 if dados["ativo"] else 0)

    senha = dados.get("senha") or ""
    virando_admin = papel_novo == "admin" and usuario["papel"] == "aluno"

    if papel_novo != usuario["papel"]:
        campos.append("papel = ?")
        valores.append(papel_novo)
        if papel_novo == "aluno":
            # O CHECK do schema não admite aluno com senha.
            campos.append("senha_hash = ?")
            valores.append(None)

    if senha or virando_admin:
        if papel_novo != "admin":
            return erro("Aluno não tem senha: o acesso dele é pelo e-mail.", 400)
        if len(senha) < SENHA_MINIMA:
            return erro(f"A senha precisa de pelo menos {SENHA_MINIMA} caracteres.", 400)
        campos.append("senha_hash = ?")
        valores.append(generate_password_hash(senha))

    if not campos:
        return erro("Nada para alterar.", 400)

    with transacao() as conexao:
        conexao.execute(
            f"UPDATE usuarios SET {', '.join(campos)} WHERE id = ?",
            (*valores, usuario_id),
        )
        # Desativar ou rebaixar precisa derrubar as sessões abertas, senão a
        # pessoa continua entrando com o token que já tinha na mão.
        if dados.get("ativo") is False or papel_novo != usuario["papel"]:
            conexao.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))

    return jsonify({"ok": True})


# --- Presenças --------------------------------------------------------------


@admin.post("/presencas")
@exige_admin
def lancar_presenca():
    """Presença lançada pela coordenação, sem palavra-chave.

    Para quem esqueceu de registrar ou chegou depois. A avaliação fica NULL:
    a coordenação não tem como saber a nota que o aluno daria, e inventar
    contaminaria a média da oficina.
    """
    dados = corpo()
    usuario_id = dados.get("usuario_id")
    oficina_id = dados.get("oficina_id")

    if not isinstance(usuario_id, int) or not isinstance(oficina_id, int):
        return erro("Informe o aluno e a oficina.", 400)

    db = get_db()
    aluno = db.execute(
        "SELECT papel FROM usuarios WHERE id = ?", (usuario_id,)
    ).fetchone()
    if aluno is None:
        return erro("Aluno não encontrado.", 404)
    if aluno["papel"] != "aluno":
        return erro("Só é possível lançar presença para aluno.", 400)
    if db.execute("SELECT 1 FROM oficinas WHERE id = ?", (oficina_id,)).fetchone() is None:
        return erro("Oficina não encontrada.", 404)

    try:
        with transacao() as conexao:
            conexao.execute(
                "INSERT INTO presencas (usuario_id, oficina_id, comentario)"
                " VALUES (?, ?, ?)",
                (usuario_id, oficina_id, "lançada pela coordenação"),
            )
    except sqlite3.IntegrityError:
        return erro("Este aluno já tem presença nesta oficina.", 409)

    return jsonify({"ok": True}), 201


@admin.delete("/presencas")
@exige_admin
def remover_presenca():
    """Desfaz um lançamento errado."""
    dados = corpo()
    usuario_id = dados.get("usuario_id")
    oficina_id = dados.get("oficina_id")

    if not isinstance(usuario_id, int) or not isinstance(oficina_id, int):
        return erro("Informe o aluno e a oficina.", 400)

    with transacao() as conexao:
        cur = conexao.execute(
            "DELETE FROM presencas WHERE usuario_id = ? AND oficina_id = ?",
            (usuario_id, oficina_id),
        )
    if cur.rowcount == 0:
        return erro("Não havia presença registrada para esse aluno nessa oficina.", 404)

    return jsonify({"ok": True})
