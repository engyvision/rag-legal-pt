"""Translation service using Google Cloud Translation API."""

import logging
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    from google.cloud import translate_v2 as translate
except ImportError:
    translate = None

from ..core.config import settings

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translating text between Portuguese and English."""

    def __init__(self):
        self.client = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._initialize()

    def _initialize(self):
        """Initialize Google Cloud Translation client."""
        try:
            if translate is None:
                logger.warning(
                    "Google Cloud Translation not available. Install google-cloud-translate."
                )
                return

            self.client = translate.Client()
            logger.info("Translation client initialized successfully")

        except Exception as e:
            logger.warning(f"Could not initialize translation client: {e}")
            self.client = None

    def translate_to_portuguese(self, text: str) -> str:
        """Translate text from any language to Portuguese."""
        if not self.client or not text.strip():
            return text

        try:
            # Detect source language first
            detection = self.client.detect_language(text)
            source_lang = detection["language"]

            # If already Portuguese, return as-is
            if source_lang == "pt":
                return text

            # Translate to Portuguese
            result = self.client.translate(
                text, target_language="pt", source_language=source_lang
            )

            translated_text = result["translatedText"]
            logger.info(f"Translated from {source_lang} to Portuguese")
            return translated_text

        except Exception as e:
            logger.error(f"Translation to Portuguese failed: {e}")
            return text  # Return original text as fallback

    def translate_to_english(self, text: str) -> str:
        """Translate text from Portuguese to English."""
        if not self.client or not text.strip():
            return text

        try:
            # Translate to English
            result = self.client.translate(
                text, target_language="en", source_language="pt"
            )

            translated_text = result["translatedText"]
            logger.info("Translated from Portuguese to English")
            return translated_text

        except Exception as e:
            logger.error(f"Translation to English failed: {e}")
            return text  # Return original text as fallback

    def detect_language(self, text: str) -> str:
        """Detect the language of the input text."""
        if not self.client or not text.strip():
            return "pt"  # Default to Portuguese

        try:
            detection = self.client.detect_language(text)
            detected_lang = detection["language"]
            confidence = detection["confidence"]

            logger.info(
                f"Detected language: {detected_lang} (confidence: {confidence})"
            )
            return detected_lang

        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return "pt"  # Default to Portuguese

    async def atranslate_to_portuguese(self, text: str) -> str:
        """Async wrapper for translate_to_portuguese."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, self.translate_to_portuguese, text
        )

    async def atranslate_to_english(self, text: str) -> str:
        """Async wrapper for translate_to_english."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, self.translate_to_english, text
        )

    async def adetect_language(self, text: str) -> str:
        """Async wrapper for detect_language."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.detect_language, text)

    def is_available(self) -> bool:
        """Check if translation service is available."""
        return self.client is not None


# Global translation service instance
translation_service = TranslationService()
