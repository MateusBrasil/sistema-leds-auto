# Sistema de Leads — Instruções de Configuração

## Passo 1 — Criar a Planilha Google

1. Acesse [sheets.google.com](https://sheets.google.com) e crie uma nova planilha
2. No menu superior, clique em **Extensões → Apps Script**
3. Apague o código padrão e cole todo o conteúdo do arquivo `Codigo.gs`
4. Salve (Ctrl+S) e volte para a planilha
5. Recarregue a página — aparecerá o menu **"🎯 Sistema de Leads"**
6. Clique em **⚙️ Inicializar Planilha**

---

## Passo 2 — Chaves de API (preencher na aba "Config")

### Google Places API (Google Maps)
- Acesse: https://console.cloud.google.com
- Crie um projeto → Ative "Places API"
- Gere uma chave de API em "Credenciais"
- **Gratuito:** $200 de crédito/mês (~6.600 buscas)

### Hunter.io (Enriquecimento de E-mail)
- Cadastre em: https://hunter.io
- Vá em API → copie sua chave
- **Gratuito:** 25 buscas/mês

### Brevo (Envio de E-mail)
- Cadastre em: https://brevo.com
- Vá em SMTP & API → copie a chave
- **Gratuito:** 300 e-mails/dia

### Apify (LinkedIn + Instagram)
- Cadastre em: https://apify.com
- Vá em Settings → Integrations → API token
- **Gratuito:** $5 de crédito/mês (≈ 50-100 leads)

### Evolution API (WhatsApp) — RECOMENDADO GRÁTIS
Opção A — Self-hosted (Docker):
```bash
docker run -d \
  --name evolution-api \
  -p 8080:8080 \
  -e AUTHENTICATION_API_KEY=sua_chave_aqui \
  atendai/evolution-api:latest
```
- Após subir, acesse http://localhost:8080
- Crie uma instância e escaneie o QR Code com seu WhatsApp

Opção B — Deploy gratuito na Railway:
- Acesse: https://railway.app
- Deploy do repositório: https://github.com/EvolutionAPI/evolution-api
- Configure as variáveis de ambiente no painel

---

## Passo 3 — Preencher a aba Config

| Chave | Onde pegar |
|-------|-----------|
| GOOGLE_PLACES_API_KEY | Google Cloud Console |
| HUNTER_API_KEY | hunter.io → API |
| BREVO_API_KEY | brevo.com → SMTP & API |
| EMAIL_FROM | Seu e-mail remetente |
| EMAIL_FROM_NAME | Nome que aparece no e-mail |
| EVOLUTION_API_URL | URL da sua instância (ex: http://localhost:8080) |
| EVOLUTION_API_KEY | Chave que você definiu no Docker |
| EVOLUTION_INSTANCE | Nome da instância criada |
| APIFY_API_TOKEN | apify.com → Settings → API token |

---

## Como Usar

### Buscar leads do Google Maps
1. Menu → 🔍 Buscar Leads → 📍 Google Maps
2. Informe o nicho (ex: "clínica odontológica")
3. Informe a cidade (ex: "Curitiba PR")
4. Os leads aparecem automaticamente na aba Leads

### Buscar leads do LinkedIn / Instagram
1. Menu → 🔍 Buscar Leads → 💼 LinkedIn ou 📸 Instagram
2. Aguarde ~2 minutos
3. Menu → 📥 Importar Resultados (Apify)

### Enriquecer e-mails
1. Menu → ✉️ Enriquecer E-mails
2. O sistema busca automaticamente e-mails dos leads que têm website mas não têm e-mail

### Disparar e-mail
1. Menu → 🚀 Disparar → 📧 Enviar E-mails
2. Informe assunto e corpo (use {{nome}} para personalizar)
3. Só envia para leads com e-mail e que ainda não receberam

### Disparar WhatsApp
1. Menu → 🚀 Disparar → 💬 Enviar WhatsApp
2. Informe a mensagem (use {{nome}} para personalizar)
3. Só envia para leads com telefone e que ainda não receberam

---

## Estrutura da Planilha (aba Leads)

| Coluna | Campo |
|--------|-------|
| A | Data Adição |
| B | Fonte (Google Maps / LinkedIn / Instagram) |
| C | Nome/Empresa |
| D | Website |
| E | Telefone/WhatsApp |
| F | E-mail |
| G | Endereço/Localização |
| H | Avaliação (Google) |
| I | Nº de Avaliações |
| J | Status |
| K | Email Enviado |
| L | WhatsApp Enviado |
| M | ID/URL Fonte |

---

## Observações Importantes

- **WhatsApp:** O número deve estar no formato internacional (55 + DDD + número)
- **Rate Limits:** O script já tem delays para evitar bloqueios
- **LinkedIn/Instagram:** Scraping respeita os termos de uso via Apify
- **Logs:** Toda atividade fica registrada na aba "Log"
- Leads marcados como "Enviado" não recebem novamente (evita spam)
