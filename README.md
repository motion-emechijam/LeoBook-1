# Leo
**Developer**: Matterialless LLC  
**Chief Engineer**: Emenike Chinenye James
**Powered by**: Grok 4.1 & Gemini 3

## PROLOGUE
Leo v5.0: The refined, autonomous betting ecosystem. This system represents the pinnacle of self-healing automation, powered by **AIGO (AI-Guided-Operation)**—a proprietary recovery framework that combines multi-path execution with strategic AI analysis to maintain continuous operations under dynamic UI conditions.

A comprehensive AI-powered system that observes, analyzes, predicts, and executes betting strategies with advanced self-healing capabilities.

The prime objective of this Agent is to handle all sports analysis and betting accurately, enabling passive income from sports betting without constant manual interaction.

OVERVIEW:
Leo combines advanced data analysis, machine learning, and automated execution. The system features a hybrid AI architecture using xAI's Grok 4 and Google's Gemini for high-precision selector discovery, multimodal analysis, and complex UI mapping.

- **AIGO V5 Resilience**: 
  - **Phase 0 Confidence Retry**: Validates visual discovery with local AI, retrying low-confidence probes before escalation.
  - **Heatmap-Aware Healing**: Tracks failed selectors and directs AI to avoid broken patterns, accelerating recovery.
  - **Intra-Cycle Redundancy**: Provides Primary (Selector) and Backup (Extraction/Action) paths simultaneously for zero-cycle-failure goal.
- **Codebase Optimization**: 
  - Removed 170+ lines of legacy recovery code (`recovery.py`, `visual_analysis.py`).
  - Integrated AIGO into critical flows (Login, Betslip, Balance) for 100% self-healing.
  - Centralized task tracking and implementation logs into brain artifacts.

2. OBSERVE & DECIDE (Chapters 0, 1A & 1B):
   - **Chapter 0 (Review)**: Cross-syncs past outcomes and updates momentum weights.
   - **Chapter 1A/1B (Extraction & Analysis)**: Generates high-confidence predictions via the Rule Engine.

3. ACT: CHAPTER 1C & 2A (Betting Orchestration):
   - **Chapter 1C (Discovery)**: Navigates to each match, extracts a single booking code.
   - **Chapter 2A (Booking)**: Batch-injects all harvested codes for the day and places a single combined accumulator bet.
   - **Financial Safety**: Stake is calculated using a Fractional Kelly formula (min ₦100, max 50% balance).

4. VERIFY & WITHDRAW (Chapter 2B):
   - **Chapter 2B (Withdrawal)**: Checks triggers (₦10k balance) and maintains bankroll floor (₦5,000).
   - **Chapter 3 (Monitoring)**: Finalizes the cycle by logging `CYCLE_COMPLETE` after recording all events.

SUPPORTED BETTING MARKETS:
1. 1X2 | 2. Double Chance | 3. Draw No Bet | 4. BTTS | 5. Over/Under | 6. Goal Ranges | 7. Correct Score | 8. Clean Sheet | 9. Asian Handicap | 10. Combo Bets | 11. Team O/U

SYSTEM COMPONENTS:
- **Leo.py**: Main controller orchestrating the "Observe, Decide, Act" core loop.
- **Core/**: System Intelligence (AIGO Engine, Page/Visual Analysis, System Primitives).
- **Data/**: Persistence Layer (Supabase Sync, CSV Storage, DB Helpers).
- **Modules/**: Browser Automation (Flashscore Extractors, Football.com Interaction).
- **LeoBookApp/**: Cross-Platform Elite Betting Dashboard (Flutter).
# LeoBook - Elite Betting Dashboard

Elite, autonomous betting dashboard with direct GitHub data synchronization and persistent local caching.

## Key Features
- **Supabase Backend**: Cloud-native data storage for instant global access and real-time updates.
- **Brand Enrichment**: Automatic extraction of Team Crests, Region Flags, and detailed League/Team URLs.
- **Offline Caching**: Built-in persistence for seamless viewing under low-network conditions.
- **High-Fidelity Predictions**: Real-time accent lines and live-status indicators.
- **Match Registry**: `Data/Store/fb_matches.csv` (Mapped URLs and booking codes).
- **Reference Data**: `Data/Store/region_league.csv` and `teams.csv` (Brand asset registries).
- **Code Quality**: 100% migrated to modern `withValues` API and standardized `debugPrint` logging.
- **Scripts/**: Utility tools for reporting, DB maintenance, and Cloud Sync.

MAINTENANCE:
- Monitor **`DB/audit_log.csv`** for real-time financial transparency.
- Review **`walkthrough.md`** for detailed implementation logs of current session.
- Refer to **`pilot_algorithm.md`** for exhaustive file and function documentation.
- Use `python Scripts/sync_to_supabase.py` to push latest predictions to the cloud.
