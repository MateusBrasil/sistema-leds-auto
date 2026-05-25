"""Substitui placeholders {{nome}}, {{primeiro_nome}}, {{cidade}}, {{nicho}},
{{nome_negocio}}, {{personalizacao}} no template do utilizador.
"""

import re

from ...models import Lead


def render_template(template: str, lead: Lead) -> str:
    first_name = (lead.name or "").split()[0] if lead.name else ""
    mapping = {
        "nome": first_name or (lead.name or ""),
        "primeiro_nome": first_name,
        "nome_completo": lead.name or "",
        "nome_negocio": lead.name or "",
        "cidade": lead.city or "",
        "nicho": lead.niche or "",
        "personalizacao": lead.personalization or "",
    }

    def repl(match: re.Match) -> str:
        key = match.group(1).strip().lower()
        return mapping.get(key, match.group(0))

    return re.sub(r"\{\{\s*([\w_]+)\s*\}\}", repl, template)
