const html              = document.documentElement;

const drawer            = document.getElementById('drawer');
const drawerOverlay     = document.getElementById('drawerOverlay');
const openDrawer        = document.getElementById('openDrawer');
const closeDrawer       = document.getElementById('closeDrawer');
const themeToggle       = document.getElementById('themeToggle');

const keyword           = document.getElementById('keyword');
const starsContainer    = document.getElementById('stars');
const rescueButton      = document.getElementById('rescueButton');
const oficinaSelect     = document.getElementById('oficinaSelect');
const presenceError     = document.getElementById('presenceError');

const successModal      = document.getElementById("successModal");
const closeSuccess      = document.getElementById("closeSuccess");

const moduleCarousel    = document.getElementById("moduleCarousel");
const moduleDots        = document.getElementById("moduleDots");
const moduleCounter     = document.getElementById("moduleCounter");

const dateWorkshop      = document.getElementById('dateWorkshop');
const currentWorkshop   = document.getElementById("currentWorkshop");
const progressBar       = document.getElementById("progressBar");
const progressPercent   = document.getElementById("progressPercent");
const progressText      = document.getElementById("progressText");
const accessModal       = document.getElementById("accessModal");
const accessForm        = document.getElementById("accessForm");
const accessEmail       = document.getElementById("accessEmail");
const accessError       = document.getElementById("accessError");

// --- API --------------------------------------------------------------------

const config = window.passaporteConfig ?? {apiBase: "", modulos: []};

// Página e API vêm do mesmo servidor, então o caminho é relativo e nada
// precisa ser configurado. `apiBase` só é preenchido se algum dia o frontend
// for hospedado fora — aí a API precisa liberar aquela origem no CORS.
const API = `${(config.apiBase || "").replace(/\/+$/, "")}/api/v1`;

const TOKEN_KEY = "ltd-token";

function lerToken(){
    try {
        return localStorage.getItem(TOKEN_KEY);
    } catch {
        return null;
    }
}

function guardarToken(token){
    try {
        if(token) localStorage.setItem(TOKEN_KEY, token);
        else localStorage.removeItem(TOKEN_KEY);
    } catch {
        // Navegação privada ou storage bloqueado: a sessão dura só esta aba.
    }
}

class ErroApi extends Error {
    constructor(mensagem, status){
        super(mensagem);
        this.status = status;
    }
}

async function chamarApi(rota, {metodo = "GET", corpo = null, comToken = true} = {}){
    const cabecalhos = {};
    if(corpo) cabecalhos["Content-Type"] = "application/json";

    const token = lerToken();
    if(comToken && token) cabecalhos["Authorization"] = `Bearer ${token}`;

    let resposta;
    try {
        resposta = await fetch(`${API}${rota}`, {
            method: metodo,
            headers: cabecalhos,
            body: corpo ? JSON.stringify(corpo) : undefined,
        });
    } catch {
        // fetch só rejeita por rede ou CORS — nunca por status HTTP.
        throw new ErroApi("Não foi possível falar com o servidor. Verifique sua conexão.", 0);
    }

    const dados = await resposta.json().catch(() => ({}));

    if(!resposta.ok){
        throw new ErroApi(dados.erro || "Erro inesperado. Tente novamente.", resposta.status);
    }
    return dados;
}

// --- Estado -----------------------------------------------------------------

// Esqueleto vindo do build: todos os módulos bloqueados, sem dado de aluno.
// É o que a página mostra antes do login.
function modulosVazios(){
    return (config.modulos ?? []).map(modulo => ({
        numero: modulo.numero,
        nome: modulo.nome,
        imagem: modulo.imagem_pendente,
        status: "bloqueado",
        oficinas_concluidas: 0,
        oficinas_total: modulo.oficinas.length,
        oficinas: modulo.oficinas.map(oficina => ({...oficina, presente: false, avaliacao: null})),
    }));
}

let aluno = null;
let modulos = modulosVazios();
let currentModuleNumero = modulos[0]?.numero ?? 1;
let selectedRating = 0;

function moduloAtual(){
    return modulos.find(m => m.numero === currentModuleNumero) ?? modulos[0];
}

function oficinasPendentes(modulo){
    return (modulo?.oficinas ?? []).filter(o => !o.presente);
}

// --- Renderização -----------------------------------------------------------

function statusInfo(status){
    if(status === "conquistada"){
        return {
            texto: "CONQUISTADO",
            classe: "text-emerald-500 dark:text-emerald-400",
            icone: "check-circle-2"
        };
    }

    return {
        texto: "BLOQUEADO",
        classe: "text-slate-400 dark:text-gray-500",
        icone: "lock"
    };
}

