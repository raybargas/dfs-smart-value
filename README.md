# DFS Lineup Optimizer

A Streamlit-based web application for optimizing Daily Fantasy Sports (DFS) lineups with contextual intelligence.

## Features

### Core Features
- **Data Ingestion**: Upload player data via CSV or Excel files
- **Smart Column Detection**: Automatically detects column name variations
- **Data Validation**: Comprehensive validation with quality scoring
- **Interactive UI**: Filter and search players with an intuitive interface

### Phase 2C: Narrative Intelligence & Smart Pool Selection (NEW! 🚀)
- **Vegas Lines Integration**: Real-time NFL odds and Implied Team Totals (ITT) from The Odds API
- **Injury Reports**: Live injury status from MySportsFeeds API (Q/D/O/IR with practice status)
- **Smart Rules Engine**: Position-specific evaluation rules for QBs, RBs, WRs, TEs, and DST
- **Narrative Flags**: Automated red/yellow/green flags based on business rules (ITT thresholds, salary/ceiling ratios, snap counts, etc.)
- **Player Context Builder**: Enriches player data with ITT, injury status, and narrative flags
- **Enhanced Player Selection**: 6 new columns in player table (ITT, Injury, Score, Red/Yellow/Green flag counts)
- **Smart Filtering**: Filter players by narrative score (optimal/caution/avoid)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) Set up API keys for Narrative Intelligence features:
   - Create a `.env` file in the DFS directory
   - Add your API keys:
```bash
THE_ODDS_API_KEY=your_odds_api_key_here
MYSPORTSFEEDS_API_KEY=your_mysportsfeeds_key_here
```
   - See `API_SETUP.md` for detailed instructions on obtaining API keys

## Usage

### Basic Workflow
1. Start the Streamlit app:
```bash
streamlit run app.py
```

2. Open your browser to `http://localhost:8501`

3. Upload your player data file (CSV or Excel)

4. Review the data summary and quality metrics

5. **(Optional) Visit Narrative Intelligence tab**:
   - View Vegas lines and Implied Team Totals
   - Review injury reports with color-coded statuses
   - Rate limiting: 15-minute cooldown between API calls
   - Data caching: Load previously fetched data without API calls

6. **Select Players**:
   - Enhanced table shows ITT, injury status, and narrative flags
   - Filter by player score (red/yellow/green)
   - Expand "View Detailed Narrative Flags" for deep analysis
   - Lock must-have players, exclude fades

7. Proceed to lineup optimization

## Data Format

### Required Columns
- **Name** (Player, Player Name)
- **Position** (Pos) - Valid: QB, RB, WR, TE, DST
- **Salary** (Cost, Price) - Range: $3,000 - $10,000
- **Projection** (Proj, FPPG, Points) - Must be positive

### Optional Columns
- **Team** - Team abbreviation
- **Opponent** (Opp) - Opponent abbreviation
- **Ownership** (Own%) - Projected ownership (0-100%)
- **Player ID** - Unique identifier

## Project Structure

