"""Who the bot listens to and where it may talk.

The bot acts only for allow-listed admins, and only in the ops group or an
admin's private chat. Anyone else, or any other chat (for example a group a
buyer is in), is ignored.
"""

from __future__ import annotations

from dataclasses import dataclass

from baby_arb.config import Settings


@dataclass(frozen=True)
class Access:
    """Allow-lists derived from settings."""

    admin_ids: frozenset[int]
    chat_ids: frozenset[int]

    @classmethod
    def from_settings(cls, settings: Settings) -> Access:
        """Admins' private chats (chat ID == user ID) plus the ops group."""
        chats = set(settings.admin_ids)
        if settings.telegram_ops_chat_id is not None:
            chats.add(settings.telegram_ops_chat_id)
        return cls(admin_ids=settings.admin_ids, chat_ids=frozenset(chats))

    def allows(self, user_id: int | None, chat_id: int | None) -> bool:
        """True when an admin writes in an allowed chat."""
        return (
            user_id is not None
            and chat_id is not None
            and user_id in self.admin_ids
            and chat_id in self.chat_ids
        )
