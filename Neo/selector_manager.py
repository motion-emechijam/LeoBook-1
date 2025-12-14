"""
Selector Manager Module
Handles CSS selector storage, retrieval, and management for web automation.
Responsible for maintaining the knowledge base of UI selectors with auto-healing capabilities.
"""

import os
from typing import Dict, Any, Optional

from Helpers.Neo_Helpers.Managers.db_manager import load_knowledge, save_knowledge, knowledge_db


class SelectorManager:
    """Manages CSS selectors for web automation with auto-healing capabilities"""

    @staticmethod
    def get_selector(context: str, element_key: str) -> str:
        """Legacy synchronous accessor (does not auto-heal)."""
        return knowledge_db.get(context, {}).get(element_key, "")

    @staticmethod
    async def get_selector_auto(page, context_key: str, element_key: str) -> str:
        """
        SMART ACCESSOR:
        1. Checks if selector exists in DB.
        2. Validates if selector is present on the current page.
        3. If missing or invalid, AUTOMATICALLY triggers AI re-analysis and returns fresh selector.
        """
        # Import here to avoid circular imports
        from .intelligence import analyze_page_and_update_selectors

        # 1. Quick Lookup
        selector = knowledge_db.get(context_key, {}).get(element_key)

        # 2. Validation
        is_valid = False
        if selector:
            # --- NEW: Wait up to 2 minutes for the selector to be attached to the DOM ---
            # This prevents premature auto-healing due to network lag or slow rendering.
            try:
                # Use wait_for_selector which is more robust for this check.
                await page.wait_for_selector(selector, state='attached', timeout=120000)  # 2 minutes
                is_valid = True
            except Exception as e:
                print(f"    [Selector Stale] '{element_key}' ('{selector}') not found after 2 min wait.")
                is_valid = False

        # 3. Auto-Healing
        if not is_valid:
            print(
                f"    [Auto-Heal] Selector '{element_key}' in '{context_key}' invalid/missing. Initiating AI repair..."
            )
            info = f"Selector '{element_key}' in '{context_key}' invalid/missing."
            # Run AI Analysis (which now captures its own snapshot)
            await analyze_page_and_update_selectors(page, context_key, force_refresh=True, info=info)

            # Re-fetch
            selector = knowledge_db.get(context_key, {}).get(element_key)

            if selector:
                print(f"    [Auto-Heal Success] New selector for '{element_key}': {selector}")
            else:
                print(f"    [Auto-Heal Failed] AI could not find '{element_key}' even after refresh.")

        result = selector or ""
        return str(result)

    @staticmethod
    def has_selectors_for_context(context: str) -> bool:
        """Check if selectors exist for a given context"""
        return context in knowledge_db and bool(knowledge_db[context])

    @staticmethod
    def get_all_selectors_for_context(context: str) -> Dict[str, str]:
        """Get all selectors for a specific context"""
        return knowledge_db.get(context, {})

    @staticmethod
    def update_selector(context: str, key: str, selector: str):
        """Update a specific selector in the knowledge base"""
        if context not in knowledge_db:
            knowledge_db[context] = {}
        knowledge_db[context][key] = selector
        save_knowledge()

    @staticmethod
    def remove_selector(context: str, key: str):
        """Remove a specific selector from the knowledge base"""
        if context in knowledge_db and key in knowledge_db[context]:
            del knowledge_db[context][key]
            save_knowledge()

    @staticmethod
    def clear_context_selectors(context: str):
        """Clear all selectors for a specific context"""
        if context in knowledge_db:
            knowledge_db[context] = {}
            save_knowledge()

    @staticmethod
    def get_contexts_list() -> list:
        """Get list of all available contexts"""
        return list(knowledge_db.keys())

    @staticmethod
    def validate_selector_format(selector: str) -> bool:
        """Basic validation of CSS selector format"""
        if not selector or not isinstance(selector, str):
            return False

        # Check for obviously invalid patterns
        invalid_patterns = [
            ':contains(',  # Non-standard jQuery selector
            'skeleton',    # Loading state selectors
            'ska__',       # Skeleton loading selectors
        ]

        for pattern in invalid_patterns:
            if pattern in selector.lower():
                return False

        return True