```
DFS/
├── app.py                         # Main Streamlit application
├── src/                           # Backend modules
│   ├── __init__.py
│   ├── parser.py                  # File parsing and column detection
│   ├── validator.py               # Data validation and quality checks
│   ├── models.py                  # Core data models (Player, Lineup)
│   ├── extended_models.py         # Extended models (PlayerProjection, GameScenario, etc.)
│   ├── optimizer.py               # Lineup optimization engine (PuLP)
│   ├── simulation.py              # Monte Carlo simulation engine
│   ├── database_models.py         # Phase 2C: SQLAlchemy ORM models
│   ├── player_context_builder.py  # Phase 2C: Player data enrichment service
│   ├── rules_engine.py            # Phase 2C: Smart rules evaluation engine
│   └── api/                       # Phase 2C: External API integrations
│       ├── __init__.py
│       ├── base_client.py         # Base API client (retry, caching, logging)
│       ├── odds_api.py            # The Odds API client (Vegas lines)
│       └── mysportsfeeds_api.py   # MySportsFeeds API client (injuries)
├── ui/                            # UI components
│   ├── __init__.py
│   ├── data_ingestion.py          # Data upload and display UI
│   ├── narrative_intelligence.py  # Phase 2C: Narrative Intelligence tab
│   ├── player_selection.py        # Enhanced player selection with flags
│   ├── optimization_config.py     # Optimization settings
│   ├── lineup_generation.py       # Lineup generation UI
│   └── results.py                 # Results display and export
├── migrations/                    # Database migrations
│   ├── 001_add_phase2_tables.sql
│   ├── 002_add_narrative_intelligence_tables.sql
│   └── run_migrations.py
├── tests/                         # Comprehensive test suite (237 tests, 87% coverage)
│   ├── test_database_models.py    # Phase 2C: Database model tests
│   ├── test_api_clients.py        # Phase 2C: API client tests
│   ├── test_rules_engine.py       # Phase 2C: Rules engine tests
│   ├── test_player_context_builder.py  # Phase 2C: Context builder tests
│   ├── test_models.py
│   ├── test_extended_models.py
│   ├── test_optimizer.py
│   ├── test_simulation.py
│   ├── test_parser.py
│   ├── test_validator.py
│   └── ...
├── requirements.txt               # Python dependencies
├── API_SETUP.md                   # Phase 2C: API key setup guide
├── .env.example                   # Environment variable template
└── README.md                      # This file
```

## Development

### Running Tests
```bash
pytest tests/ -v
```

### Code Coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

## Version

Current version: 2.3.0 (Phase 2C: Narrative Intelligence & Smart Pool Selection Complete)

### Version History
- **2.3.0** - Phase 2C: Narrative Intelligence (Vegas lines, injury reports, smart rules engine, narrative flags)
- **2.2.0** - Phase 2B: Contextual Intelligence  (game scenarios, advanced simulations)
- **2.1.0** - Phase 2A: Advanced Differentiation (player projections, correlation matrices, partial implementation)
- **1.0.0** - Phase 1: MVP (data ingestion, player selection, basic optimization)

## Phase 2C: Narrative Intelligence Deep Dive

### What is Narrative Intelligence?

Phase 2C introduces contextual intelligence to your DFS lineup building by integrating real-time Vegas lines, injury reports, and smart business rules. Instead of relying solely on projections, you now have access to **narrative flags** that highlight optimal plays, caution zones, and avoid situations based on proven DFS strategies.

### Key Components

#### 1. Vegas Lines & Implied Team Totals (ITT)
- **Source**: The Odds API (500 free requests/month)
- **Data**: Home/away spreads, game totals, calculated ITT for each team
- **Formula**: `ITT = (total / 2) + (spread / 2)` for the favorite
- **Use Case**: QBs in high-ITT games (24+) are prioritized; low-ITT DSTs facing weak offenses get green flags

#### 2. Injury Reports
- **Source**: MySportsFeeds API
- **Data**: Player injury status (Q/D/O/IR), body part, practice status (Full/Limited/DNP)
- **Use Case**: Questionable (Q) players get yellow flags; Out/IR players are automatically excluded from optimal consideration

#### 3. Smart Rules Engine
Position-specific evaluation rules based on DFS best practices:

**QB Rules:**
- Low ITT (<20) → Red flag (low scoring environment)
- High ITT (24+) → Green flag (high scoring potential)
- Salary vs ceiling mismatch → Yellow/red flag

**RB Rules:**
- Low attempts (<15 expected) → Red flag (low volume)
- Salary vs ceiling analysis → Value plays highlighted
- Goal-line work indicators → Green flags

**WR Rules:**
- 80/20 Rule: Prior week regression (20% targets) → Yellow flag
- Low snap/route counts → Red flag (limited involvement)
- Leverage plays (low ownership, high ceiling) → Green flag
- Value plays (<$4k with upside) → Green flag

