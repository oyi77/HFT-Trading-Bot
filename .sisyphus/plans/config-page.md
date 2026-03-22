# Config Page for HFT Trading Bot

## TL;DR

> **Quick Summary**: Create a dedicated configuration page accessible from both TUI and Web interfaces, allowing users to change trading parameters (provider, mode, pair, leverage, TP/SL, strategy, etc.) with hot-swap support for simple settings and restart for complex ones.
> 
> **Deliverables**:
> - TUI Config Page with Rich-based UI
> - Web Config Page with Flask/HTML templates
> - Hotkey navigation ('C' key)
> - Navigation menu integration
> - Config persistence (JSON file)
> - Mixed apply method (hot-swap + restart)
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Wave 1 → Wave 2 → Wave 3 → Final Verification

---

## Context

### Original Request
User wants a separate configuration page in the HFT Trading Bot to change:
- Provider (exness, ccxt, ostium, simulator)
- Mode (paper, frontest, real)
- Pair/Symbol
- Leverage
- TP & SL
- Strategy
- And additional settings (lot, balance, trailing, break-even, session filters, risk, etc.)

### Interview Summary
**Key Discussions**:
- Interface: TUI + Web
- Access: Both hotkey ('C') and navigation menu
- Settings: Full coverage with all config options
- Persistence: Save to JSON config file
- Apply method: Mixed (hot-swap for simple, restart for complex)

### Research Findings
- **InterfaceConfig** in `base.py` contains all 14 config fields
- **TUI** uses Rich library with Panels, Tables, Live updates
- **Setup Wizard** has existing multi-step config flow (397 lines)
- **9 strategies** available in `strategy/__init__.py`

---

## Work Objectives

### Core Objective
Create a dedicated, accessible configuration page in both TUI and Web interfaces that allows real-time modification of all trading parameters with appropriate persistence and apply mechanisms.

### Concrete Deliverables
- TUI Config Page (Rich-based)
- Web Config Page (Flask/HTML)
- Hotkey handler for 'C' key
- Navigation menu option
- Config file persistence (JSON)
- Apply/Restart logic
- Input validation

### Definition of Done
- [ ] Press 'C' in TUI opens config page
- [ ] All 14+ config fields editable via UI
- [ ] Changes persist to config.json
- [ ] Hot-swap works for: lot, TP, SL, leverage (basic params)
- [ ] Restart required for: mode, provider, strategy, symbol
- [ ] Web interface has equivalent config page
- [ ] Input validation prevents invalid values

### Must Have
- All InterfaceConfig fields editable
- Visual feedback on changes
- Config file save/load
- Error handling for invalid inputs

### Must NOT Have (Guardrails)
- No direct API credential editing (security)
- No changes to exchange connection logic (only config)
- No auto-save without user confirmation
- No hot-swap of strategy-specific params without restart

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.
> Acceptance criteria requiring "user manually tests/confirms" are FORBIDDEN.

### Test Decision
- **Infrastructure exists**: YES (pytest in project)
- **Automated tests**: YES (tests-after)
- **Framework**: pytest
- **TDD**: No - tests after implementation

### QA Policy
Every task MUST include agent-executed QA scenarios.

- **TUI**: Use interactive_bash (tmux) — Run bot, send 'C' key, verify screen opens
- **Web**: Use Playwright — Navigate to config page, edit fields, verify save
- **Config**: Use Bash — Verify JSON file exists and has correct values

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation - can run immediately):
├── Task 1: Extend InterfaceConfig with validation
├── Task 2: Create config persistence module
├── Task 3: Create TUI config page base
└── Task 4: Create Web config route

Wave 2 (Core Implementation - after Wave 1):
├── Task 5: Implement TUI provider/mode/symbol selection
├── Task 6: Implement TUI leverage/TP/SL controls
├── Task 7: Implement TUI strategy selection
├── Task 8: Implement TUI advanced settings
├── Task 9: Implement Web config page HTML
├── Task 10: Add hotkey handler for 'C'
└── Task 11: Add navigation menu option

Wave 3 (Integration - after Wave 2):
├── Task 12: Implement hot-swap logic
├── Task 13: Implement restart logic
├── Task 14: Add config validation
└── Task 15: Integration testing

