"""
Intelligence Module - Unified AI Interface
Main entry point providing backwards compatibility with specialized AI components.
All advanced AI functionality is now handled by dedicated modules.
"""

import re
from typing import Optional

# Import specialized AI modules
from .selector_manager import SelectorManager
from .visual_analyzer import VisualAnalyzer
from .popup_handler import PopupHandler
from .page_analyzer import PageAnalyzer
from .utils import clean_json_response

# Legacy compatibility imports
from Helpers.Neo_Helpers.Managers.db_manager import knowledge_db
from Helpers.Neo_Helpers.Managers.api_key_manager import gemini_api_call_with_rotation


# Legacy compatibility functions - delegate to specialized modules
async def analyze_page_and_update_selectors(page, context_key: str, force_refresh: bool = False, info: Optional[str] = None):
    """Delegate to VisualAnalyzer"""
    return await VisualAnalyzer.analyze_page_and_update_selectors(page, context_key, force_refresh, info)


async def attempt_visual_recovery(page, context_name: str) -> bool:
    """Delegate to VisualAnalyzer"""
    return await VisualAnalyzer.attempt_visual_recovery(page, context_name)


def get_selector(context: str, element_key: str) -> str:
    """Delegate to SelectorManager"""
    return SelectorManager.get_selector(context, element_key)


async def get_selector_auto(page, context_key: str, element_key: str) -> str:
    """Delegate to SelectorManager"""
    return await SelectorManager.get_selector_auto(page, context_key, element_key)


async def extract_league_data(page, context_key: str = "home_page"):
    """Delegate to PageAnalyzer"""
    return await PageAnalyzer.extract_league_data(page, context_key)


async def fb_universal_popup_dismissal(page, context: str = "fb_generic", html: Optional[str] = None, monitor_interval: int = 0) -> bool:
    """Delegate to PopupHandler"""
    return await PopupHandler.fb_universal_popup_dismissal(page, context, html, monitor_interval)


# Module-level exports for backwards compatibility
__all__ = [
    'clean_json_response',
    'analyze_page_and_update_selectors',
    'attempt_visual_recovery',
    'get_selector',
    'get_selector_auto',
    'extract_league_data',
    'fb_universal_popup_dismissal',
    'SelectorManager',
    'VisualAnalyzer',
    'PopupHandler',
    'PageAnalyzer'
]
