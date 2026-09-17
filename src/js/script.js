 const html              = document.documentElement;

    const drawer            = document.getElementById('drawer');
    const drawerOverlay     = document.getElementById('drawerOverlay');
    const openDrawer        = document.getElementById('openDrawer');
    const closeDrawer       = document.getElementById('closeDrawer');
    const themeToggle       = document.getElementById('themeToggle');

    const keyword           = document.getElementById('keyword');
    const starsContainer    = document.getElementById('stars');
    const rescueButton      = document.getElementById('rescueButton');

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

    lucide.createIcons();

    const modulosPadrao = [
        {id: 1, nome: "MÓDULO 1 - PARTE 1: INCLUSÃO DIGITAL", imagem: "../assets/badges/mdl_1_col.png", status: "conquistada"},

        {id: 2, nome: "MÓDULO 1 - PARTE 2: INCLUSÃO DIGITAL", imagem: "../assets/badges/mdl_1_col.png", status: "conquistada"},

        {id: 3, nome: "MÓDULO 2 - PARTE 1: PRODUTIVIDADE DIGITAL E EMPREGABILIDADE", imagem: "../assets/badges/mdl_2_col.png", status: "conquistada"},

        {id: 4, nome: "MÓDULO 2 - PARTE 2: PRODUTIVIDADE DIGITAL E EMPREGABILIDADE", imagem: "../assets/badges/mdl_2_col.png", status: "conquistada"},

        {id: 5, nome: "MÓDULO 3: SEGURANÇA DIGITAL, CIDADANIA E PRIVACIDADE", imagem: "../assets/badges/mdl_3_col.png", status: "conquistada"},

        {id: 6, nome: "MÓDULO 4: INTELIGÊNCIA ARTIFICIAL NA PRÁTICA", imagem: "../assets/badges/", status: "bloqueado"},

        {id: 7, nome: "MÓDULO 5 - PARTE 1: PENSAMENTO COMPUTACIONAL", imagem: "../assets/badges/mdl_5_cinza.png", status: "bloqueado"},

        {id: 8, nome: "MÓDULO 5 - PARTE 2: PENSAMENTO COMPUTACIONAL", imagem: "../assets/badges/mdl_5_cinza.png", status: "bloqueado"},

        {id: 9, nome: "MÓDULO 6: ACESSIBILIDADE DIGITAL E TECNOLOGIA INCLUSIVA", imagem: "../assets/badges/mdl_6_cinza.png", status: "bloqueado"},

        {id: 10, nome: "MÓDULO 7: TECNOLOGIA, ESG E SUSTENTABILIDADE", imagem: "../assets/badges/mdl_7_cinza.png", status: "bloqueado"},
    ]

    let modulos;

    try{
        const salvo = localStorage.getItem("ltd-modulos");
        modulos = salvo ? JSON.parse(salvo) : modulosPadrao;
    } catch {
        modulos = modulosPadrao;
    }

    let currentModuleId = 
        modulos.find(m => m.status === "conquistada")?.id|| 1;

    let selectedRating = 0;

    function salvarModulos(){
        localStorage.setItem("ltd-modulos", JSON.stringify(modulos))
    }

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
            const bloqueado = modulo.status === "bloqueado";
            const conquistado = modulo.status === "conquistada";
            const selecionado = modulo.id === currentModuleId;
            const info = statusInfo(modulo.status);

            const card = document.createElement('article');

            let borderClass =  "border-slate-200 dark:border-white/10";

            if(conquistado){
                borderClass = "border-emerald-500/50"
            }

            card.className = `
                    group relative w-[80%] shrink-0 snap-center overflow-hidden rounded-2xl border bg-white shadow-sm transition-all lg:w-full dark:bg-[#191A1E] sm:w-[45%]
                    ${borderClass}
                    ${bloqueado 
                        ? "cursor-not-allowed"
                        : "cursor-pointer lg:hover:-translate-y-1 hover:shadow-md"
                    }
                `;

                card.dataset.moduleId = modulo.id;

                card.innerHTML = `
                    <div class="relative aspect-square overflow-hidden">
                        <img
                            src="${modulo.imagem}"
                            alt="Insígnia do ${modulo.id}º módulo"
                            class="h-full w-full object-cover transition-transform duration-500 
                            ${bloqueado 
                                ? "grayscale opacity-40" 
                                : "group-hover:scale-105"
                            }"
                        >
                        ${bloqueado ? `
                                <div class="absolute inset-0 flex items-center justify-center bg-black/40">
                                    <div class="flex h-12 w-12 items-center justify-center rounded-full bg-black/60 shadow-lg backdrop-blur-sm">
                                        <i
                                            data-lucide="lock"
                                            class="h-6 w-6 text-white"
                                        >
                                        </i>
                                    </div>
                                </div>
                            ` : ""}
                            ${conquistado ? `
                            ` : ""}
                    </div>
                    <div class="p-4">
                        <h3 class="mt-1 h-12 font-bold text-xs leading-5 break-word line-clamp-2 lg:h-[100px] lg:line-clamp-5">
                            ${modulo.nome}
                        </h3>
                        <p class="mt-2 flex items-center gap-1.5 text-xs font-bold ${info.classe}">
                            <i 
                                data-lucide="${info.icone}" 
                                class="h-3.5 w-3.5"
                            >
                            </i>
                            <span>${info.texto}</span>
                        </p>
                    </div>
                `;

                if(!bloqueado){
                    card.addEventListener("click", () =>{
                        currentModuleId = modulo.id;
                        resetPresenceForm();
                        updateCurrentModule();
                        renderModules()
                    })
                }

                moduleCarousel.appendChild(card);
        });

        renderDots();
        updateCounter();
        lucide.createIcons();
    }

    function renderDots(){
        moduleDots.innerHTML= "";
        modulos.forEach(modulo => {
            const dot = document.createElement("span");
            dot.className = `
                h-1.5 rounded-full transition-all 
                ${modulo.id === currentModuleId ? "w-5 bg-orange-500" : "w-1.5 bg-slate-300 dark:bg-gray-600"}`;
                moduleDots.appendChild(dot);
        });
    }

    function updateCounter(){
        const conquistadas = modulos.filter(m => m.status === "conquistada").length;
        moduleCounter.textContent = `${conquistadas} / ${modulos.length}`
    }

    function updateProgress(){
        const conquistadas = modulos.filter(m => m.status === "conquistada").length;
        const porcentagem = Math.round((conquistadas / modulos.length) * 100);

        if(progressText){
            progressText.innerHTML = `Progresso: ${conquistadas} de ${modulos.length} Oficinas`;
        }

        if(progressBar){
            progressBar.style.width = `${porcentagem}%`
        }

        if(progressPercent){
            progressPercent.textContent = `${porcentagem}%`
        }
    }

    function updateCurrentModule(){
        const modulo = modulos.find(m => m.id === currentModuleId);
        if(!modulo || !currentWorkshop) return;
        currentWorkshop.textContent = `Oficina de Hoje: Módulo ${modulo.id}- ${modulo.nome}`;
    }

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
    
    if (openDrawer) openDrawer.addEventListener("click", openMenu);
    if (closeDrawer) closeDrawer.addEventListener("click", closeMenu);
    if (drawerOverlay) drawerOverlay.addEventListener("click", closeMenu);

    document.querySelectorAll(".nav-item").forEach(button =>{
        button.addEventListener("click", () =>{
            document.querySelectorAll(".nav-item").forEach(item =>{
                item.classList.remove("bg-orange-500/10" , "text-[#ff2a00]");
            })

            button.classList.add("bg-orange-500/10", "text-[#ff2a00]");

            const section = document.getElementById(button.dataset.section);
            if(window.innerWidth < 1024){
                closeMenu();
            }

            if(section){
                setTimeout(() => {
                    section.scrollIntoView({behavior: "smooth", block:"start"});
                }, 250)
            }
        });
    });

    function setTheme(theme){
        if(theme === "dark"){
            html.classList.add("dark");
        } else {
            html.classList.remove("dark")
        }
        localStorage.setItem("ltd-theme", theme);
    }

    const savedTheme = localStorage.getItem("ltd-theme");
    setTheme(savedTheme || "dark");

    themeToggle.addEventListener("click", () =>{
        setTheme(html.classList.contains("dark") ? "light" : "dark");
    })

    function dateWorkShop(){
        const today = new Date().toLocaleDateString('pt-br')
        dateWorkshop.innerHTML = `Data: ${today}`
    }

    function createStars(){
        starsContainer.innerHTML = "";

        for(let i = 1; i <= 5; i++){
            const button = document.createElement("button");
            button.type = "button";
            button.className = "flex h-9 w-9 items-center justify-center rounded-lg text-slate-300 transition hover:scale-110 hover:text-yellow-400 focus:outline-none focus:ring-2 focus:ring-yellow-400/40 dark:text-gray-600";
            button.setAttribute("aria-label", `${i} estrela ${i > 1 ?  "s" : ""}`);

            button.innerHTML = `
                <svg 
                    xmlns="http://www.w3.org/2000/svg" 
                    viewBox="0 0 24 24"
                    class="h-7 w-7"
                    fill="currentColor"
                    aria-hidden="true"
                >
                    <polygon 
                        points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26"
                    />
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
        })
    }

    function updateButton(){
        const moduloAtual = modulos.find(m => m.id === currentModuleId);
        const disponivel = moduloAtual && moduloAtual.status !== "bloqueado"

        rescueButton.disabled = !(disponivel && keyword.value.trim() && selectedRating > 0);
    }

    keyword.addEventListener("input", updateButton);

    function resetPresenceForm(){
        keyword.value = "";
        selectedRating = 0;
        updateStars();
        updateButton();
    }

    rescueButton.addEventListener("click", () => {
        const moduloAtual = modulos.find(m => m.id === currentModuleId);

        if(!moduloAtual || moduloAtual.status === "bloqueado" || !keyword.value.trim() || selectedRating === 0){
            return;
        }

        moduloAtual.status = "conquistada";

        const proximoModulo = modulos.find(m => m.id === moduloAtual.id + 1);
        if(proximoModulo && proximoModulo.status === "bloqueado"){
            proximoModulo.status = "conquistada";
            currentModuleId = proximoModulo.id;
        }

        salvarModulos();
        updateProgress();
        updateCurrentModule();
        renderModules();
        
        successModal.classList.remove("hidden");
        successModal.classList.add("flex");
    });

    function closeModal(){
        successModal.classList.remove("flex");
        successModal.classList.add("hidden");
        resetPresenceForm();

        const card = moduleCarousel.querySelector(`[data-module-id="${currentModuleId}"]`);
        if(card){
            card.scrollIntoView({behavior: "smooth", block: "nearest", inline: "center"});
        }
    }

    closeSuccess.addEventListener("click", closeModal);

    successModal.addEventListener("click", event => {
        if(event.target === successModal) closeModal();
    })

    document.addEventListener("keydown", event => {
        if(event.key === "Escape"){
            closeMenu();
            closeModal();
        }
    })

    renderModules();
    updateProgress();
    updateCurrentModule();
    dateWorkShop()
    createStars();
    updateButton();

