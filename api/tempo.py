"""Data local do LTD.

Existe por um motivo só: o SQLite trabalha em UTC, e comparar a data de uma
oficina com `date('now')` daria errado nas oficinas da noite. No horário de
Brasília (UTC-3), às 21h já é o dia seguinte em UTC — a presença de uma
oficina noturna seria recusada com "hoje não é o dia desta oficina".

O fuso é configurável por PASSAPORTE_FUSO para o caso de o LTD rodar em outra
região.
"""

import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FUSO_PADRAO = "America/Sao_Paulo"


def fuso():
    nome = os.environ.get("PASSAPORTE_FUSO", FUSO_PADRAO)
    try:
        return ZoneInfo(nome)
    except (ZoneInfoNotFoundError, ValueError):
        # Sem a base de fusos instalada, cai no offset fixo de Brasília. O
        # Brasil não usa horário de verão desde 2019, então UTC-3 é estável.
        return timezone(timedelta(hours=-3))


def hoje_local() -> date:
    return datetime.now(fuso()).date()


def hoje_iso() -> str:
    """Data de hoje como 'AAAA-MM-DD', no formato em que `oficinas.data` é gravada."""
    return hoje_local().isoformat()


def formatar_br(data_iso: str) -> str:
    """'2026-10-01' -> '01/10/2026', para mensagem de erro legível."""
    try:
        return date.fromisoformat(data_iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return data_iso
