from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    brand_name: str = "往事榨汁机"
    brand_en: str = "Memory Juicer"
    brand_slogan: str = "榨取记忆，真假随缘"

    database_url: str = f"sqlite:///{(DATA_DIR / 'memory_juicer.db').as_posix()}"

    dashscope_api_key: str = ""
    llm_model: str = "qwen-plus"
    asr_model: str = "paraformer-realtime-v2"

    app_base_url: str = "http://127.0.0.1:8000"

    max_audio_mb: int = 25
    max_photo_mb: int = 10

    @property
    def ai_enabled(self) -> bool:
        return bool(self.dashscope_api_key.strip())


settings = Settings()

for _d in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)