Critical Path: Task 1-4 → Task 5-11 → Task 12-15
Parallel Speedup: ~40% faster than sequential
Max Concurrent: 4-7 (Wave 2)
```

---

## TODOs

- [x] 1. Extend InterfaceConfig with validation methods

  **What to do**:
  - Add validation methods to InterfaceConfig in `trading_bot/interface/base.py`
  - Add fields: trailing_stop, trail_start, break_even, break_even_offset
  - Add use_auto_lot, risk_percent, max_daily_loss, max_drawdown
  - Add session filters: use_asia_session, use_london_open, use_ny_session
  - Add validation for: leverage (10-5000), lot (0.001-100), pips (0-10000)
  - Add `requires_restart()` method to identify settings needing restart
  
  **Must NOT do**:
  - Don't change existing field names (backward compatibility)
  - Don't add credential fields (security)
  
  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Extends existing config model with validation logic
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - N/A
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Tasks 5-11 (all config page implementations)
  - **Blocked By**: None
  
  **References**:
  - `trading_bot/interface/base.py:12-51` - InterfaceConfig class (existing)
  - `trading_bot/core/models.py:89-122` - Config dataclass (reference pattern)
  
  **Acceptance Criteria**:
  - [ ] InterfaceConfig has all new fields
  - [ ] Validation methods return correct errors for invalid input
  - [ ] requires_restart() correctly identifies restart-requiring settings
  
  **QA Scenarios**:
  ```
  Scenario: Validate leverage bounds
    Tool: Bash
    Steps:
      1. python -c "from trading_bot.interface.base import InterfaceConfig; c = InterfaceConfig(); c.leverage = 5; c.validate()"
      2. Assert error returned: "leverage must be between 10 and 5000"
    Expected Result: ValidationError with correct message
    Evidence: .sisyphus/evidence/task-1-leverage-validation.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 2. Create config persistence module

  **What to do**:
  - Create `trading_bot/interface/config_persistence.py`
  - Add functions: save_config(), load_config(), get_config_path()
  - Implement auto-discover of config file location (home dir, project dir)
  - Add config file versioning for migration support
  - Implement atomic save (write to temp, then rename)
  
  **Must NOT do**:
  - Don't save credentials to file (security)
  - Don't use pickle (security)
  
  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Standard file I/O with JSON
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Task 15 (integration testing)
  - **Blocked By**: None
  
  **References**:
  - `trading_bot/interface/base.py:54-90` - save/load functions (existing pattern)
  
  **Acceptance Criteria**:
  - [ ] save_config() writes valid JSON to config.json
  - [ ] load_config() correctly parses saved JSON
  - [ ] Credentials are never saved to file
  
  **QA Scenarios**:
  ```
  Scenario: Save and load config
    Tool: Bash
    Steps:
      1. python -c "from trading_bot.interface.base import InterfaceConfig; from trading_bot.interface.config_persistence import save_config, load_config; c = InterfaceConfig(mode='paper', lot=0.01); save_config(c, 'test_config.json')"
      2. python -c "from trading_bot.interface.config_persistence import load_config; c = load_config('test_config.json'); print(c.mode, c.lot)"
      3. Assert output: "paper 0.01"
    Expected Result: Config correctly saved and loaded
    Evidence: .sisyphus/evidence/task-2-persistence.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 3. Create TUI config page base

  **What to do**:
  - Create `trading_bot/interface/tui_config.py`
  - Inherit from BaseInterface
  - Create ConfigPage class with render() method
  - Create navigation: enter config, exit config, next/prev field
  - Add keyboard handling for: arrows (navigation), enter (select), esc (back)
  - Add screen sections: Basic Settings, Strategy, Risk Management
  
  **Must NOT do**:
  - Don't implement actual editing yet (Task 5-8)
  - Don't block main thread
  
  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Rich UI components and keyboard handling
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Tasks 5-8 (actual field editing)
  - **Blocked By**: None
  
  **References**:
  - `trading_bot/interface/tui.py:1-100` - Rich usage patterns
  - `trading_bot/interface/setup_wizard.py:1-100` - Step navigation
  
  **Acceptance Criteria**:
  - [ ] ConfigPage renders as Panel
  - [ ] Arrow keys navigate between fields
  - [ ] Enter key selects for editing
  - [ ] Esc returns to main dashboard
  
  **QA Scenarios**:
  ```
  Scenario: Open config page in TUI
    Tool: interactive_bash
    Preconditions: trading_bot.py runs in TUI mode
    Steps:
      1. Send 'C' key to running TUI
      2. Verify config panel appears
      3. Send Escape key
      4. Verify return to dashboard
    Expected Result: Config page opens and closes correctly
    Evidence: .sisyphus/evidence/task-3-tui-config-base.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 4. Create Web config route

  **What to do**:
  - Add routes to `trading_bot/interface/web.py`
  - Add GET /config - returns current config as JSON
  - Add POST /config - accepts JSON config, validates, saves
  - Add GET /config/page - returns HTML config page
  - Add validation endpoint POST /config/validate
  
  **Must NOT do**:
  - Don't expose credentials in GET response
  
  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Flask route additions
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 9 (Web config page HTML)
  - **Blocked By**: None
  
  **References**:
  - `trading_bot/interface/web.py:1-50` - Existing Flask routes
  
  **Acceptance Criteria**:
  - [ ] GET /config returns JSON (without credentials)
  - [ ] POST /config saves valid config
  - [ ] POST /config/validate returns validation result
  
  **QA Scenarios**:
  ```
  Scenario: Web config API
    Tool: Bash
    Preconditions: Web server running on localhost:5000
    Steps:
      1. curl http://localhost:5000/config
      2. Assert JSON returned with mode, symbol, etc
      3. curl -X POST -H "Content-Type: application/json" -d '{"mode":"paper","lot":0.01}' http://localhost:5000/config
      4. Assert success response
    Expected Result: API endpoints work correctly
    Evidence: .sisyphus/evidence/task-4-web-config.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 5. Implement TUI provider/mode/symbol selection

  **What to do**:
  - Add selection UI for Provider: simulator, exness, ccxt, ostium
  - Add selection UI for Mode: paper, frontest, real
  - Add selection UI for Symbol: XAUUSDm, XAUUSD, BTCUSDT, etc.
  - Show current selection with highlight
  - Require restart after change (set requires_restart flag)
  
  **Must NOT do**:
  - Don't validate credentials here (security)
  - Don't attempt connection (Task 12-13)
  
  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Rich-based selection UI
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9, 10, 11)
  - **Blocks**: Tasks 12-13 (apply logic)
  - **Blocked By**: Task 3 (config page base)
  
  **References**:
  - `trading_bot/interface/setup_wizard.py:63-130` - Selection patterns
  - `trading_bot/interface/base.py:12-18` - InterfaceConfig fields
  
  **Acceptance Criteria**:
  - [ ] Provider shows 4 options with current highlighted
  - [ ] Mode shows 3 options with current highlighted
  - [ ] Symbol shows available symbols with current highlighted
  - [ ] Change triggers "restart required" message
  
  **QA Scenarios**:
  ```
  Scenario: Change provider in TUI
    Tool: interactive_bash
    Preconditions: Config page open
    Steps:
      1. Navigate to Provider field
      2. Press Enter to open selection
      3. Navigate to "exness"
      4. Press Enter to select
      5. Verify "Restart required" message appears
    Expected Result: Provider changed, restart message shown
    Evidence: .sisyphus/evidence/task-5-provider-change.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 6. Implement TUI leverage/TP/SL controls

  **What to do**:
  - Add numeric input for Leverage (10-5000)
  - Add numeric input for Stop Loss pips (0-10000)
  - Add numeric input for Take Profit pips (0-10000)
  - Add increment/decrement buttons (arrow keys)
  - Allow direct number entry
  - Hot-swap enabled (no restart needed)
  
  **Must NOT do**:
  - Don't allow values outside valid range
  - Don't block invalid input
  
  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Rich numeric input handling
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 7, 8, 9, 10, 11)
  - **Blocks**: Task 12 (hot-swap logic)
  - **Blocked By**: Task 3
  
  **References**:
  - `trading_bot/interface/tui.py:78-150` - Display patterns
  
  **Acceptance Criteria**:
  - [ ] Leverage input accepts 10-5000
  - [ ] SL/TP input accepts 0-10000
  - [ ] Arrow up/down increments/decrements by step
  - [ ] Invalid input shows error, doesn't save
  
  **QA Scenarios**:
  ```
  Scenario: Change leverage
    Tool: interactive_bash
    Preconditions: Config page open
    Steps:
      1. Navigate to Leverage field
      2. Press Enter to edit
      3. Type "500"
      4. Press Enter to save
      5. Verify "Applied (hot-swap)" message
    Expected Result: Leverage changed without restart
    Evidence: .sisyphus/evidence/task-6-leverage-change.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 7. Implement TUI strategy selection

  **What to do**:
  - Add strategy dropdown with all 9 strategies
  - Show strategy description on selection
  - Require restart after change
  - Show current strategy with highlight
  
  **Must NOT do**:
  - Don't validate strategy parameters here
  - Don't load strategy class (engine handles)
  
  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Rich dropdown UI
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 8, 9, 10, 11)
  - **Blocks**: Task 13 (restart logic)
  - **Blocked By**: Task 3
  
  **References**:
  - `trading_bot/strategy/__init__.py:1-41` - Available strategies
  - `trading_bot/interface/setup_wizard.py:150-200` - Selection pattern
  
  **Acceptance Criteria**:
  - [ ] All 9 strategies shown in dropdown
  - [ ] Strategy description visible on hover/select
  - [ ] Change requires restart
  
  **QA Scenarios**:
  ```
  Scenario: Change strategy
    Tool: interactive_bash
    Preconditions: Config page open
    Steps:
      1. Navigate to Strategy field
      2. Press Enter to open dropdown
      3. Select "GridStrategy"
      4. Verify "Restart required" message
    Expected Result: Strategy changed with restart prompt
    Evidence: .sisyphus/evidence/task-7-strategy-change.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 8. Implement TUI advanced settings

  **What to do**:
  - Add lot size input (0.001-100)
  - Add balance input (for paper mode)
  - Add trailing stop toggle and pips
  - Add break-even toggle and pips
  - Add session filters (Asia, London, NY checkboxes)
  - Add risk % and max drawdown
  - Add auto-lot toggle
  
  **Must NOT do**:
  - Don't save invalid values
  
  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Multiple input types
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7, 9, 10, 11)
  - **Blocks**: Task 12 (hot-swap)
  - **Blocked By**: Task 3
  
  **References**:
  - `trading_bot/core/models.py:97-122` - Config fields
  
  **Acceptance Criteria**:
  - [ ] All advanced fields editable
  - [ ] Session filters are toggleable
  - [ ] Numeric fields validate ranges
  - [ ] Auto-lot toggles correctly
  
  **QA Scenarios**:
  ```
  Scenario: Toggle auto-lot
    Tool: interactive_bash
    Preconditions: Config page open, advanced settings section
    Steps:
      1. Navigate to Auto-Lot toggle
      2. Press Enter to toggle
      3. Verify toggle state changes
      4. Verify "Applied (hot-swap)" message
    Expected Result: Auto-lot toggled successfully
    Evidence: .sisyphus/evidence/task-8-advanced-settings.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 9. Implement Web config page HTML

  **What to do**:
  - Create HTML template for config page
  - Add form sections matching TUI: Basic, Strategy, Risk
  - Add JavaScript for dynamic form handling
  - Add API calls for save/validate
  - Add visual feedback (success/error messages)
  - Style to match web interface theme
  
  **Must NOT do**:
  - Don't hardcode API URLs (use relative paths)
  - Don't expose credentials fields
  
  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: HTML/CSS/JS frontend
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7, 8, 10, 11)
  - **Blocks**: Task 15 (integration testing)
  - **Blocked By**: Task 4
  
  **References**:
  - `trading_bot/interface/web.py` - Existing web structure
  
  **Acceptance Criteria**:
  - [ ] All config fields rendered in form
  - [ ] Form submits to POST /config
  - [ ] Validation errors shown inline
  - [ ] Success message after save
  
  **QA Scenarios**:
  ```
  Scenario: Edit config in Web
    Tool: Playwright
    Preconditions: Web server running
    Steps:
      1. Navigate to /config/page
      2. Fill Leverage field with "500"
      3. Click Save button
      4. Verify success message
    Expected Result: Config saved via web interface
    Evidence: .sisyphus/evidence/task-9-web-config.png
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 10. Add hotkey handler for 'C'

  **What to do**:
  - Add keyboard listener in TUI main loop
  - Map 'C' or 'c' to open config page
  - Handle case when in different screen
  - Show help text "(Press C for Config)"
  
  **Must NOT do**:
  - Don't break existing hotkeys
  - Don't interfere with trading actions
  
  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Keyboard event handling integration
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7, 8, 9, 11)
  - **Blocks**: None
  - **Blocked By**: Task 3
  
  **References**:
  - `trading_bot/interface/tui.py:200-250` - Input handling
  
  **Acceptance Criteria**:
  - [ ] Press 'C' opens config from dashboard
  - [ ] Works regardless of current screen
  - [ ] Help text visible on dashboard
  
  **QA Scenarios**:
  ```
  Scenario: Hotkey opens config
    Tool: interactive_bash
    Preconditions: TUI running on dashboard
    Steps:
      1. Send 'c' key
      2. Verify config page opens
    Expected Result: Hotkey triggers config page
    Evidence: .sisyphus/evidence/task-10-hotkey.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 11. Add navigation menu option

  **What to do**:
  - Add "Config" option to main navigation menu
  - Position in menu: between "Dashboard" and "Positions"
  - Show keyboard shortcut "(C)"
  - Handle menu selection
  
  **Must NOT do**:
  - Don't duplicate existing menu items
  - Don't break existing navigation
  
  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Menu UI integration
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7, 8, 9, 10)
  - **Blocks**: None
  - **Blocked By**: Task 3
  
  **References**:
  - `trading_bot/interface/tui.py:250-300` - Menu handling
  
  **Acceptance Criteria**:
  - [ ] Config visible in menu
  - [ ] Selecting Config opens config page
  - [ ] Keyboard shortcut shown
  
  **QA Scenarios**:
  ```
  Scenario: Menu navigation to config
    Tool: interactive_bash
    Preconditions: TUI on dashboard
    Steps:
      1. Navigate menu to "Config"
      2. Press Enter
      3. Verify config page opens
    Expected Result: Menu navigation works
    Evidence: .sisyphus/evidence/task-11-menu.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 12. Implement hot-swap logic

  **What to do**:
  - Identify settings that can be hot-swapped: lot, leverage, SL, TP, trailing, break-even, session filters
  - Create apply_config() method that updates running bot
  - Handle callback to trading engine for live updates
  - Show success/error feedback in UI
  
  **Must NOT do**:
  - Don't hot-swap provider/mode/strategy/symbol (require restart)
  - Don't cause race conditions with trading
  
  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Runtime config application logic
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 13, 14, 15)
  - **Blocks**: None
  - **Blocked By**: Tasks 5, 6, 8
  
  **References**:
  - `trading_bot/bot.py` - Bot configuration handling
  - `trading_bot/interface/base.py:147` - on_config_update_callback
  
  **Acceptance Criteria**:
  - [ ] Hot-swap applies changes without restart
  - [ ] Changes take effect immediately
  - [ ] Error handling for failed hot-swap
  
  **QA Scenarios**:
  ```
  Scenario: Hot-swap leverage
    Tool: interactive_bash
    Preconditions: Bot running in paper mode
    Steps:
      1. Open config page
      2. Change leverage to 500
      3. Save config
      4. Verify "Applied" message
      5. Check bot is still running with new leverage
    Expected Result: Hot-swap works without restart
    Evidence: .sisyphus/evidence/task-12-hotswap.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 13. Implement restart logic

  **What to do**:
  - Identify settings requiring restart: provider, mode, symbol, strategy
  - Show "Restart Required" dialog when these change
  - Implement graceful shutdown sequence
  - Auto-restart with new config
  
  **Must NOT do**:
  - Don't force close positions without confirmation
  - Don't lose trading state unexpectedly
  
  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Graceful shutdown and restart logic
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 12, 14, 15)
  - **Blocks**: None
  - **Blocked By**: Tasks 5, 7
  
  **References**:
  - `trading_bot/bot.py` - Bot lifecycle
  - `trading_bot/interface/tui.py:300-362` - Shutdown handling
  
  **Acceptance Criteria**:
  - [ ] Restart prompt shown for restart-requiring changes
  - [ ] Graceful shutdown closes positions safely
  - [ ] Bot restarts with new configuration
  
  **QA Scenarios**:
  ```
  Scenario: Restart for strategy change
    Tool: interactive_bash
    Preconditions: Bot running
    Steps:
      1. Change strategy to GridStrategy
      2. Save config
      3. Verify "Restart Required" dialog
      4. Confirm restart
      5. Verify bot restarts with new strategy
    Expected Result: Graceful restart with new strategy
    Evidence: .sisyphus/evidence/task-13-restart.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 14. Add config validation

  **What to do**:
  - Add comprehensive validation for all config fields
  - Return detailed error messages
  - Block save of invalid config
  - Validate dependencies (e.g., TP > SL, leverage vs balance)
  
  **Must NOT do**:
  - Don't allow impossible configurations
  - Don't save partial invalid config
  
  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Validation logic
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 12, 13, 15)
  - **Blocks**: None
  - **Blocked By**: Task 1
  
  **References**:
  - `trading_bot/interface/base.py:92-131` - validate_safety function
  
  **Acceptance Criteria**:
  - [ ] All invalid values rejected with error message
  - [ ] Dependencies validated (TP > SL, etc)
  - [ ] Validation runs before save
  
  **QA Scenarios**:
  ```
  Scenario: Validate invalid config
    Tool: Bash
    Steps:
      1. python -c "from trading_bot.interface.base import InterfaceConfig; c = InterfaceConfig(); c.leverage = 5; c.validate()"
      2. Assert validation error returned
    Expected Result: Invalid leverage rejected
    Evidence: .sisyphus/evidence/task-14-validation.txt
  ```
  
  **Commit**: NO (group with Task 4)

