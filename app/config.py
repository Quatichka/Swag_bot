import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: tuple[int, ...]
    admin_chat_id: int | None
    channel_url: str
    manager_username: str
    db_path: Path
    images_dir: Path
    reject_votes: int  # сколько голосов в группе нужно, чтобы отклонить заказ

    @property
    def notify_targets(self) -> tuple[int, ...]:
        """Куда слать заявки: в группу админов, если задана, иначе каждому админу в личку."""
        return (self.admin_chat_id,) if self.admin_chat_id else self.admin_ids


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN не задан — скопируйте .env.example в .env и заполните")

    admin_ids = tuple(int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x)
    if not admin_ids:
        raise RuntimeError("ADMIN_IDS не задан — укажите хотя бы один Telegram ID админа")

    chat_id = os.getenv("ADMIN_CHAT_ID", "").strip()
    return Config(
        bot_token=token,
        admin_ids=admin_ids,
        admin_chat_id=int(chat_id) if chat_id else None,
        channel_url=os.getenv("CHANNEL_URL", "https://t.me/SSwag_studio"),
        manager_username=os.getenv("MANAGER_USERNAME", "nils4021").lstrip("@"),
        db_path=BASE_DIR / "data" / "orders.db",
        images_dir=BASE_DIR / "images",
        reject_votes=max(1, int(os.getenv("REJECT_VOTES", "5"))),
    )


config = load_config()
