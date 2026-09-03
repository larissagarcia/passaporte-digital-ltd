# 🎖️ Passaporte Digital - LTD

O **Passaporte Digital do LTD (Laboratório de Tecnologia Digital)** é uma plataforma estática, leve e automatizada desenvolvida para registrar a presença de alunos em oficinas, coletar feedbacks de reação (1 a 5 estrelas) e disponibilizar uma galeria virtual de insígnias de conquistas.

---

## 🛠️ Arquitetura do Projeto

O projeto utiliza uma abordagem de **Gerador de Site Estático (SSG)** com **Python** hospedado 100% gratuitamente via **GitHub Pages** e automatizado pelo **GitHub Actions**.

```text
[ Resposta do Aluno ] ──► [ Formulário Tally / Google Forms ]
                                     │
                                     ▼
                          [ Planilha / data/alunos.json ]
                                     │
                                     ▼
                          [ Script Python: generator.py ]
                                     │
                                     ▼
                          [ Template Jinja2: index.html ]
                                     │
                                     ▼
                          [ Build via GitHub Actions ]
                                     │
                                     ▼
                          [ Publicação no GitHub Pages ]
