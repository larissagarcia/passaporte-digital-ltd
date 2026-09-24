"""Gera o index.html estático publicado no GitHub Pages.

O build produz apenas a casca da página: layout e a galeria de insígnias com
todos os módulos bloqueados. Nenhum dado de aluno entra aqui — nome, e-mail e
progresso vêm da API depois do login (ADR-001).

Antes, este script embutia a turma inteira em `window.passaporteData`, o que
publicava os e-mails dos alunos no HTML. Ver ADR-001, seção 1.1.
"""

import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURSO_FILE = PROJECT_ROOT / "data" / "curso.json"
TEMPLATE_DIR = PROJECT_ROOT / "src" / "templates"
OUTPUT_FILE = PROJECT_ROOT / "index.html"

# Vazio = mesma origem: a página e a API são servidas pelo mesmo servidor, então
# o script.js monta um caminho relativo. Só preencha (via PASSAPORTE_API_BASE)
# se o frontend for hospedado fora do PythonAnywhere — e, nesse caso, libere a
# origem dele em PASSAPORTE_CORS_ORIGENS na API.
API_BASE_PADRAO = ""


def carregar_modulos():
    """Módulos e oficinas para a galeria estática.

    Só o que é público: número, nome, imagens e os nomes das oficinas. A
    palavra-chave de cada oficina fica de fora — ela é o segredo que valida a
    presença e nunca pode ir para o HTML.
    """
    curso = json.loads(CURSO_FILE.read_text(encoding="utf-8"))
    return [
        {
            "numero": modulo["numero"],
            "nome": modulo["nome"],
            "descricao": modulo.get("descricao", ""),
            "imagem_conquistada": modulo["imagem_conquistada"],
            "imagem_pendente": modulo["imagem_pendente"],
            "oficinas": [
                {
                    "slug": oficina["slug"],
                    "ordem": oficina["ordem"],
                    "nome": oficina["nome"],
                    "data": oficina.get("data"),
                }
                for oficina in modulo["oficinas"]
            ],
        }
        for modulo in curso["modulos"]
    ]


def generate_site():
    modulos = carregar_modulos()
    if not modulos:
        raise ValueError(f"Nenhum módulo encontrado em {CURSO_FILE}")

    api_base = os.environ.get("PASSAPORTE_API_BASE", API_BASE_PADRAO).rstrip("/")

    environment = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    template = environment.get_template("index.html")
    OUTPUT_FILE.write_text(
        template.render(modulos=modulos, api_base=api_base),
        encoding="utf-8",
    )

    oficinas = sum(len(m["oficinas"]) for m in modulos)
    print(f"Página gerada em {OUTPUT_FILE}")
    print(f"  {len(modulos)} módulos, {oficinas} oficinas, API em {api_base or 'mesma origem'}")


if __name__ == "__main__":
    generate_site()
