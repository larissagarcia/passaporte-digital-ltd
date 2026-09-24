const html          = document.documentElement;
const painel        = document.getElementById("painel");
const adminNome     = document.getElementById("adminNome");
const accessModal   = document.getElementById("accessModal");
const accessForm    = document.getElementById("accessForm");
const accessEmail   = document.getElementById("accessEmail");
const accessSenha   = document.getElementById("accessSenha");
const accessError   = document.getElementById("accessError");
const painelErro    = document.getElementById("painelErro");
const painelOk      = document.getElementById("painelOk");
const totais        = document.getElementById("totais");
const avisoChaves   = document.getElementById("avisoChaves");
const themeToggle   = document.getElementById("themeToggle");
const logoutButton  = document.getElementById("logoutButton");

const config    = window.passaporteConfig ?? {apiBase: ""};
const API       = `${(config.apiBase || "").replace(/\/+$/, "")}/api/v1`;
const TOKEN_KEY = "ltd-token-admin";  // separado do token do aluno

let dadosResumo = null;
let dadosCurso  = null;
let abaAtiva    = "turma";

// --- Utilidades -------------------------------------------------------------

// Todo texto que vem do banco passa por aqui antes de entrar no HTML. Nome de
// aluno e comentário de oficina são digitados por pessoas: sem escapar, um
// comentário com <script> viraria XSS — e o token do admin está no
// localStorage (ADR-001, seção 3.5).
function esc(valor){
    return String(valor ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
}

function lerToken(){
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

function guardarToken(token){
    try {
        if(token) localStorage.setItem(TOKEN_KEY, token);
        else localStorage.removeItem(TOKEN_KEY);
    } catch { /* storage bloqueado: sessão dura só esta aba */ }
}

class ErroApi extends Error {
    constructor(mensagem, status){ super(mensagem); this.status = status; }
}

async function api(rota, {metodo = "GET", corpo = null, comToken = true} = {}){
    const headers = {};
    if(corpo) headers["Content-Type"] = "application/json";
    const token = lerToken();
    if(comToken && token) headers["Authorization"] = `Bearer ${token}`;

    let resposta;
    try {
        resposta = await fetch(`${API}${rota}`, {
            method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined,
        });
    } catch {
        throw new ErroApi("Não foi possível falar com o servidor.", 0);
    }

    const dados = await resposta.json().catch(() => ({}));
    if(!resposta.ok) throw new ErroApi(dados.erro || "Erro inesperado.", resposta.status);
    return dados;
}

function avisar(mensagem, sucesso = false){
    const alvo = sucesso ? painelOk : painelErro;
    const outro = sucesso ? painelErro : painelOk;
    outro.classList.add("hidden");
    alvo.textContent = mensagem;
    alvo.classList.remove("hidden");
    if(sucesso) setTimeout(() => alvo.classList.add("hidden"), 4000);
}

function limparAvisos(){
    painelErro.classList.add("hidden");
    painelOk.classList.add("hidden");
}

/** Executa uma ação da API tratando 401 e mostrando o erro na tela. */
async function acao(fn, mensagemOk){
    limparAvisos();
    try {
        await fn();
        await carregarTudo();
        if(mensagemOk) avisar(mensagemOk, true);
    } catch (e) {
        if(e.status === 401) return encerrarSessao();
        avisar(e.message);
    }
}

const CLASSE_CAMPO = "h-11 w-full rounded-xl border border-slate-200 bg-transparent px-3 text-sm outline-none transition focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20 dark:border-white/20";
const CLASSE_BOTAO = "h-11 shrink-0 rounded-xl bg-orange-600 px-4 text-sm font-bold text-white transition hover:brightness-110 disabled:opacity-50";
const CLASSE_CARD  = "rounded-2xl border border-slate-200/80 bg-white p-5 dark:border-white/10 dark:bg-[#191A1E]";

// --- Resumo -----------------------------------------------------------------

function renderTotais(){
    const t = dadosResumo.totais;
    const cartoes = [
        {rotulo: "Alunos ativos", valor: t.alunos, icone: "users"},
        {rotulo: "Módulos", valor: t.modulos, icone: "layers"},
        {rotulo: "Oficinas", valor: t.oficinas, icone: "calendar-days"},
        {rotulo: "Sem palavra-chave", valor: t.oficinas_sem_palavra_chave, icone: "key-round",
         alerta: t.oficinas_sem_palavra_chave > 0},
        {rotulo: "Sem data", valor: t.oficinas_sem_data, icone: "calendar-x",
         alerta: t.oficinas_sem_data > 0},
    ];

    totais.innerHTML = cartoes.map(c => `
        <div class="${CLASSE_CARD} ${c.alerta ? "border-amber-500/40" : ""}">
            <div class="flex items-center gap-2 text-slate-400 dark:text-gray-500">
                <i data-lucide="${c.icone}" class="h-4 w-4"></i>
                <span class="text-[11px] font-medium uppercase tracking-wide">${esc(c.rotulo)}</span>
            </div>
            <p class="mt-2 text-3xl font-bold ${c.alerta ? "text-amber-500" : ""}">${c.valor}</p>
        </div>
    `).join("");

    // A presença do aluno exige palavra-chave definida E data igual à de hoje.
    // Faltando qualquer uma, a oficina recusa presença — por isso o aviso.
    const pendencias = [];
    if(t.oficinas_sem_palavra_chave > 0){
        pendencias.push(`<strong>${t.oficinas_sem_palavra_chave} oficina(s) sem palavra-chave</strong>`);
    }
    if(t.oficinas_sem_data > 0){
        pendencias.push(`<strong>${t.oficinas_sem_data} oficina(s) sem data marcada</strong>`);
    }

    if(pendencias.length){
        avisoChaves.innerHTML = `${pendencias.join(" e ")}.
            Nesse estado a presença é recusada — o aluno só consegue registrar
            no dia da oficina e com a palavra-chave certa. Ajuste na aba
            <em>Módulos e oficinas</em> antes da oficina começar.`;
        avisoChaves.classList.remove("hidden");
    } else {
        avisoChaves.classList.add("hidden");
    }
}

// --- Aba: turma -------------------------------------------------------------

function renderTurma(){
    const alunos = dadosResumo.alunos;
    const destino = document.getElementById("conteudoTurma");

    if(alunos.length === 0){
        destino.innerHTML = `<div class="${CLASSE_CARD} text-sm text-slate-500">Nenhum aluno cadastrado ainda. Use a aba Usuários.</div>`;
        return;
    }

    const linhas = alunos.map(a => {
        const pct = a.insignias_total ? Math.round(a.insignias / a.insignias_total * 100) : 0;
        return `
        <tr class="border-t border-slate-100 dark:border-white/5 ${a.ativo ? "" : "opacity-50"}">
            <td class="py-3 pr-4">
                <p class="font-medium">${esc(a.nome)}</p>
                <p class="text-xs text-slate-400">${esc(a.email)}${a.ativo ? "" : " · inativo"}</p>
            </td>
            <td class="py-3 pr-4 text-sm whitespace-nowrap">${a.oficinas_feitas} / ${a.oficinas_total}</td>
            <td class="py-3 pr-4 text-sm whitespace-nowrap">${a.insignias} / ${a.insignias_total}</td>
            <td class="py-3 w-32">
                <div class="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-white/10">
                    <div class="h-full rounded-full bg-gradient-to-r from-orange-600 to-red-400" style="width: ${pct}%"></div>
                </div>
            </td>
        </tr>`;
    }).join("");

    destino.innerHTML = `
        <div class="${CLASSE_CARD} overflow-x-auto">
            <table class="w-full min-w-[520px] text-left">
                <thead>
                    <tr class="text-[11px] uppercase tracking-wide text-slate-400">
                        <th class="pb-2 pr-4 font-medium">Aluno</th>
                        <th class="pb-2 pr-4 font-medium">Oficinas</th>
                        <th class="pb-2 pr-4 font-medium">Insígnias</th>
                        <th class="pb-2 font-medium">Progresso</th>
                    </tr>
                </thead>
                <tbody>${linhas}</tbody>
            </table>
        </div>

        <div class="${CLASSE_CARD} mt-4">
            <h3 class="font-bold">Lançar presença manualmente</h3>
            <p class="mt-1 text-sm text-slate-500 dark:text-gray-400">
                Para quem esqueceu de registrar ou chegou depois. A avaliação fica
                em branco — inventar uma nota contaminaria a média da oficina.
            </p>
            <div class="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
                <select id="presencaAluno" class="${CLASSE_CAMPO}">
                    ${alunos.filter(a => a.ativo).map(a => `<option value="${a.id}">${esc(a.nome)}</option>`).join("")}
                </select>
                <select id="presencaOficina" class="${CLASSE_CAMPO}">
                    ${(dadosCurso?.modulos ?? []).flatMap(m =>
                        m.oficinas.map(o => `<option value="${o.id}">M${m.numero} · ${esc(o.nome)}</option>`)
                    ).join("")}
                </select>
                <div class="flex gap-2">
                    <button id="presencaAdicionar" class="${CLASSE_BOTAO}">Lançar</button>
                    <button id="presencaRemover" class="h-11 shrink-0 rounded-xl border border-slate-200 px-4 text-sm font-medium transition hover:bg-slate-100 dark:border-white/20 dark:hover:bg-white/10">Remover</button>
                </div>
            </div>
        </div>`;

    const corpoPresenca = () => ({
        usuario_id: Number(document.getElementById("presencaAluno").value),
        oficina_id: Number(document.getElementById("presencaOficina").value),
    });

    document.getElementById("presencaAdicionar").onclick = () =>
        acao(() => api("/admin/presencas", {metodo: "POST", corpo: corpoPresenca()}),
             "Presença lançada.");

    document.getElementById("presencaRemover").onclick = () =>
        acao(() => api("/admin/presencas", {metodo: "DELETE", corpo: corpoPresenca()}),
             "Presença removida.");
}

// --- Aba: módulos e oficinas ------------------------------------------------

function renderOficinas(){
    const destino = document.getElementById("conteudoOficinas");
    const modulos = dadosCurso.modulos;

    destino.innerHTML = modulos.map(m => `
        <div class="${CLASSE_CARD} mb-4">
            <div class="flex flex-wrap items-start justify-between gap-3">
                <div class="min-w-0">
                    <h3 class="font-bold">Módulo ${m.numero} — ${esc(m.nome)}</h3>
                    <p class="text-xs text-slate-400">${m.oficinas.length} oficina(s)</p>
                </div>
                <button data-apagar-modulo="${m.id}"
                    class="h-9 shrink-0 rounded-lg border border-red-500/30 px-3 text-xs font-medium text-red-600 transition hover:bg-red-500/10 dark:text-red-400">
                    Apagar módulo
                </button>
            </div>

            <div class="mt-4 space-y-3">
                ${m.oficinas.map(o => `
                    <div class="rounded-xl border border-slate-100 p-3 dark:border-white/5">
                        <div class="flex flex-wrap items-center justify-between gap-2">
                            <p class="text-sm font-medium">${esc(o.nome)}</p>
                            <span class="flex flex-wrap items-center gap-2 text-[11px]">
                                ${o.e_hoje ? `<span class="rounded-full bg-emerald-500/15 px-2 py-0.5 font-bold text-emerald-500">É HOJE</span>` : ""}
                                <span class="${o.configurada ? "text-emerald-500" : "text-amber-500"}">
                                    ${o.configurada ? "palavra-chave definida" : "SEM PALAVRA-CHAVE"}
                                </span>
                                <span class="${o.data ? "text-slate-400" : "text-amber-500"}">
                                    ${o.data ? esc(o.data.split("-").reverse().join("/")) : "SEM DATA"}
                                </span>
                                <span class="text-slate-400">· ${o.presencas} presença(s)</span>
                            </span>
                        </div>
                        <div class="mt-3 grid gap-2 sm:grid-cols-[2fr_1fr_auto]">
                            <input class="${CLASSE_CAMPO}" data-chave="${o.id}" placeholder="Palavra-chave do dia"
                                   value="${o.configurada ? esc(o.palavra_chave) : ""}">
                            <input class="${CLASSE_CAMPO}" data-data="${o.id}" type="date" value="${esc(o.data ?? "")}">
                            <div class="flex gap-2">
                                <button data-salvar="${o.id}" class="${CLASSE_BOTAO}">Salvar</button>
                                <button data-apagar-oficina="${o.id}"
                                    class="h-11 shrink-0 rounded-xl border border-red-500/30 px-3 text-xs font-medium text-red-600 transition hover:bg-red-500/10 dark:text-red-400">
                                    Apagar
                                </button>
                            </div>
                        </div>
                    </div>
                `).join("")}
            </div>

            <details class="mt-4">
                <summary class="cursor-pointer text-sm font-medium text-orange-600">Nova oficina neste módulo</summary>
                <div class="mt-3 grid gap-2 sm:grid-cols-2">
                    <input class="${CLASSE_CAMPO}" data-nova-nome="${m.id}" placeholder="Nome da oficina">
                    <input class="${CLASSE_CAMPO}" data-nova-slug="${m.id}" placeholder="Identificador (ex: Modulo8_Robotica)">
                    <input class="${CLASSE_CAMPO}" data-nova-chave="${m.id}" placeholder="Palavra-chave">
                    <input class="${CLASSE_CAMPO}" data-nova-data="${m.id}" type="date">
                    <button data-criar-oficina="${m.id}" class="${CLASSE_BOTAO} sm:col-span-2">Criar oficina</button>
                </div>
            </details>
        </div>
    `).join("") + `
        <div class="${CLASSE_CARD}">
            <h3 class="font-bold">Novo módulo</h3>
            <div class="mt-3 grid gap-2 sm:grid-cols-2">
                <input class="${CLASSE_CAMPO}" id="moduloNumero" type="number" min="1" placeholder="Número (ex: 8)">
                <input class="${CLASSE_CAMPO}" id="moduloNome" placeholder="Nome do módulo">
                <input class="${CLASSE_CAMPO}" id="moduloImgCol" placeholder="Imagem conquistada" value="src/assets/badges/mdl_8_col.png">
                <input class="${CLASSE_CAMPO}" id="moduloImgCinza" placeholder="Imagem pendente" value="src/assets/badges/mdl_8_cinza.png">
                <button id="criarModulo" class="${CLASSE_BOTAO} sm:col-span-2">Criar módulo</button>
            </div>
        </div>`;

    destino.querySelectorAll("[data-salvar]").forEach(botao => {
        botao.onclick = () => {
            const id = botao.dataset.salvar;
            const chave = destino.querySelector(`[data-chave="${id}"]`).value.trim();
            const data = destino.querySelector(`[data-data="${id}"]`).value;
            const corpo = {data: data || null};
            if(chave) corpo.palavra_chave = chave;
            acao(() => api(`/admin/oficinas/${id}`, {metodo: "PATCH", corpo}), "Oficina atualizada.");
        };
    });

    destino.querySelectorAll("[data-apagar-oficina]").forEach(botao => {
        botao.onclick = () => {
            if(!confirm("Apagar esta oficina?")) return;
            acao(() => api(`/admin/oficinas/${botao.dataset.apagarOficina}`, {metodo: "DELETE"}),
                 "Oficina apagada.");
        };
    });

    destino.querySelectorAll("[data-apagar-modulo]").forEach(botao => {
        botao.onclick = () => {
            if(!confirm("Apagar este módulo?")) return;
            acao(() => api(`/admin/modulos/${botao.dataset.apagarModulo}`, {metodo: "DELETE"}),
                 "Módulo apagado.");
        };
    });

    destino.querySelectorAll("[data-criar-oficina]").forEach(botao => {
        botao.onclick = () => {
            const id = botao.dataset.criarOficina;
            const pegar = attr => destino.querySelector(`[data-${attr}="${id}"]`).value.trim();
            const modulo = modulos.find(m => String(m.id) === id);
            acao(() => api("/admin/oficinas", {metodo: "POST", corpo: {
                modulo_id: Number(id),
                nome: pegar("nova-nome"),
                slug: pegar("nova-slug"),
                palavra_chave: pegar("nova-chave"),
                data: pegar("nova-data") || null,
                ordem: modulo.oficinas.length + 1,
            }}), "Oficina criada.");
        };
    });

    document.getElementById("criarModulo").onclick = () => {
        const v = id => document.getElementById(id).value.trim();
        acao(() => api("/admin/modulos", {metodo: "POST", corpo: {
            numero: Number(v("moduloNumero")),
            nome: v("moduloNome"),
            imagem_conquistada: v("moduloImgCol"),
            imagem_pendente: v("moduloImgCinza"),
        }}), "Módulo criado.");
    };
}

// --- Aba: feedback ----------------------------------------------------------

async function renderFeedback(){
    const destino = document.getElementById("conteudoFeedback");
    const dados = await api("/admin/feedback");

    destino.innerHTML = dados.oficinas.map(o => `
        <div class="${CLASSE_CARD} mb-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="font-medium">M${o.modulo_numero} · ${esc(o.nome)}</p>
                <p class="text-sm">
                    ${o.media !== null
                        ? `<span class="font-bold text-yellow-500">${o.media} ★</span>
                           <span class="text-slate-400">(${o.avaliacoes} de ${o.presencas})</span>`
                        : `<span class="text-slate-400">sem avaliações</span>`}
                </p>
            </div>
            ${o.comentarios.length ? `
                <ul class="mt-3 space-y-2 border-t border-slate-100 pt-3 dark:border-white/5">
                    ${o.comentarios.map(c => `
                        <li class="text-sm">
                            <span class="text-yellow-500">${c.avaliacao ? "★".repeat(c.avaliacao) : ""}</span>
                            <span class="text-slate-600 dark:text-gray-300">${esc(c.comentario)}</span>
                            <span class="text-xs text-slate-400">— ${esc(c.aluno)}</span>
                        </li>`).join("")}
                </ul>` : ""}
        </div>
    `).join("") || `<div class="${CLASSE_CARD} text-sm text-slate-500">Nenhuma oficina cadastrada.</div>`;
}

// --- Aba: usuários ----------------------------------------------------------

async function renderUsuarios(){
    const destino = document.getElementById("conteudoUsuarios");
    const dados = await api("/admin/usuarios");

    const linhas = dados.usuarios.map(u => `
        <tr class="border-t border-slate-100 dark:border-white/5 ${u.ativo ? "" : "opacity-50"}">
            <td class="py-3 pr-4">
                <p class="font-medium">${esc(u.nome)}</p>
                <p class="text-xs text-slate-400">${esc(u.email)}</p>
            </td>
            <td class="py-3 pr-4 text-sm">
                <span class="rounded-full px-2 py-0.5 text-xs font-bold ${u.papel === "admin"
                    ? "bg-orange-500/10 text-orange-600" : "bg-slate-200 text-slate-500 dark:bg-white/10"}">
                    ${u.papel}
                </span>
            </td>
            <td class="py-3 text-right">
                <button data-alternar="${u.id}" data-ativo="${u.ativo}"
                    class="h-9 rounded-lg border border-slate-200 px-3 text-xs font-medium transition hover:bg-slate-100 dark:border-white/20 dark:hover:bg-white/10">
                    ${u.ativo ? "Desativar" : "Reativar"}
                </button>
            </td>
        </tr>`).join("");

    destino.innerHTML = `
        <div class="${CLASSE_CARD} overflow-x-auto">
            <table class="w-full min-w-[420px] text-left">
                <thead>
                    <tr class="text-[11px] uppercase tracking-wide text-slate-400">
                        <th class="pb-2 pr-4 font-medium">Pessoa</th>
                        <th class="pb-2 pr-4 font-medium">Papel</th>
                        <th class="pb-2 font-medium"></th>
                    </tr>
                </thead>
                <tbody>${linhas}</tbody>
            </table>
        </div>

        <div class="${CLASSE_CARD} mt-4">
            <h3 class="font-bold">Novo usuário</h3>
            <p class="mt-1 text-sm text-slate-500 dark:text-gray-400">
                Aluno entra só com o e-mail. Administrador precisa de senha.
            </p>
            <div class="mt-4 grid gap-2 sm:grid-cols-2">
                <input class="${CLASSE_CAMPO}" id="novoNome" placeholder="Nome completo">
                <input class="${CLASSE_CAMPO}" id="novoEmail" type="email" placeholder="email@exemplo.com">
                <select class="${CLASSE_CAMPO}" id="novoPapel">
                    <option value="aluno">Aluno</option>
                    <option value="admin">Administrador</option>
                </select>
                <input class="${CLASSE_CAMPO}" id="novaSenha" type="password"
                       placeholder="Senha (mín. 8) — só para administrador" disabled>
                <button id="criarUsuario" class="${CLASSE_BOTAO} sm:col-span-2">Criar usuário</button>
            </div>
        </div>`;

    const papel = document.getElementById("novoPapel");
    const senha = document.getElementById("novaSenha");
    papel.onchange = () => {
        senha.disabled = papel.value !== "admin";
        if(senha.disabled) senha.value = "";
    };

    document.getElementById("criarUsuario").onclick = () => {
        const corpo = {
            nome: document.getElementById("novoNome").value.trim(),
            email: document.getElementById("novoEmail").value.trim(),
            papel: papel.value,
        };
        if(papel.value === "admin") corpo.senha = senha.value;
        acao(() => api("/admin/usuarios", {metodo: "POST", corpo}), "Usuário criado.");
    };

    destino.querySelectorAll("[data-alternar]").forEach(botao => {
        botao.onclick = () => {
            const ativo = botao.dataset.ativo === "true";
            acao(() => api(`/admin/usuarios/${botao.dataset.alternar}`,
                           {metodo: "PATCH", corpo: {ativo: !ativo}}),
                 ativo ? "Usuário desativado." : "Usuário reativado.");
        };
    });
}

// --- Abas -------------------------------------------------------------------

const RENDERIZADORES = {
    turma: renderTurma,
    oficinas: renderOficinas,
    feedback: renderFeedback,
    usuarios: renderUsuarios,
};

function pintarAbas(){
    document.querySelectorAll(".aba").forEach(botao => {
        const ativa = botao.dataset.aba === abaAtiva;
        botao.classList.toggle("border-orange-500", ativa);
        botao.classList.toggle("text-orange-600", ativa);
        botao.classList.toggle("border-transparent", !ativa);
        botao.classList.toggle("text-slate-400", !ativa);
    });

    document.querySelectorAll(".conteudo").forEach(secao => {
        const nome = secao.id.replace("conteudo", "").toLowerCase();
        secao.classList.toggle("hidden", nome !== abaAtiva);
    });
}

document.querySelectorAll(".aba").forEach(botao => {
    botao.onclick = async () => {
        abaAtiva = botao.dataset.aba;
        limparAvisos();
        pintarAbas();
        try {
            await RENDERIZADORES[abaAtiva]();
            lucide.createIcons();
        } catch (e) {
            if(e.status === 401) return encerrarSessao();
            avisar(e.message);
        }
    };
});

// --- Sessão -----------------------------------------------------------------

async function carregarTudo(){
    [dadosResumo, dadosCurso] = await Promise.all([
        api("/admin/resumo"),
        api("/admin/modulos"),
    ]);

    renderTotais();
    await RENDERIZADORES[abaAtiva]();
    lucide.createIcons();
}

function mostrarPainel(usuario){
    adminNome.textContent = `${usuario.nome} · ${usuario.email}`;
    accessModal.classList.add("hidden");
    painel.classList.remove("hidden");
    document.body.classList.remove("overflow-hidden");
}

function encerrarSessao(mensagem = ""){
    guardarToken(null);
    painel.classList.add("hidden");
    accessModal.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
    accessSenha.value = "";
    if(mensagem){
        accessError.textContent = mensagem;
        accessError.classList.remove("hidden");
    }
}

accessForm.onsubmit = async event => {
    event.preventDefault();
    const botao = accessForm.querySelector("button[type=submit]");
    botao.disabled = true;
    accessError.classList.add("hidden");

    try {
        const dados = await api("/login", {
            metodo: "POST",
            corpo: {email: accessEmail.value.trim().toLowerCase(), senha: accessSenha.value},
            comToken: false,
        });

        if(dados.usuario.papel !== "admin"){
            accessError.textContent = "Esta área é restrita à coordenação.";
            accessError.classList.remove("hidden");
            return;
        }

        guardarToken(dados.token);
        mostrarPainel(dados.usuario);
        await carregarTudo();
    } catch (e) {
        accessError.textContent = e.message;
        accessError.classList.remove("hidden");
    } finally {
        botao.disabled = false;
    }
};

logoutButton.onclick = async () => {
    try { await api("/logout", {metodo: "POST"}); } catch { /* token já pode ter expirado */ }
    encerrarSessao();
};

// --- Tema -------------------------------------------------------------------

function setTheme(tema){
    html.classList.toggle("dark", tema === "dark");
    try { localStorage.setItem("ltd-theme", tema); } catch { /* sem storage */ }
}

let temaSalvo = null;
try { temaSalvo = localStorage.getItem("ltd-theme"); } catch { temaSalvo = null; }
setTheme(temaSalvo || "dark");

themeToggle.onclick = () => setTheme(html.classList.contains("dark") ? "light" : "dark");

// --- Início -----------------------------------------------------------------

async function iniciar(){
    lucide.createIcons();
    pintarAbas();
    document.body.classList.add("overflow-hidden");

    if(!lerToken()) return;

    // Token guardado: só vale se ainda for de um admin ativo.
    try {
        const resumo = await api("/admin/resumo");
        dadosResumo = resumo;
        dadosCurso = await api("/admin/modulos");
        mostrarPainel({nome: "Coordenação", email: ""});
        renderTotais();
        await RENDERIZADORES[abaAtiva]();
        lucide.createIcons();
    } catch {
        encerrarSessao();
    }
}

iniciar();
