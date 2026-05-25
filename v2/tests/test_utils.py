"""Testes essenciais — utilitários puros (sem DB/IO)."""

from app.utils import normalize_phone, normalize_website, dedup_hash


# ───────────────────────── normalize_phone ─────────────────────────

class TestNormalizePhone:
    def test_pt_local_format(self):
        # 9 dígitos → adiciona 351
        assert normalize_phone("912345678") == "+351912345678"

    def test_pt_with_spaces(self):
        assert normalize_phone("912 345 678") == "+351912345678"

    def test_pt_with_country_code(self):
        assert normalize_phone("+351912345678") == "+351912345678"
        assert normalize_phone("351912345678") == "+351912345678"

    def test_invalid_returns_none(self):
        assert normalize_phone("123") is None
        assert normalize_phone("") is None
        assert normalize_phone(None) is None

    def test_strips_special_chars(self):
        assert normalize_phone("+351 (912) 345-678") == "+351912345678"


# ───────────────────────── normalize_website ─────────────────────────

class TestNormalizeWebsite:
    def test_strips_protocol(self):
        assert normalize_website("https://example.pt") == "example.pt"
        assert normalize_website("http://example.pt") == "example.pt"

    def test_strips_www(self):
        assert normalize_website("https://www.example.pt") == "example.pt"

    def test_strips_path_and_query(self):
        assert normalize_website("https://example.pt/sobre?x=1") == "example.pt"

    def test_lowercase(self):
        assert normalize_website("HTTPS://EXAMPLE.PT") == "example.pt"

    def test_none_or_empty(self):
        assert normalize_website(None) is None
        assert normalize_website("") is None


# ───────────────────────── dedup_hash ─────────────────────────

class TestDedupHash:
    def test_same_input_same_hash(self):
        h1 = dedup_hash("Padaria Lisboa", "+351912345678", "padaria.pt", "info@padaria.pt")
        h2 = dedup_hash("Padaria Lisboa", "+351912345678", "padaria.pt", "info@padaria.pt")
        assert h1 == h2

    def test_case_insensitive_name(self):
        h1 = dedup_hash("Padaria Lisboa", "912345678", "padaria.pt", "info@padaria.pt")
        h2 = dedup_hash("PADARIA LISBOA", "912345678", "padaria.pt", "info@padaria.pt")
        assert h1 == h2

    def test_different_input_different_hash(self):
        h1 = dedup_hash("A", "111", "a.pt", "a@a.pt")
        h2 = dedup_hash("B", "222", "b.pt", "b@b.pt")
        assert h1 != h2

    def test_handles_none(self):
        # Não deve crashar
        h = dedup_hash("X", None, None, None)
        assert isinstance(h, str)
        assert len(h) == 32  # SHA256[:32]

    def test_phone_normalized(self):
        # Espaços e símbolos no telefone não afectam dedup
        h1 = dedup_hash("X", "+351 912 345 678", "x.pt", "x@x.pt")
        h2 = dedup_hash("X", "+351912345678", "x.pt", "x@x.pt")
        assert h1 == h2
