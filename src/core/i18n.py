"""Internationalization (i18n) support for PieMenu.

Handles loading and installing Qt translation files based on
user language preferences or system locale.
"""

import os

from PyQt6.QtCore import QLocale, QTranslator
from PyQt6.QtWidgets import QApplication

from src.core.logger import get_logger

logger = get_logger(__name__)

# Global translator instance to keep it alive
_TRANSLATOR: QTranslator | None = None


def install_translator(app: QApplication, language: str = "auto") -> None:
    """Install a translator based on the language setting.

    Args:
        app: QApplication instance
        language: Language code ('auto', 'en', 'ja')
                 'auto' will detect system locale

    Note:
        If the translation file is not found or fails to load,
        the application will fall back to English (source language).
    """
    global _TRANSLATOR

    # Remove existing translator if any
    if _TRANSLATOR:
        app.removeTranslator(_TRANSLATOR)
        _TRANSLATOR = None

    lang_code = language
    if language == "auto":
        # Detect system locale
        sys_locale = QLocale.system().name()  # e.g. "ja_JP", "en_US"
        lang_code = sys_locale.split("_")[0]
        logger.info(f"Detected system language: {lang_code} (from {sys_locale})")

    # If English (default), we don't strictly need a translator if source is in English,
    # but we might want one if we have en_US.qm vs en_GB.qm etc.
    # For now, if "en", we assume source default.
    if lang_code == "en":
        logger.info("Using default language (English)")
        return

    # Load translation file
    # We look for files like "piemenu_ja.qm" in resources/translations
    from src.core.utils import get_resource_path

    qm_path = get_resource_path(
        os.path.join("resources", "translations", f"piemenu_{lang_code}.qm")
    )

    if os.path.exists(qm_path):
        translator = QTranslator()
        if translator.load(qm_path):
            app.installTranslator(translator)
            _TRANSLATOR = translator
            logger.info(f"Loaded translation: {qm_path}")
        else:
            logger.error(f"Failed to load translation file: {qm_path}")
    else:
        logger.warning(f"Translation file not found: {qm_path}")
