-- Passaporte Digital LTD — esquema do banco (SQLite)
--
-- Conceito central: MÓDULO e OFICINA são coisas diferentes.
--   - Um módulo agrupa 1..N oficinas e é o que rende a insígnia.
--   - A insígnia NÃO é uma tabela: é derivada da presença do aluno em todas
--     as oficinas do módulo. Ver a view `insignias` no fim do arquivo.
--
-- Hoje o curso tem 7 módulos e 10 oficinas (módulos 1, 2 e 5 têm duas partes).

PRAGMA foreign_keys = ON;


-- ---------------------------------------------------------------------------
-- usuarios
-- ---------------------------------------------------------------------------
-- Aluno não tem senha: na fase 1 o acesso é liberado apenas conferindo se o
-- e-mail existe na base (ver `sessoes`). Só administrador tem senha, por isso
-- `senha_hash` é NULL para aluno — garantido pelo CHECK final.
CREATE TABLE usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    senha_hash  TEXT,
    papel       TEXT    NOT NULL DEFAULT 'aluno'
                        CHECK (papel IN ('aluno', 'admin')),
    ativo       INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em   TEXT    NOT NULL DEFAULT (datetime('now')),

    -- admin obriga senha; aluno não pode ter uma
    CHECK (
        (papel = 'admin' AND senha_hash IS NOT NULL) OR
        (papel = 'aluno' AND senha_hash IS NULL)
    )
);


-- ---------------------------------------------------------------------------
-- modulos
-- ---------------------------------------------------------------------------
-- Dono da insígnia: as duas imagens vivem aqui, não na oficina.
CREATE TABLE modulos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    numero              INTEGER NOT NULL UNIQUE,   -- ordem de exibição (1..7)
    nome                TEXT    NOT NULL,
    descricao           TEXT    NOT NULL DEFAULT '',
    imagem_conquistada  TEXT    NOT NULL,
    imagem_pendente     TEXT    NOT NULL
);


-- ---------------------------------------------------------------------------
-- oficinas
-- ---------------------------------------------------------------------------
-- O encontro presencial. `palavra_chave` é o segredo dito em aula que o aluno
-- digita para registrar presença — NOCASE porque ninguém acerta maiúscula.
-- `slug` é o identificador estável, compatível com os tokens já usados em
-- data/alunos.json (ex.: 'Modulo1_InclusaoDigital_Parte2').
CREATE TABLE oficinas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    modulo_id     INTEGER NOT NULL REFERENCES modulos(id) ON DELETE RESTRICT,
    slug          TEXT    NOT NULL UNIQUE,
    ordem         INTEGER NOT NULL DEFAULT 1,      -- parte 1, parte 2, ...
    nome          TEXT    NOT NULL,
    descricao     TEXT    NOT NULL DEFAULT '',
    data          TEXT,                            -- 'YYYY-MM-DD', NULL = sem data marcada
    palavra_chave TEXT    NOT NULL COLLATE NOCASE,

    UNIQUE (modulo_id, ordem),
    CHECK (data IS NULL OR data GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);

CREATE INDEX idx_oficinas_modulo ON oficinas(modulo_id);


-- ---------------------------------------------------------------------------
-- presencas
-- ---------------------------------------------------------------------------
-- Um aluno numa oficina. Substitui o `localStorage` do frontend atual e é a
-- única escrita que o aluno faz no sistema.
-- A avaliação de 1 a 5 estrelas mora aqui: ela é sobre a oficina, não sobre o
-- módulo, e hoje não é persistida em lugar nenhum.
CREATE TABLE presencas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id    INTEGER NOT NULL REFERENCES usuarios(id)  ON DELETE CASCADE,
    oficina_id    INTEGER NOT NULL REFERENCES oficinas(id)  ON DELETE CASCADE,
    avaliacao     INTEGER CHECK (avaliacao IS NULL OR avaliacao BETWEEN 1 AND 5),
    comentario    TEXT,
    registrada_em TEXT    NOT NULL DEFAULT (datetime('now')),

    -- impede dupla presença na mesma oficina (e torna a chamada idempotente)
    UNIQUE (usuario_id, oficina_id)
);

CREATE INDEX idx_presencas_usuario ON presencas(usuario_id);
CREATE INDEX idx_presencas_oficina ON presencas(oficina_id);


-- ---------------------------------------------------------------------------
-- sessoes
-- ---------------------------------------------------------------------------
-- Token devolvido no login e enviado depois no cabeçalho `Authorization`.
-- Cookie de sessão não serve porque o frontend (GitHub Pages) e a API
-- (PythonAnywhere) são origens diferentes — ver ADR-001, seção 3.5.
--
-- Guardamos o SHA-256 do token, não o token: se o arquivo .db vazar, os tokens
-- não podem ser reaproveitados. O valor original só existe no navegador.
--
-- FASE 1: o token é emitido apenas conferindo que o e-mail existe — não há
-- segredo verificado do lado do aluno. Isso é uma fraqueza conhecida e
-- aceita, condicionada a os e-mails saírem do HTML público (ver ADR-001).
-- FASE 2: basta exigir um código de 6 dígitos antes deste INSERT. Nenhuma
-- outra tabela e nenhuma rota autenticada mudam.
CREATE TABLE sessoes (
    token_hash TEXT    PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    criada_em  TEXT    NOT NULL DEFAULT (datetime('now')),
    expira_em  TEXT    NOT NULL
);

CREATE INDEX idx_sessoes_usuario ON sessoes(usuario_id);


-- ---------------------------------------------------------------------------
-- insignias (VIEW — não é tabela)
-- ---------------------------------------------------------------------------
-- Uma linha por (aluno, módulo), com o estado da insígnia calculado na hora.
-- Conquistada quando o aluno tem presença em TODAS as oficinas do módulo.
--
-- Por que view e não tabela: um estado guardado precisaria ser recalculado toda
-- vez que uma oficina fosse criada, removida ou remanejada de módulo. Esquecer
-- de recalcular = insígnia mentindo. Derivar não tem esse risco.
CREATE VIEW insignias AS
SELECT
    u.id     AS usuario_id,
    m.id     AS modulo_id,
    m.numero AS modulo_numero,
    m.nome   AS modulo_nome,
    COUNT(DISTINCT o.id)         AS oficinas_total,
    COUNT(DISTINCT p.oficina_id) AS oficinas_concluidas,
    CASE
        WHEN COUNT(DISTINCT o.id) > 0
         AND COUNT(DISTINCT p.oficina_id) = COUNT(DISTINCT o.id)
        THEN 1 ELSE 0
    END AS conquistada,
    CASE
        WHEN COUNT(DISTINCT o.id) > 0
         AND COUNT(DISTINCT p.oficina_id) = COUNT(DISTINCT o.id)
        THEN m.imagem_conquistada
        ELSE m.imagem_pendente
    END AS imagem,
    -- data da última presença que fechou o módulo; NULL enquanto pendente
    CASE
        WHEN COUNT(DISTINCT o.id) > 0
         AND COUNT(DISTINCT p.oficina_id) = COUNT(DISTINCT o.id)
        THEN MAX(p.registrada_em)
    END AS conquistada_em
FROM usuarios u
CROSS JOIN modulos m
LEFT JOIN oficinas  o ON o.modulo_id = m.id
LEFT JOIN presencas p ON p.oficina_id = o.id AND p.usuario_id = u.id
WHERE u.papel = 'aluno'
GROUP BY u.id, m.id;
