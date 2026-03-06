"""
Trading Bot Interface Module
Provides multiple user interfaces: CLI, TUI, Web
"""

from trading_bot.interface.base import InterfaceConfig
from trading_bot.interface.cli import CLIInterface
from trading_bot.interface.tui import TUIInterface

try:
    from trading_bot.interface.web import WebInterface
except ImportError:
    WebInterface = None

__all__ = ['InterfaceConfig', 'CLIInterface', 'TUIInterface', 'WebInterface', 'get_interface']


def get_interface(interface_type: str = 'cli', **kwargs):
    """
    Factory function to get the appropriate interface
    
    Args:
        interface_type: 'cli', 'tui', or 'web'
        **kwargs: Configuration options
    
    Returns:
        Interface instance
    """
    interfaces = {
        'cli': CLIInterface,
        'tui': TUIInterface,
    }
    
    if WebInterface:
        interfaces['web'] = WebInterface
    
    interface_class = interfaces.get(interface_type.lower())
    if not interface_class:
        raise ValueError(f"Unknown interface type: {interface_type}. Choose from: {list(interfaces.keys())}")
    
    return interface_class(**kwargs)
