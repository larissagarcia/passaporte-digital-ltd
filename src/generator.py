import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


MODULES = [
    "Modulo1_InclusaoDigital",
    "Modulo2_ProdutividadeDigital",
    "Modulo3_SegurancaDigital",
    "Modulo4_IA",
    "Modulo5_PensamentoComputacional",
    "Modulo6_AcessibilidadeDigital",
    "Modulo7_ESG",
]


def generate_site(data_path=None, template_path=None, output_path=None):
    project_root = Path(__file__).resolve().parent.parent

    if data_path is None:
        data_path = project_root / "data" / "alunos.json"
    if template_path is None:
        template_path = Path(__file__).resolve().parent / "templates" / "index.html"
    if output_path is None:
        output_path = project_root / "index.html"

    data_path = Path(data_path)
    template_path = Path(template_path)
    output_path = Path(output_path)

    with data_path.open("r", encoding="utf-8") as file:
        alunos = json.load(file)

    aluno = alunos[0] if isinstance(alunos, list) and alunos else {}
    insignias = set(aluno.get("insignias", []))
    completed_count = sum(1 for modulo in MODULES if modulo in insignias)
    percentual = round((completed_count / len(MODULES)) * 100)

    env = Environment(loader=FileSystemLoader(str(template_path.parent)))
    template = env.get_template(template_path.name)
    rendered = template.render(
        aluno=aluno,
        insignias=insignias,
        completed_count=completed_count,
        percentual=percentual,
    )

    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    assets_src = project_root / "src" / "assets"
    assets_dst = output_dir / "assets"
    if assets_src.exists():
        if assets_dst.exists():
            for child in assets_dst.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
        shutil.copytree(assets_src, assets_dst, dirs_exist_ok=True)

    rendered = rendered.replace('src="../assets/', 'src="assets/')
    rendered = rendered.replace("src='../assets/", "src='assets/")

    output_path.write_text(rendered, encoding="utf-8")
    print(f"Página gerada em: {output_path}")


if __name__ == "__main__":
    generate_site()
