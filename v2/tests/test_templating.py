"""Testes de templating (render_template)."""

from app.services.messaging import render_template
from app.models import Lead


def _make_lead(**kwargs):
    defaults = {
        "name": "Padaria Central de Lisboa",
        "city": "Lisboa",
        "niche": "padaria",
        "personalization": "frase única",
    }
    defaults.update(kwargs)
    return Lead(**defaults)


class TestRenderTemplate:
    def test_basic_substitution(self):
        out = render_template("Olá {{nome}}", _make_lead())
        assert out == "Olá Padaria"  # primeiro nome

    def test_nome_negocio_full_name(self):
        out = render_template("Sobre {{nome_negocio}}", _make_lead())
        assert "Padaria Central de Lisboa" in out

    def test_cidade(self):
        out = render_template("em {{cidade}}", _make_lead())
        assert out == "em Lisboa"

    def test_nicho(self):
        out = render_template("nicho={{nicho}}", _make_lead())
        assert out == "nicho=padaria"

    def test_personalizacao(self):
        out = render_template("X {{personalizacao}} Y", _make_lead())
        assert "frase única" in out

    def test_multiple_in_same_string(self):
        out = render_template("{{nome}} de {{cidade}}", _make_lead())
        assert out == "Padaria de Lisboa"

    def test_unknown_placeholder_kept_as_is(self):
        out = render_template("{{desconhecido}}", _make_lead())
        assert "{{desconhecido}}" in out

    def test_case_insensitive(self):
        out = render_template("{{NOME}}", _make_lead())
        assert out == "Padaria"

    def test_no_personalization_uses_empty(self):
        lead = _make_lead(personalization=None)
        out = render_template("X{{personalizacao}}Y", lead)
        assert out == "XY"
