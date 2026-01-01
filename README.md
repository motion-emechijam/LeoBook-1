# Leo
**Manufacturer**: Emenike Chinenye James  
**Powered by**: Qwen3-VL & Custom Llama Server


"""
Leo v3.0: Advanced Autonomous Agent (Manufacturer: Emenike Chinenye James)

A comprehensive AI-powered system that observes, analyzes, predicts, and executes betting strategies.

OVERVIEW:
Leo is an intelligent football prediction system that combines advanced data analysis, machine learning,

and automated betting execution. The system features a fully local, privacy-focused AI architecture using
Qwen3-VL for vision analysis and Llama Server for semantic reasoning.

NEW IN v2.8.0 (LOCAL AI UPGRADE):
- **Local Vision Engine**: Replaced Google Gemini with a local Qwen3-VL model running on port 8080.
- **Split-Model Support**: Custom `llama-server` integration to run split GGUF files (Brain + Eyes) natively.
- **Privacy First**: All visual analysis and team matching logic now happens 100% locally.
- **Improved Semantic Matching**: `llm_matcher.py` updated to communicate with the local inference server.

CORE ARCHITECTURE:
- Dual-browser system (Flashscore + Football.com) with persistent login sessions
- **Local Inference Server**: Custom `run_split_model.bat` orchestrating the Qwen3-VL multimodal engine.
- Advanced prediction engine with 11+ betting markets support
- Self-learning AI with rule-based and ML components
- Automated outcome review with retry mechanisms
- Production-grade monitoring and health checks

MAIN WORKFLOW:
1. INFRASTRUCTURE INIT:
   - **Windows**: `.\Mind\run_split_model.bat` (or let Leo auto-start it)
   - **Linux/Codespaces**: `bash Mind/setup_linux_env.sh` (one-time setup) -> `python Leo.py`
   - Initialize Databases: `python Leo.py`

2. DATA COLLECTION PHASE:
   - Navigate to Flashscore.com/football scheduled matches
   - Extract match metadata (ID, URLs, teams, times)
   - **Local Vision**: Analyze UI elements using local Qwen3-VL for robust anti-bot detection

3. ANALYSIS & PREDICTION PHASE:
   - Process extracted data through RuleEngine (Neo/model.py)
   - **Semantic Matching**: Use local LLM to resolve team name discrepancies
   - Generate predictions across 11+ betting markets
   - Apply machine learning confidence scoring

4. BETTING EXECUTION PHASE:
   - Match predictions with Football.com betting markets
   - Use AI to identify safest betting opportunities
   - Execute automated bet placement with stake management  

5. OUTCOME REVIEW & LEARNING PHASE:
   - Monitor completed matches for results
   - Evaluate prediction accuracy across all markets
   - Update learning weights based on performance

ADVANCED FEATURES:
- **Zero-Cost Operation**: Removed dependency on paid cloud API keys for core vision tasks.
- Health monitoring with automated alerts
- Production readiness validation
- Error rate tracking and threshold alerts
- Atomic CSV operations for data integrity

SUPPORTED BETTING MARKETS:
1. 1X2 (Home/Away/Draw)
2. Double Chance (Home or Draw, Away, etc.)
3. Draw No Bet
4. Both Teams To Score (Yes/No)
5. Over/Under Goals (0.5 - 5.5)
6. Goal Ranges
7. Correct Score
8. Clean Sheet
9. Asian Handicap
10. Combo Bets
11. Team Over/Under

SYSTEM COMPONENTS:

1. Leo.py (Main Controller)
   - Orchestrates workflow
   - Manages browser sessions and local AI connectivity

2. Mind/ (Local AI Core)
   - `setup_linux_env.sh`: Automated installer for Linux/Codespaces
   - `run_split_model.bat` / `.sh`: Auto-launch scripts for the local Qwen2-VL server
   - `llama-server`: Cross-platform uncensored inference engine
   - `model.gguf` & `mmproj.gguf`: Model weights (Brain + Eyes)

3. Neo/ (AI Engine)
   - `visual_analyzer.py`: **[UPDATED]** Uses `localhost:8080` for UI analysis
   - `rule_engine.py`: Core prediction rules
   - `ml_model.py`: Machine learning integration

4. Helpers/ (Utility Systems)
   - `llm_matcher.py`: **[UPDATED]** Local team name resolution
   - `db_helpers.py`: Database operations
   - `health_monitor.py`: System health tracking

5. DB/ (Data Storage)
   - predictions.csv: Core prediction data
   - auth/: Authentication state management

6. Logs/ (Monitoring)
   - Detailed session logs and error reports

MAINTENANCE & MONITORING:
- Ensure `run_split_model.bat` is running before starting `Leo.py`
- Monitor `http://localhost:8080` for model status
- Health check intervals (5-minute cycles)

The system continuously learns and improves through outcome analysis,
adapting prediction weights and ML models based on real-world performance.
"""