- [x] 15. Integration testing

  **What to do**:
  - Test TUI config page end-to-end
  - Test Web config page end-to-end
  - Test config persistence across restarts
  - Test hot-swap and restart flows
  - Test error handling
  
  **Must NOT do**:
  - Don't test in production mode (use paper)
  
  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration testing
  - **Skills**: []
  
  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 12, 13, 14)
  - **Blocks**: F1-F4 (Final Verification)
  - **Blocked By**: All previous tasks
  
  **References**:
  - `tests/test_config.py` - Existing config tests
  
  **Acceptance Criteria**:
  - [ ] All integration tests pass
  - [ ] TUI flow works end-to-end
  - [ ] Web flow works end-to-end
  - [ ] No regressions in existing tests
  
  **QA Scenarios**:
  ```
  Scenario: Full config flow
    Tool: interactive_bash
    Preconditions: Clean test environment
    Steps:
      1. Start TUI in paper mode
      2. Press 'C' to open config
      3. Change leverage to 1000
      4. Save and verify hot-swap
      5. Exit and restart
      6. Verify config persisted
    Expected Result: Full flow works correctly
    Evidence: .sisyphus/evidence/task-15-integration.txt
  ```
  
  **Commit**: NO (group with Task 4)

---

## Final Verification Wave (MANDATORY)

> 4 review agents run in PARALLEL. ALL must APPROVE.

- [ ] F1. **Plan Compliance Audit** — `oracle`
- [ ] F2. **Code Quality Review** — `unspecified-high`
- [ ] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` for Web)
- [ ] F4. **Scope Fidelity Check** — `deep`

---

## Commit Strategy

- **1**: `feat(config-page): add InterfaceConfig extensions and validation`
- **2**: `feat(config-page): add config persistence module`
- **3**: `feat(config-page): add TUI config page`
- **4**: `feat(config-page): add Web config page`
- **5**: `feat(config-page): add hotkey and navigation integration`
- **6**: `feat(config-page): add hot-swap and restart logic`
- **7**: `test(config-page): add integration tests`

---

## Success Criteria

### Verification Commands
```bash
# TUI Test - Verify config page opens
echo "C" | python trading_bot.py -i tui --mode paper

# Web Test - Verify config endpoint
curl http://localhost:5000/config

# Config persistence test
python -c "from trading_bot.interface.base import load_config_from_file; print(load_config_from_file('config.json'))"
```

### Final Checklist
- [ ] All Must Have present
- [ ] All Must NOT Have absent
- [ ] All tests pass
