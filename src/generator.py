import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "alunos.json"
BADGES_FILE = PROJECT_ROOT / "data" / "insignias.json"
TEMPLATE_DIR = PROJECT_ROOT / "src" / "templates"
TEMPLATE_FILE = "index.html"
OUTPUT_FILE = PROJECT_ROOT / "index.html"


def generate_site():
    with DATA_FILE.open(encoding="utf-8") as data_file:
        alunos = json.load(data_file)

    with BADGES_FILE.open(encoding="utf-8") as badges_file:
        insignias = json.load(badges_file)

    for aluno in alunos:
        modulos_concluidos = set(aluno.get("modulos_concluidos", []))
        modulos_concluidos.update(
            item for item in aluno.get("insignias", []) if item.startswith("Modulo")
        )
        badges_conquistadas = set(aluno.get("insignias", []))
        aluno["insignias_status"] = [
            {
                "nome": insignia["nome"],
            "numero": insignia.get("numero", index + 1),
            "descricao": insignia.get("descricao", ""),
            "imagem_conquistada": insignia.get("imagem_conquistada", ""),
            "imagem_pendente": insignia.get("imagem_pendente", ""),
            "cor": insignia.get("cor", "slate"),
                "conquistada": (
                    insignia["nome"] in badges_conquistadas
                    or set(insignia["modulos"]).issubset(modulos_concluidos)
                ),
            }
            for index, insignia in enumerate(insignias)
        ]
        total_insignias = len(aluno["insignias_status"])
        insignias_conquistadas = sum(
            insignia["conquistada"] for insignia in aluno["insignias_status"]
        )
        aluno["progresso_insignias"] = {
            "conquistadas": insignias_conquistadas,
            "total": total_insignias,
            "percentual": round(insignias_conquistadas / total_insignias * 100)
            if total_insignias
            else 0,
        }

    environment = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = environment.get_template(TEMPLATE_FILE)
    OUTPUT_FILE.write_text(
        template.render(alunos=alunos, insignias=insignias),
        encoding="utf-8",
    )
    print(f"Página gerada em {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_site()