function renderModules(){
    moduleCarousel.innerHTML = "";

    modulos.forEach(modulo =>{
        const conquistado = modulo.status === "conquistada";
        const info = statusInfo(modulo.status);
        const selecionado = modulo.numero === currentModuleNumero;

        const card = document.createElement('article');

        let borderClass = "border-slate-200 dark:border-white/10";
        if(conquistado) borderClass = "border-emerald-500/50";
        else if(selecionado) borderClass = "border-orange-500/50";

        card.className = `
            group relative w-[80%] shrink-0 snap-center overflow-hidden rounded-2xl border bg-white shadow-sm transition-all lg:w-full dark:bg-[#191A1E] sm:w-[45%]
            ${borderClass}
            cursor-pointer lg:hover:-translate-y-1 hover:shadow-md
        `;

        card.dataset.moduleNumero = modulo.numero;

        card.innerHTML = `
            <div class="relative aspect-square overflow-hidden">
                <img
                    src="${modulo.imagem}"
                    alt="Insígnia do módulo ${modulo.numero}"
                    class="h-full w-full object-cover transition-transform duration-500
                    ${conquistado ? "group-hover:scale-105" : "grayscale opacity-40"}"
                >
                ${conquistado ? "" : `
                    <div class="absolute inset-0 flex items-center justify-center bg-black/40">
                        <div class="flex h-12 w-12 items-center justify-center rounded-full bg-black/60 shadow-lg backdrop-blur-sm">
                            <i data-lucide="lock" class="h-6 w-6 text-white"></i>
                        </div>
                    </div>
                `}
            </div>
            <div class="p-4">
                <h3 class="mt-1 h-12 font-bold text-xs leading-5 break-word line-clamp-2 lg:h-[100px] lg:line-clamp-5">
                    ${modulo.nome}
                </h3>
                <p class="mt-2 flex items-center gap-1.5 text-xs font-bold ${info.classe}">
                    <i data-lucide="${info.icone}" class="h-3.5 w-3.5"></i>
                    <span>${info.texto}</span>
                </p>
                <p class="mt-1 text-[11px] text-slate-400 dark:text-gray-500">
                    ${modulo.oficinas_concluidas} de ${modulo.oficinas_total} oficinas
                </p>
            </div>
        `;

        // Todo módulo é clicável: a palavra-chave é o que valida a presença,
        // não a ordem em que o aluno percorre a galeria.
        card.addEventListener("click", () =>{
            currentModuleNumero = modulo.numero;
            resetPresenceForm();
            updateCurrentModule();
            renderModules();
        });

        moduleCarousel.appendChild(card);
    });

    renderDots();
    updateCounter();
    lucide.createIcons();
}

function renderDots(){
    moduleDots.innerHTML = "";
    modulos.forEach(modulo => {
        const dot = document.createElement("span");
        dot.className = `
            h-1.5 rounded-full transition-all
            ${modulo.numero === currentModuleNumero ? "w-5 bg-orange-500" : "w-1.5 bg-slate-300 dark:bg-gray-600"}`;
        moduleDots.appendChild(dot);
    });
}

function updateCounter(){
    const conquistadas = modulos.filter(m => m.status === "conquistada").length;
    moduleCounter.textContent = `${conquistadas} / ${modulos.length}`;
}

function updateProgress(){
    const conquistadas = modulos.filter(m => m.status === "conquistada").length;
    const porcentagem = modulos.length ? Math.round((conquistadas / modulos.length) * 100) : 0;

    if(progressText)    progressText.innerHTML = `Progresso: ${conquistadas} de ${modulos.length} Módulos`;
    if(progressBar)     progressBar.style.width = `${porcentagem}%`;
    if(progressPercent) progressPercent.textContent = `${porcentagem}%`;
}

function updateStudentProfile(){
    const nome = aluno?.nome || "";
    const email = aluno?.email || "";
    const sidebarName = document.getElementById("studentNameSidebar");
    const sidebarEmail = document.getElementById("studentEmailSidebar");
    const studentName = document.getElementById("studentName");

    if(sidebarName)  sidebarName.textContent = nome || " ";
    if(sidebarEmail) sidebarEmail.textContent = email || " ";
    if(studentName)  studentName.textContent = nome ? `Olá, ${nome}` : "Olá";
}

function updateCurrentModule(){
    const modulo = moduloAtual();
    if(!modulo) return;

    if(currentWorkshop){
        currentWorkshop.textContent = `Módulo ${modulo.numero} - ${modulo.nome}`;
    }
    renderOficinaOptions(modulo);
}

