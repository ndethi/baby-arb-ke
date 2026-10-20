"""Demand signal collectors package."""

from .base import BaseCollector
from .facebook import FacebookCollector
from .instagram_public import InstagramPublicCollector
from .jiji import JijiCollector
from .tiktok_public import TikTokPublicCollector

__all__ = [
    "BaseCollector",
    "FacebookCollector",
    "InstagramPublicCollector",
    "JijiCollector",
    "TikTokPublicCollector",
]