**TE Rules:**
- Blocking TEs (<40 routes) → Red flag
- Low salary TEs (<$3k) → Red flag (limited role)
- Value plays with ITT boost → Green flag

**DST Rules:**
- Weak O-line matchups → Green flag
- Strong O-line matchups → Yellow flag

#### 4. Player Context Builder
Automatically enriches your uploaded player data with:
- ITT for each player's team
- Opponent ITT
- Injury status and details
- Prior week points (if available)
- Narrative flags (red/yellow/green)
- Overall player score (avoid/caution/optimal)

#### 5. Enhanced Player Selection Table
Six new columns added:
1. **ITT** - Implied Team Total (green text, sortable)
2. **🏥** - Injury status badge (Q/D/O/IR)
3. **Score** - Red/Yellow/Green player score
4. **🔴** - Count of red flags (avoid indicators)
5. **🟡** - Count of yellow flags (caution indicators)
6. **🟢** - Count of green flags (optimal indicators)

#### 6. Narrative Flags Panel
Expandable "View Detailed Narrative Flags" section provides:
- Grouped by score category (Red → Yellow → Green)
- Player-by-player breakdown
- Specific flag messages (e.g., "QB in low-scoring game (ITT: 18.5)", "WR value play under $4k")
- Color-coded for quick scanning

### Data Flow

```
1. Upload CSV → 2. (Optional) Narrative Intelligence Tab → 3. Player Selection
                     - Fetch Vegas lines                    - Auto-enrichment
                     - Fetch injury reports                 - View flags
                     - Cache in database                    - Filter by score
                                                            - Lock/exclude players
```

### Performance & Caching

- **Rate Limiting**: 15-minute cooldown between API calls to protect your monthly quota
- **Caching**: All fetched data stored in SQLite database (`dfs_lineup_optimizer.db`)
- **Load Cached Data**: No API calls needed for repeat visits (instant load)
- **Session Persistence**: Enriched data cached in session state (fast page switches)

### Testing

Phase 2C includes 87 comprehensive tests:
- 38 database model tests
- 14 API client tests (with mocks)
- 18 rules engine tests (position-specific)
- 17 player context builder tests
- **87% code coverage** (1,319 statements, 219 tests passing)

### Future Enhancements (Phase 2D)

Coming soon:
- Weather volatility analysis
- News & sentiment tracking
- Team pace & playcalling tendencies
- DVOA matchup angles
- Milestone watch
- AI-derived storylines

## License

Proprietary - All rights reserved

## Player Selection Controls

After uploading and validating your player data, proceed to the Player Selection page to apply strategic constraints.

### Usage
1. **Filters (Sidebar):** Narrow the table with name search, position/team multiselect, or salary slider. Updates live.
2. **Table Interactions:**
   - **Selection Column:** Dropdown per row (Normal/Lock/Exclude). Locked = green (must include), Exclude = red (avoid).
   - **Select Column:** Checkbox for bulk actions.
3. **Bulk Actions:** Check rows → "Lock All Selected" (forces inclusion), "Exclude All Selected" (filters out), or "Clear All" (reset).
4. **Counts:** Live metrics for Total/Locked/Excluded.
5. **Validation:** 
   - Yellow warning if locked salary > $50k (proceed but limited options).
   - Red error if exclusions leave no players for a position (e.g., 0 QBs)—adjust before optimizing.
6. **Continue:** Exports available/locked players to optimization.

### Tips
- Lock studs (high projection/value); exclude fades (low ownership/upside).
- Persistence: Selections save in session—regenerate configs without re-selecting.
- Edge Cases: Rapid changes auto-update; 500+ players filter <1s.

**Troubleshooting:**
- No data? Back to upload.
- Warnings? Review locks/excludes; non-blocking but impacts lineups.
- For custom data, ensure unique names/IDs to avoid key conflicts.

## Future Components
- Optimization Configuration (sliders for lineups/uniqueness).
- Generation Engine (PuLP-based).
- Results & Export (DK CSV).