function renderOficinaOptions(modulo){
    if(!oficinaSelect) return;

    oficinaSelect.innerHTML = "";
    const pendentes = oficinasPendentes(modulo);

    if(pendentes.length === 0){
        const option = document.createElement("option");
        option.textContent = "Todas as oficinas deste módulo já foram registradas";
        option.value = "";
        oficinaSelect.appendChild(option);
        oficinaSelect.disabled = true;
    } else {
        oficinaSelect.disabled = false;
        pendentes.forEach(oficina => {
            const option = document.createElement("option");
            option.value = oficina.slug;
            option.textContent = oficina.nome;
            oficinaSelect.appendChild(option);
        });
    }

    atualizarDataOficina();
}

function atualizarDataOficina(){
    if(!dateWorkshop) return;

    const modulo = moduloAtual();
    const slug = oficinaSelect?.value;
    const oficina = (modulo?.oficinas ?? []).find(o => o.slug === slug);

    const data = oficina?.data
        ? new Date(`${oficina.data}T00:00:00`).toLocaleDateString('pt-br')
        : new Date().toLocaleDateString('pt-br');

    dateWorkshop.innerHTML = `Data: ${data}`;
}

// --- Estrelas ---------------------------------------------------------------

function createStars(){
    starsContainer.innerHTML = "";

    for(let i = 1; i <= 5; i++){
        const button = document.createElement("button");
        button.type = "button";
        button.className = "flex h-9 w-9 items-center justify-center rounded-lg text-slate-300 transition hover:scale-110 hover:text-yellow-400 focus:outline-none focus:ring-2 focus:ring-yellow-400/40 dark:text-gray-600";
        button.setAttribute("aria-label", `${i} estrela${i > 1 ? "s" : ""}`);

        button.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="h-7 w-7" fill="currentColor" aria-hidden="true">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26"/>
            </svg>
        `;

        button.addEventListener("mouseenter", () => updateStars(i));
        button.addEventListener("focus", () => updateStars(i));
        button.addEventListener("click", () => {
            selectedRating = i;
            updateStars();
            updateButton();
        });
        button.addEventListener("mouseleave", () => updateStars());
        button.addEventListener("blur", () => updateStars());

        starsContainer.appendChild(button);
    }

    updateStars();
}

function updateStars(hoveredRating = selectedRating){
    starsContainer.querySelectorAll("button").forEach((star, index) =>{
        const active = index < hoveredRating;
        star.classList.toggle("text-yellow-400", active);
        star.classList.toggle("text-slate-300", !active);
        star.classList.toggle("dark:text-gray-600", !active);
    });
}

// --- Formulário de presença -------------------------------------------------

function mostrarErroPresenca(mensagem){
    if(!presenceError) return;
    presenceError.textContent = mensagem;
    presenceError.classList.remove("hidden");
}

function limparErroPresenca(){
    presenceError?.classList.add("hidden");
}

function updateButton(){
    const temOficina = Boolean(oficinaSelect?.value);
    rescueButton.disabled = !(aluno && temOficina && keyword.value.trim() && selectedRating > 0);
}

function resetPresenceForm(){
    keyword.value = "";
    selectedRating = 0;
    limparErroPresenca();
    updateStars();
    updateButton();
}

keyword.addEventListener("input", () => {
    limparErroPresenca();
    updateButton();
});

oficinaSelect?.addEventListener("change", () => {
    limparErroPresenca();
    atualizarDataOficina();
    updateButton();
});

rescueButton.addEventListener("click", async () => {
    const slug = oficinaSelect?.value;
    if(!slug || !keyword.value.trim() || selectedRating === 0) return;

    rescueButton.disabled = true;
    limparErroPresenca();

    try {
        const resposta = await chamarApi("/presenca", {
            metodo: "POST",
            corpo: {
                oficina: slug,
                palavra_chave: keyword.value.trim(),
                avaliacao: selectedRating,
            },
        });

        // Recarrega do servidor: ele é a fonte da verdade sobre a insígnia.
        await carregarPassaporte();
        currentModuleNumero = resposta.modulo.numero;
        updateCurrentModule();
        renderModules();

        successModal.classList.remove("hidden");
        successModal.classList.add("flex");
    } catch (e) {
        if(e.status === 401){
            encerrarSessao("Sua sessão expirou. Entre novamente.");
            return;
        }
        mostrarErroPresenca(e.message);
        updateButton();
    }
});

function closeModal(){
    successModal.classList.remove("flex");
    successModal.classList.add("hidden");
    resetPresenceForm();

    const card = moduleCarousel.querySelector(`[data-module-numero="${currentModuleNumero}"]`);
    card?.scrollIntoView({behavior: "smooth", block: "nearest", inline: "center"});
}

closeSuccess.addEventListener("click", closeModal);
successModal.addEventListener("click", event => {
    if(event.target === successModal) closeModal();
});

// --- Sessão -----------------------------------------------------------------

async function carregarPassaporte(){
    const dados = await chamarApi("/passaporte");

    aluno = dados.aluno;
    modulos = dados.modulos;

    if(!modulos.some(m => m.numero === currentModuleNumero)){
        currentModuleNumero = modulos[0]?.numero ?? 1;
    }

    updateStudentProfile();
    updateProgress();
}

function abrirLogin(mensagem = ""){
    if(mensagem){
        accessError.textContent = mensagem;
        accessError.classList.remove("hidden");
    } else {
        accessError.classList.add("hidden");
    }
    accessModal.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");
}

function fecharLogin(){
    accessModal.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
}

function encerrarSessao(mensagem = ""){
    guardarToken(null);
    aluno = null;
    modulos = modulosVazios();
    currentModuleNumero = modulos[0]?.numero ?? 1;

    updateStudentProfile();
    renderModules();
    updateProgress();
    updateCurrentModule();
    resetPresenceForm();
    abrirLogin(mensagem);
}

accessForm.addEventListener("submit", async event => {
    event.preventDefault();

    const email = accessEmail.value.trim().toLowerCase();
    if(!email) return;

    const botao = accessForm.querySelector("button[type=submit]");
    if(botao) botao.disabled = true;
    accessError.classList.add("hidden");

    try {
        const dados = await chamarApi("/login", {
            metodo: "POST",
            corpo: {email},
            comToken: false,
        });

        guardarToken(dados.token);
        await carregarPassaporte();

        renderModules();
        updateCurrentModule();
        resetPresenceForm();
        fecharLogin();
    } catch (e) {
        accessError.textContent = e.message;
        accessError.classList.remove("hidden");
        accessEmail.focus();
    } finally {
        if(botao) botao.disabled = false;
    }
});

accessEmail.addEventListener("input", () => accessError.classList.add("hidden"));

// --- Navegação e tema -------------------------------------------------------

function openMenu(){
    drawer.classList.remove("-translate-x-full");
    drawerOverlay.classList.remove("opacity-0", "invisible");
    drawerOverlay.classList.add("opacity-100", "visible");
    document.body.classList.add("overflow-hidden");
}

function closeMenu(){
    drawer.classList.add("-translate-x-full");
    drawerOverlay.classList.remove("opacity-100", "visible");
    drawerOverlay.classList.add("opacity-0", "invisible");
    document.body.classList.remove("overflow-hidden");
}

if (openDrawer)    openDrawer.addEventListener("click", openMenu);
if (closeDrawer)   closeDrawer.addEventListener("click", closeMenu);
if (drawerOverlay) drawerOverlay.addEventListener("click", closeMenu);

document.querySelectorAll(".nav-item").forEach(button =>{
    button.addEventListener("click", () =>{
        document.querySelectorAll(".nav-item").forEach(item =>{
            item.classList.remove("bg-orange-500/10", "text-[#ff2a00]");
        });

        button.classList.add("bg-orange-500/10", "text-[#ff2a00]");

        const section = document.getElementById(button.dataset.section);
        if(window.innerWidth < 1024) closeMenu();

        if(section){
            setTimeout(() => {
                section.scrollIntoView({behavior: "smooth", block: "start"});
            }, 250);
        }
    });
});

function setTheme(theme){
    if(theme === "dark") html.classList.add("dark");
    else html.classList.remove("dark");

    try {
        localStorage.setItem("ltd-theme", theme);
    } catch {
        // Preferência de tema é conveniência: sem storage, só não persiste.
    }
}

let savedTheme = null;
try {
    savedTheme = localStorage.getItem("ltd-theme");
} catch {
    savedTheme = null;
}
setTheme(savedTheme || "dark");

themeToggle.addEventListener("click", () =>{
    setTheme(html.classList.contains("dark") ? "light" : "dark");
});

document.addEventListener("keydown", event => {
    if(event.key === "Escape"){
        closeMenu();
        closeModal();
    }
});

// --- Início -----------------------------------------------------------------

async function iniciar(){
    lucide.createIcons();
    createStars();
    updateStudentProfile();
    renderModules();
    updateProgress();
    updateCurrentModule();
    updateButton();

    if(!lerToken()){
        abrirLogin();
        return;
    }

    // Token guardado de uma visita anterior: só vale se o servidor aceitar.
    try {
        await carregarPassaporte();
        renderModules();
        updateCurrentModule();
        resetPresenceForm();
        fecharLogin();
    } catch (e) {
        encerrarSessao(e.status === 401 ? "" : e.message);
    }
}

iniciar();
