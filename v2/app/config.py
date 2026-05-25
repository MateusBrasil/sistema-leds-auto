from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    SENDER_NAME: str = "VV TRAFFIC DATA"
    SENDER_EMAIL: str = "wtrafficdataeu@gmail.com"
    SENDER_COUNTRY_CODE: str = "351"

    GOOGLE_PLACES_API_KEY: str = ""
    APIFY_API_TOKEN: str = ""

    HUNTER_API_KEY: str = ""
    ZEROBOUNCE_API_KEY: str = ""

    BREVO_API_KEY: str = ""

    WHATSAPP_PROVIDER: str = "evolution"
    ZAPI_INSTANCE_ID: str = ""
    ZAPI_TOKEN: str = ""
    ZAPI_CLIENT_TOKEN: str = ""

    EVOLUTION_BASE_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str = ""
    EVOLUTION_INSTANCE: str = "vvtraffic"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    GROQ_API_KEY: str = ""

    # Notifications
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    SLACK_WEBHOOK_URL: str = ""

    # Webhook security (assina os webhooks com HMAC se preenchido)
    BREVO_WEBHOOK_SECRET: str = ""
    WHATSAPP_WEBHOOK_SECRET: str = ""

    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    APP_SECRET: str = "change-me"
    APP_USERNAME: str = "admin"
    APP_PASSWORD: str = "change-me"

    DATABASE_URL: str = "sqlite:///./data/leads.db"
    PUBLIC_WEBHOOK_BASE: str = ""

    LOG_LEVEL: str = "INFO"

    WHATSAPP_MAX_PER_DAY: int = 50
    EMAIL_MAX_PER_DAY: int = 100
    SEND_DELAY_MS: int = 1500

    FOLLOWUP_D1: int = 0
    FOLLOWUP_D2: int = 2
    FOLLOWUP_D3: int = 4
    FOLLOWUP_D4: int = 7
    FOLLOWUP_D5: int = 10


settings = Settings()
