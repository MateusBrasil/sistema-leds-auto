"""Testa o bug C4: match exacto vs últimos 9 dígitos no webhook WhatsApp."""

from app.routes.webhooks import _extract_whatsapp_payload


class TestExtractPayload:
    def test_evolution_format(self):
        payload = {
            "data": {
                "key": {"remoteJid": "351912345678@s.whatsapp.net"},
                "message": {"conversation": "Olá!"},
            }
        }
        phone, text = _extract_whatsapp_payload(payload)
        assert phone == "351912345678"
        assert text == "Olá!"

    def test_zapi_format_text_obj(self):
        payload = {"phone": "351912345678", "text": {"message": "ok"}}
        phone, text = _extract_whatsapp_payload(payload)
        assert phone == "351912345678"
        assert text == "ok"

    def test_zapi_format_message_string(self):
        payload = {"phone": "351912345678", "message": "ok"}
        phone, text = _extract_whatsapp_payload(payload)
        assert phone == "351912345678"
        assert text == "ok"

    def test_extended_text(self):
        payload = {
            "data": {
                "key": {"remoteJid": "351912345678@s.whatsapp.net"},
                "message": {"extendedTextMessage": {"text": "Longa mensagem"}},
            }
        }
        phone, text = _extract_whatsapp_payload(payload)
        assert text == "Longa mensagem"

    def test_missing_data_returns_none(self):
        phone, text = _extract_whatsapp_payload({})
        assert phone is None
        assert text is None
