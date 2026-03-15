# Interface Module

User interface implementations (CLI, TUI, Web).

## Structure

```
trading_bot/interface/
├── base.py              # BaseInterface ABC
├── cli.py              # Command-line interface
├── tui.py              # Terminal UI with Rich (325 lines)
├── web.py              # Web interface (optional)
├── setup_wizard.py     # Interactive configuration (367 lines)
└── __init__.py         # Factory function
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Add UI | `base.py` → new file | Inherit from `BaseInterface` |
| CLI args | `cli.py` | argparse implementation |
| Interactive UI | `tui.py` | Rich tables, progress bars |
| Config wizard | `setup_wizard.py` | Step-by-step setup |

## Interface Factory

```python
from trading_bot.interface import get_interface

interface = get_interface('tui')  # or 'cli', 'web'
interface.run()
```

## BaseInterface Contract

```python
class BaseInterface(ABC):
    @abstractmethod
    def run(self): pass
    
    @abstractmethod
    def stop(self): pass
    
    @abstractmethod
    def log(self, message: str, level: str = 'info'): pass
    
    @abstractmethod
    def update_metrics(self, metrics: dict): pass
```

## Conventions

- **Rich Library**: TUI uses `rich` for tables/progress
- **Live Updates**: Use `Live` context manager for real-time displays
- **Thread Safety**: UI updates from trading engine must be thread-safe
- **Graceful Exit**: Handle Ctrl+C (SIGINT) for clean shutdown

## Anti-Patterns

- **Don't** block main thread in UI (use async/threading)
- **Don't** call exchange methods directly from UI
- **Never** use `input()` in TUI mode (breaks display)
- **Don't** ignore exceptions in UI callbacks

## Large Files

- `setup_wizard.py` (367 lines): Multi-step configuration flow
- `tui.py` (325 lines): Rich terminal UI with live metrics

## Entry Points

```bash
python main.py -i tui    # TUI mode (default)
python main.py -i cli    # CLI mode
```
