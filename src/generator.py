import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "alunos.json"
TEMPLATE_DIR = PROJECT_ROOT / "src" / "templates"
OUTPUT_FILE = PROJECT_ROOT / "index.html"

DEFAULT_BADGES = [
    {"nome": "MÓDULO 1 - PARTE 1: INCLUSÃO DIGITAL", "modulos": ["Modulo1_InclusaoDigital", "Modulo1_InclusaoDigital_Parte2"], "imagem_conquistada": "src/assets/badges/mdl_1_col.png", "imagem_pendente": "src/assets/badges/mdl_1_cinza.png"},
    {"nome": "MÓDULO 1 - PARTE 2: INCLUSÃO DIGITAL", "modulos": ["Modulo1_InclusaoDigital", "Modulo1_InclusaoDigital_Parte2"], "imagem_conquistada": "src/assets/badges/mdl_1_col.png", "imagem_pendente": "src/assets/badges/mdl_1_cinza.png"},
    {"nome": "MÓDULO 2 - PARTE 1: PRODUTIVIDADE DIGITAL E EMPREGABILIDADE", "modulos": ["Modulo2_ProdutividadeDigital", "Modulo2_ProdutividadeDigital_Parte2"], "imagem_conquistada": "src/assets/badges/mdl_2_col.png", "imagem_pendente": "src/assets/badges/mdl_2_cinza.png"},
    {"nome": "MÓDULO 2 - PARTE 2: PRODUTIVIDADE DIGITAL E EMPREGABILIDADE", "modulos": ["Modulo2_ProdutividadeDigital", "Modulo2_ProdutividadeDigital_Parte2"], "imagem_conquistada": "src/assets/badges/mdl_2_col.png", "imagem_pendente": "src/assets/badges/mdl_2_cinza.png"},
    {"nome": "MÓDULO 3: SEGURANÇA DIGITAL, CIDADANIA E PRIVACIDADE", "modulos": ["Modulo3_SegurancaDigital"], "imagem_conquistada": "src/assets/badges/mdl_3_col.png", "imagem_pendente": "src/assets/badges/mdl_3_cinza.png"},
    {"nome": "MÓDULO 4: INTELIGÊNCIA ARTIFICIAL NA PRÁTICA", "modulos": ["Modulo4_InteligenciaArtificial"], "imagem_conquistada": "src/assets/badges/mdl_4_col.png", "imagem_pendente": "src/assets/badges/mdl_4_cinza.png"},
    {"nome": "MÓDULO 5 - PARTE 1: PENSAMENTO COMPUTACIONAL", "modulos": ["Modulo5_PensamentoComputacional", "Modulo5_PensamentoComputacional_Parte2"], "imagem_conquistada": "src/assets/badges/mdl_5_col.png", "imagem_pendente": "src/assets/badges/mdl_5_cinza.png"},
    {"nome": "MÓDULO 5 - PARTE 2: PENSAMENTO COMPUTACIONAL", "modulos": ["Modulo5_PensamentoComputacional", "Modulo5_PensamentoComputacional_Parte2"], "imagem_conquistada": "src/assets/badges/mdl_5_col.png", "imagem_pendente": "src/assets/badges/mdl_5_cinza.png"},
    {"nome": "MÓDULO 6: ACESSIBILIDADE DIGITAL E TECNOLOGIA INCLUSIVA", "modulos": ["Modulo6_AcessibilidadeDigital"], "imagem_conquistada": "src/assets/badges/mdl_6_col.png", "imagem_pendente": "src/assets/badges/mdl_6_cinza.png"},
    {"nome": "MÓDULO 7: TECNOLOGIA, ESG E SUSTENTABILIDADE", "modulos": ["Modulo7_TecnologiaESG"], "imagem_conquistada": "src/assets/badges/mdl_7_col.png", "imagem_pendente": "src/assets/badges/mdl_7_cinza.png"},
]


def prepare_student(student, badges):
    completed = set(student.get("modulos_concluidos", []))
    completed.update(item for item in student.get("insignias", []) if item.startswith("Modulo"))
    earned = set(student.get("insignias", []))
    statuses = []
    for index, badge in enumerate(badges):
        requirements = set(badge.get("modulos", []))
        conquered = requirements.issubset(completed) if requirements else badge["nome"] in earned
        statuses.append({
            **badge,
            "numero": badge.get("numero", index + 1),
            "descricao": badge.get("descricao", ""),
            "imagem_conquistada": badge.get("imagem_conquistada", ""),
            "imagem_pendente": badge.get("imagem_pendente", ""),
            "conquistada": conquered,
        })
    conquered_count = sum(status["conquistada"] for status in statuses)
    student["insignias_status"] = statuses
    student["progresso_insignias"] = {
        "conquistadas": conquered_count,
        "total": len(statuses),
        "percentual": round(conquered_count / len(statuses) * 100) if statuses else 0,
    }
    student["modulos"] = [
        {
            "id": index + 1,
            "nome": status["nome"],
            "imagem": status["imagem_conquistada"] if status["conquistada"] else status["imagem_pendente"],
            "status": "conquistada" if status["conquistada"] else "bloqueado",
        }
        for index, status in enumerate(statuses)
    ]
    return student


def generate_site():
    with DATA_FILE.open(encoding="utf-8") as data_file:
        students = json.load(data_file)
    if not students:
        raise ValueError(f"Nenhum aluno encontrado em {DATA_FILE}")

    students = [prepare_student(student, DEFAULT_BADGES) for student in students]
    student = students[0]
    environment = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    template = environment.get_template("index.html")
    OUTPUT_FILE.write_text(
        template.render(aluno=student, alunos=students, insignias=DEFAULT_BADGES),
        encoding="utf-8",
    )
    print(f"Página gerada em {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_site()
