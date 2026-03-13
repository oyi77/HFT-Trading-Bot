import json
import os
import signal
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from trading_bot.interface.base import BaseInterface, InterfaceConfig
from trading_bot.interface.config_persistence import (
    save_config,
    load_config,
    get_config_path,
)
from trading_bot.core.backtest_runner import run_strategy_comparison


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Bot Dashboard</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        
        :root {
            --bg-color: #0f172a;
            --panel-bg: rgba(30, 41, 59, 0.7);
            --panel-border: rgba(255, 255, 255, 0.1);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-color: #38bdf8;
            --success-color: #10b981;
            --danger-color: #ef4444;
            --warning-color: #f59e0b;
        }

        body {
            margin: 0;
            padding: 20px;
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: var(--text-primary);
            min-height: 100vh;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            border-bottom: 1px solid var(--panel-border);
            padding-bottom: 15px;
        }

        h1 {
            font-size: 24px;
            font-weight: 700;
            margin: 0;
            background: linear-gradient(to right, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            color: transparent;
        }

        .status-badge {
            background: rgba(16, 185, 129, 0.2);
            color: var(--success-color);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            border: 1px solid rgba(16, 185, 129, 0.3);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .status-badge.running::before {
            content: '';
            width: 8px;
            height: 8px;
            background: var(--success-color);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--success-color);
            animation: pulse 2s infinite;
        }
        
        .control-panel {
            display: flex;
            gap: 12px;
        }
        
        .btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--panel-border);
            color: var(--text-primary);
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s ease;
            font-family: inherit;
        }
        
        .btn:hover:not(:disabled) {
            background: rgba(255, 255, 255, 0.1);
            transform: translateY(-1px);
        }
        
        .btn:active:not(:disabled) {
            transform: translateY(0);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .btn-success {
            background: rgba(16, 185, 129, 0.15);
            border-color: rgba(16, 185, 129, 0.3);
            color: var(--success-color);
        }
        
        .btn-success:hover:not(:disabled) {
            background: rgba(16, 185, 129, 0.25);
        }
        
        .btn-warning {
            background: rgba(245, 158, 11, 0.15);
            border-color: rgba(245, 158, 11, 0.3);
            color: var(--warning-color);
        }
        
        .btn-warning:hover:not(:disabled) {
            background: rgba(245, 158, 11, 0.25);
        }

        .btn-danger {
            background: rgba(239, 68, 68, 0.15);
            border-color: rgba(239, 68, 68, 0.3);
            color: var(--danger-color);
        }
        
        .btn-danger:hover:not(:disabled) {
            background: rgba(239, 68, 68, 0.25);
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .glass-panel {
            background: var(--panel-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--panel-border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            margin-bottom: 24px;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .glass-panel:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.3);
        }

        .grid-3 {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 24px;
            margin-bottom: 24px;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }

        .metric-card {
            background: rgba(15, 23, 42, 0.5);
            border-radius: 12px;
            padding: 16px;
            border: 1px solid var(--panel-border);
        }

        .metric-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }

        .metric-value {
            font-size: 24px;
            font-weight: 700;
        }
        
        .metric-value.positive { color: var(--success-color); }
        .metric-value.negative { color: var(--danger-color); }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th {
            color: var(--text-secondary);
            font-size: 12px;
            text-transform: uppercase;
            padding: 12px 16px;
            border-bottom: 1px solid var(--panel-border);
        }

        td {
            padding: 16px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 14px;
        }

        tr:last-child td {
            border-bottom: none;
        }

        .side-buy { color: var(--success-color); font-weight: 600; }
        .side-sell { color: var(--danger-color); font-weight: 600; }
        
        .action-btn {
            background: rgba(239, 68, 68, 0.2);
            color: var(--danger-color);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .action-btn:hover {
            background: rgba(239, 68, 68, 0.4);
        }
        
        .provider-badge {
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .tabs {
            display: flex;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            margin-bottom: 20px;
        }

        .tab-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            padding: 10px 20px;
            font-size: 14px;
            cursor: pointer;
            font-weight: 600;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .tab-btn.active {
            color: var(--accent-color);
            border-bottom-color: var(--accent-color);
        }

        .tab-btn:hover {
            color: #fff;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        .logs-container {
            max-height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', Courier, monospace;
            font-size: 13px;
        }
        
        .logs-container::-webkit-scrollbar {
            width: 8px;
        }
        .logs-container::-webkit-scrollbar-track {
            background: rgba(0,0,0,0.1);
        }
        .logs-container::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.2);
            border-radius: 4px;
        }

        .log-entry {
            padding: 6px 0;
            border-bottom: 1px solid rgba(255,255,255,0.02);
            display: flex;
            gap: 12px;
        }
        
        .log-time { color: var(--text-secondary); min-width: 70px; }
        .log-info { color: var(--text-primary); }
        .log-warn { color: var(--warning-color); }
        .log-error { color: var(--danger-color); }
        .log-trade { color: var(--accent-color); }
        .log-profit { color: var(--success-color); }
        .log-loss { color: var(--danger-color); }

    </style>
</head>
<body>
    <div class="container">
        <header>
            <div style="display: flex; align-items: center; gap: 20px;">
                <h1>Trading Bot Dashboard</h1>
                <div class="status-badge running" id="bot-status">Running</div>
            </div>
            <div class="control-panel">
                <button class="btn btn-success" id="btn-start" onclick="sendCommand('start')">▶ Start</button>
                <button class="btn btn-warning" id="btn-pause" onclick="sendCommand('pause')">⏸ Pause</button>
                <button class="btn" id="btn-stop" onclick="sendCommand('stop')">⏹ Stop</button>
                <button class="btn btn-danger" id="btn-close-all" onclick="sendCommand('close_all')">⚠️ Close All Positions</button>
            </div>
        </header>

        <div class="grid-3">
            <div class="glass-panel">
                <h3 style="margin-top:0; color: var(--text-secondary);">Account Summary</h3>
                <div class="metrics-grid" style="grid-template-columns: repeat(4, 1fr);">
                    <div class="metric-card">
                        <div class="metric-label">Balance</div>
                        <div class="metric-value" id="val-balance">$0.00</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Equity</div>
                        <div class="metric-value" id="val-equity">$0.00</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Total Trades</div>
                        <div class="metric-value" id="val-trades">0</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Open Positions</div>
                        <div class="metric-value" id="val-open-positions">0</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Realized P&L</div>
                        <div class="metric-value" id="val-pnl">$0.00</div>
                    </div>
                    <div class="metric-card" style="grid-column: span 2;">
                        <div class="metric-label">Unrealized P&L</div>
                        <div class="metric-value" id="val-unrealized-pnl">$0.00</div>
                    </div>
                </div>
            </div>

            <div class="glass-panel">
                <h3 style="margin-top:0; color: var(--text-secondary);">Risk Management</h3>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-label"><span id="val-price-symbol">Market</span> Price</div>
                        <div class="metric-value" id="val-price" style="font-family: monospace;">$0.00</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Margin Used</div>
                        <div class="metric-value" id="val-margin" style="color: var(--warning-color);">$0.00</div>
                    </div>
                    <div class="metric-card" style="grid-column: span 2;">
                        <div class="metric-label">Free Margin</div>
                        <div class="metric-value" id="val-freemargin" style="color: var(--accent-color);">$0.00</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="glass-panel">
            <div class="tabs">
                <button class="tab-btn active" onclick="showTab('tab-positions', this)">Open Positions (<span id="pos-count">0</span>)</button>
                <button class="tab-btn" onclick="showTab('tab-orders', this)">Pending Orders (<span id="orders-count">0</span>)</button>
                <button class="tab-btn" onclick="showTab('tab-history', this)">Trade History (<span id="history-count">0</span>)</button>
                <button class="tab-btn" onclick="showTab('tab-config', this)">⚙️ Settings</button>
                <button class="tab-btn" onclick="showTab('tab-backtest', this)">📊 Backtest</button>
                <button class="tab-btn" onclick="showTab('tab-markets', this)">📈 Markets</button>
            </div>
            
            <div id="tab-positions" class="tab-content active">
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Provider</th>
                                <th>ID</th>
                                <th>Side</th>
                                <th>Volume</th>
                                <th>Entry Price</th>
                                <th>Current P&L</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody id="positions-body">
                            <tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">No active positions</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div id="tab-orders" class="tab-content">
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Provider</th>
                                <th>ID</th>
                                <th>Side</th>
                                <th>Volume</th>
                                <th>Price Target</th>
                                <th>Type</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody id="orders-body">
                            <tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">No pending orders</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div id="tab-history" class="tab-content">
                <div style="overflow-x: auto; max-height: 250px;">
                    <table>
                        <thead>
                            <tr>
                                <th>Provider</th>
                                <th>ID</th>
                                <th>Side</th>
                                <th>Volume</th>
                                <th>Close Price</th>
                                <th>Net Final</th>
                            </tr>
                        </thead>
                        <tbody id="history-body">
                            <tr><td colspan="6" style="text-align: center; color: var(--text-secondary);">No historical trades yet</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div id="tab-config" class="tab-content">
                <div style="background: rgba(15, 23, 42, 0.4); border-radius: 8px; padding: 20px; border: 1px solid var(--panel-border);">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 20px;">
                        <div>
                            <h4 style="margin-top: 0; color: var(--accent-color);">Live Strategy Parameters</h4>
                        </div>
                        <button class="btn btn-warning" onclick="restartBot()">🔄 Restart Bot</button>
                    </div>

                    <h4 style="margin-top: 0; color: var(--accent-color);">Core Settings (Requires Restart)</h4>
                    <p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 20px;">Changing these parameters will automatically restart the bot.</p>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 24px;">
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Pair (Symbol)</label>
                            <input list="pairs" id="conf_symbol" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;" />
                            <datalist id="pairs">
                                <option value="XAUUSDm"></option>
                                <option value="BTCUSDT"></option>
                                <option value="BTCUSD"></option>
                                <option value="ETHUSDT"></option>
                                <option value="EURUSD"></option>
                            </datalist>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Provider(s) (Cmd/Ctrl+Click to multi-select)</label>
                            <select id="conf_provider" multiple size="4" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="simulator">Simulator (Paper)</option>
                                <option value="exness">Exness</option>
                                <option value="ccxt">CCXT (Binance/Bybit)</option>
                                <option value="ostium">Ostium DEX</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Timeframe</label>
                            <select id="conf_tf" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="1m">1m</option>
                                <option value="5m">5m</option>
                                <option value="15m">15m</option>
                                <option value="30m">30m</option>
                                <option value="1h">1h</option>
                                <option value="4h">4h</option>
                                <option value="1d">1d</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Mode</label>
                            <select id="conf_mode" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="paper">Paper (Simulated)</option>
                                <option value="frontest">Front Test</option>
                                <option value="real">Real</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Strategy</label>
                            <select id="conf_strategy" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="xau_hedging">XAU Hedging</option>
                                <option value="grid">Grid (Mean Reversion)</option>
                                <option value="trend">Trend (EMA Crossover)</option>
                                <option value="hft">HFT (Orderbook + Vol)</option>
                            </select>
                        </div>
                    </div>
                    
                    <h4 style="margin-top: 0; color: var(--accent-color);">Live Strategy Adjustments</h4>
                    <p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 20px;">Changes apply immediately without restart.</p>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 24px;">
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Lot Size</label>
                            <input type="number" id="conf_lot" step="0.01" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;" />
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Leverage (x)</label>
                            <input type="number" id="conf_lev" step="1" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;" />
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Stop Loss (Pips)</label>
                            <input type="number" id="conf_sl" step="1" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;" />
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Take Profit (Pips)</label>
                            <input type="number" id="conf_tp" step="1" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;" />
                        </div>
                    </div>

                    <h4 style="margin-top: 0; color: var(--accent-color);">Advanced Settings</h4>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 24px;">
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Trailing Stop</label>
                            <select id="conf_ts" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="false">Disabled</option>
                                <option value="true">Enabled</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Trail Start (Pips)</label>
                            <input type="number" id="conf_ts_start" step="1" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;" />
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Break Even</label>
                            <select id="conf_be" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="false">Disabled</option>
                                <option value="true">Enabled</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Break Even Offset (Pips)</label>
                            <input type="number" id="conf_be_offset" step="1" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;" />
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Auto Lot</label>
                            <select id="conf_autolot" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="false">Disabled</option>
                                <option value="true">Enabled</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Risk Percent (%)</label>
                            <input type="number" id="conf_risk" step="0.1" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;" />
                        </div>
                    </div>

                    <h4 style="margin-top: 0; color: var(--accent-color);">Risk & Sessions</h4>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 24px;">
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Max Daily Loss ($)</label>
                            <input type="number" id="conf_maxloss" step="1" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;" />
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Max Drawdown (%)</label>
                            <input type="number" id="conf_maxdd" step="1" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;" />
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Asia Session Filter</label>
                            <select id="conf_asia" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="true">Enabled</option>
                                <option value="false">Disabled</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">London Open Filter</label>
                            <select id="conf_london" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="true">Enabled</option>
                                <option value="false">Disabled</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">NY Session Filter</label>
                            <select id="conf_ny" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="true">Enabled</option>
                                <option value="false">Disabled</option>
                            </select>
                        </div>
                    </div>

                    <button class="btn btn-success" style="width: 100%; padding: 12px;" onclick="updateBotConfig()">Apply Configuration Variables</button>
                </div>
            </div>

            <div id="tab-backtest" class="tab-content">
                <div style="background: rgba(15, 23, 42, 0.4); border-radius: 8px; padding: 20px; border: 1px solid var(--panel-border);">
                    <h4 style="margin-top: 0; color: var(--accent-color);">📊 Run Strategy Comparison</h4>
                    <p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 20px;">Compare multiple strategies across different providers. This may take several minutes depending on data volume.</p>
                    
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 24px;">
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Strategy</label>
                            <select id="bt_strategy" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="all">All Strategies</option>
                                <option value="HFT">HFT</option>
                                <option value="Trend">Trend</option>
                                <option value="Grid">Grid</option>
                                <option value="XAU_Hedging">XAU Hedging</option>
                            </select>
                        </div>
                        <div>
                            <label style="display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 5px;">Provider</label>
                            <select id="bt_provider" style="width: 100%; padding: 8px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid var(--panel-border); color: white;">
                                <option value="all">All Providers</option>
                                <option value="simulator">Simulator (Paper)</option>
                                <option value="ostium">Ostium DEX</option>
                                <option value="exness">Exness</option>
                                <option value="ccxt">CCXT (Binance/Bybit)</option>
                            </select>
                        </div>
                    </div>
                    
                    <button id="bt_run_btn" class="btn btn-success" style="width: 100%; padding: 12px;" onclick="runBacktest()">▶ Run Backtest</button>
                    
                    <div id="bt_status_msg" style="display: none; margin-top: 16px; padding: 12px; border-radius: 8px; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.2); color: var(--accent-color); text-align: center; font-size: 14px;"></div>
                    
                    <div id="bt_results_container" style="display: none; margin-top: 24px;">
                        <h4 style="color: var(--accent-color); margin-bottom: 10px;">Results</h4>
                        <div id="bt_report_target" style="overflow-x: auto;"></div>
                    </div>
                </div>
            </div>

            <div id="tab-markets" class="tab-content">
                <div style="background: rgba(15, 23, 42, 0.4); border-radius: 8px; padding: 20px; border: 1px solid var(--panel-border);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                        <h4 style="margin: 0; color: var(--accent-color);">📈 Market Watchlist</h4>
                        <button class="btn" style="padding: 6px 14px; font-size: 12px;" onclick="fetchMarketPrices()" id="mkt_refresh_btn">🔄 Refresh</button>
                    </div>
                    <p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 16px;">Live prices from your connected exchange. Updates automatically every 5 seconds when this tab is active.</p>
                    <div id="mkt_status" style="display: none; margin-bottom: 12px; padding: 10px; border-radius: 6px; text-align: center; font-size: 13px;"></div>
                    <div style="overflow-x: auto;">
                        <table style="width: 100%; text-align: left; border-collapse: collapse;">
                            <thead>
                                <tr>
                                    <th style="padding: 10px; border-bottom: 1px solid var(--panel-border); color: var(--text-secondary); font-size: 12px; text-transform: uppercase;">Symbol</th>
                                    <th style="padding: 10px; border-bottom: 1px solid var(--panel-border); color: var(--text-secondary); font-size: 12px; text-transform: uppercase;">Last Price</th>
                                    <th style="padding: 10px; border-bottom: 1px solid var(--panel-border); color: var(--text-secondary); font-size: 12px; text-transform: uppercase;">Bid</th>
                                    <th style="padding: 10px; border-bottom: 1px solid var(--panel-border); color: var(--text-secondary); font-size: 12px; text-transform: uppercase;">Ask</th>
                                    <th style="padding: 10px; border-bottom: 1px solid var(--panel-border); color: var(--text-secondary); font-size: 12px; text-transform: uppercase;">Spread</th>
                                    <th style="padding: 10px; border-bottom: 1px solid var(--panel-border); color: var(--text-secondary); font-size: 12px; text-transform: uppercase;">Status</th>
                                </tr>
                            </thead>
                            <tbody id="mkt_table_body">
                                <tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--text-secondary);">Click Refresh or switch to this tab to load prices...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div class="glass-panel">
            <h3 style="margin-top:0; margin-bottom:15px; color: var(--text-secondary);">System Logs</h3>
            <div class="logs-container" id="logs-container">
                <div class="log-entry" style="color: var(--text-secondary);">Waiting for logs...</div>
            </div>
        </div>
    </div>

    <script>
        function showTab(tabId, btn) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            if (btn) btn.classList.add('active');
        }

        const formatMoney = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
        const formatMoneyWithSign = (val) => {
            const num = parseFloat(val);
            const str = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(Math.abs(num));
            return num >= 0 ? '+' + str : '-' + str;
        };

        async function sendCommand(cmd) {
            if (cmd === 'close_all' && !confirm('Are you sure you want to close ALL active positions? This action cannot be undone.')) {
                return;
            }
            if (cmd === 'stop' && !confirm('Are you sure you want to stop the bot? You will need to restart it from the terminal to resume.')) {
                return;
            }
            try {
                const res = await fetch(`/api/control/${cmd}`, { method: 'POST' });
                if (!res.ok) throw new Error('Command failed');
                updateDashboard();
            } catch (err) {
                alert('Failed to send command: ' + err.message);
            }
        }
        
        async function closePosition(id, provider) {
            if (!confirm(`Are you sure you want to close position ${id} on ${provider}?`)) {
                return;
            }
            try {
                const res = await fetch('/api/control/close_position', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: id, provider: provider })
                });
                if (!res.ok) throw new Error('Close position command failed');
                updateDashboard();
            } catch (err) {
                alert('Failed to send close command: ' + err.message);
            }
        }
        
        async function restartBot() {
            if (!confirm('Are you sure you want to restart the trading engine? This may take a moment to reconnect to exchanges and re-initialize.')) {
                return;
            }
            try {
                const res = await fetch('/api/control/restart', { method: 'POST' });
                if (!res.ok) throw new Error('Restart command failed');
                alert('Restart command issued successfully.');
                updateDashboard();
            } catch (err) {
                alert('Failed to send restart command: ' + err.message);
            }
        }

        async function runBacktest() {
            try {
                const strat = document.getElementById('bt_strategy').value;
                const prov = document.getElementById('bt_provider').value;
                
                document.getElementById('bt_run_btn').disabled = true;
                document.getElementById('bt_run_btn').textContent = '⏳ Starting...';
                document.getElementById('bt_results_container').style.display = 'none';
                document.getElementById('bt_report_target').innerHTML = '';
                const oldRendered = document.getElementById('bt_report_rendered');
                if (oldRendered) oldRendered.remove();
                
                const statusMsg = document.getElementById('bt_status_msg');
                statusMsg.style.display = 'block';
                statusMsg.textContent = '⏳ Backtest submitted, waiting for results...';
                
                const res = await fetch('/api/control/backtest', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        strategies: [strat],
                        providers: [prov]
                    })
                });
                
                const data = await res.json();
                if (!res.ok) {
                    throw new Error(data.error || 'Request failed');
                }
            } catch(e) {
                const statusMsg = document.getElementById('bt_status_msg');
                statusMsg.style.display = 'block';
                statusMsg.style.background = 'rgba(239, 68, 68, 0.1)';
                statusMsg.style.borderColor = 'rgba(239, 68, 68, 0.2)';
                statusMsg.style.color = 'var(--danger-color)';
                statusMsg.textContent = 'Failed: ' + e.message;
                document.getElementById('bt_run_btn').disabled = false;
                document.getElementById('bt_run_btn').textContent = '▶ Run Backtest';
            }
        }

        async function updateBotConfig() {
            try {
                const providerSelect = document.getElementById('conf_provider');
                const selectedProviders = Array.from(providerSelect.selectedOptions).map(opt => opt.value);
                
                const payload = {
                    symbol: document.getElementById('conf_symbol').value,
                    provider: selectedProviders,
                    timeframe: document.getElementById('conf_tf').value,
                    mode: document.getElementById('conf_mode').value,
                    strategy: document.getElementById('conf_strategy').value,
                    lot: document.getElementById('conf_lot').value,
                    leverage: document.getElementById('conf_lev').value,
                    sl_pips: document.getElementById('conf_sl').value,
                    tp_pips: document.getElementById('conf_tp').value,
                    trailing_stop: document.getElementById('conf_ts').value === 'true',
                    trail_start: document.getElementById('conf_ts_start').value,
                    break_even: document.getElementById('conf_be').value === 'true',
                    break_even_offset: document.getElementById('conf_be_offset').value,
                    use_auto_lot: document.getElementById('conf_autolot').value === 'true',
                    risk_percent: document.getElementById('conf_risk').value,
                    max_daily_loss: document.getElementById('conf_maxloss').value,
                    max_drawdown: document.getElementById('conf_maxdd').value,
                    use_asia_session: document.getElementById('conf_asia').value === 'true',
                    use_london_open: document.getElementById('conf_london').value === 'true',
                    use_ny_session: document.getElementById('conf_ny').value === 'true'
                };
                const res = await fetch('/api/control/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!res.ok) throw new Error('Update config command failed');
                alert('Configuration instantly applied!');
                updateDashboard();
            } catch (err) {
                alert('Failed to tune config: ' + err.message);
            }
        }

        let lastLogsCount = 0;
        let isPaused = false;
        let isStopped = false;

        async function updateDashboard() {
            try {
                // Fetch metrics
                const metricsRes = await fetch('/metrics');
                if (metricsRes.ok) {
                    const m = await metricsRes.json();
                    
                    document.getElementById('val-balance').textContent = formatMoney(m.balance);
                    document.getElementById('val-equity').textContent = formatMoney(m.equity);
                    
                    const pnlEl = document.getElementById('val-pnl');
                    pnlEl.textContent = formatMoneyWithSign(m.pnl);
                    pnlEl.className = 'metric-value ' + (m.pnl >= 0 ? 'positive' : 'negative');
                    
                    const unPnlEl = document.getElementById('val-unrealized-pnl');
                    const unrealizedPnl = m.unrealized_pnl || (m.equity - m.balance);
                    unPnlEl.textContent = formatMoneyWithSign(unrealizedPnl);
                    unPnlEl.className = 'metric-value ' + (unrealizedPnl >= 0 ? 'positive' : 'negative');
                    
                    document.getElementById('val-trades').textContent = m.trades;
                    document.getElementById('val-open-positions').textContent = (m.positions && m.positions.length) || 0;
                    document.getElementById('val-price').textContent = m.price.toFixed(3);
                    if (m.config && m.config.symbol) {
                        document.getElementById('val-price-symbol').textContent = m.config.symbol;
                    }
                    
                    document.getElementById('val-margin').textContent = formatMoney(m.margin || 0);
                    document.getElementById('val-freemargin').textContent = formatMoney(m.free_margin || m.equity);

                    // Positions
                    const posBody = document.getElementById('positions-body');
                    document.getElementById('pos-count').textContent = (m.positions && m.positions.length) || 0;
                    
                    if (!m.positions || m.positions.length === 0) {
                        posBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">No active positions</td></tr>';
                    } else {
                        posBody.innerHTML = '';
                        m.positions.forEach(pos => {
                            const tr = document.createElement('tr');
                            const valProvider = pos.provider || 'Unknown';
                            const side = (pos.side || pos.type || 'UNKNOWN').toUpperCase();
                            const sideClass = side === 'BUY' ? 'side-buy' : (side === 'SELL' ? 'side-sell' : '');
                            const vol = pos.volume || pos.amount || pos.size || 0;
                            const entry = pos.entry_price || pos.price || 0;
                            
                            // Use un-injected proper PNL
                            let posPnl = pos.unrealized_pnl || 0;
                            
                            const pnlClass = posPnl >= 0 ? 'positive' : 'negative';

                            tr.innerHTML = `
                                <td><span class="provider-badge">${valProvider}</span></td>
                                <td>${pos.id || '-'}</td>
                                <td class="${sideClass}">${side}</td>
                                <td>${vol.toFixed(3)}</td>
                                <td>${formatMoney(entry)}</td>
                                <td class="${pnlClass}">${formatMoneyWithSign(posPnl)}</td>
                                <td><button class="action-btn" onclick="closePosition('${pos.id}', '${valProvider}')">✕ Close</button></td>
                            `;
                            posBody.appendChild(tr);
                        });
                    }
                    
                    // Pending Orders
                    const ordBody = document.getElementById('orders-body');
                    document.getElementById('orders-count').textContent = (m.orders && m.orders.length) || 0;

                    if (!m.orders || m.orders.length === 0) {
                        ordBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">No pending orders</td></tr>';
                    } else {
                        ordBody.innerHTML = '';
                        m.orders.forEach(ord => {
                            const tr = document.createElement('tr');
                            const valProvider = ord.provider || 'Unknown';
                            const side = (ord.side || ord.type || 'UNKNOWN').toUpperCase();
                            const sideClass = side === 'BUY' ? 'side-buy' : (side === 'SELL' ? 'side-sell' : '');
                            const vol = ord.volume || ord.amount || ord.size || 0;
                            const priceTarget = ord.price || ord.stop_price || 0;
                            const orderType = (ord.order_type || ord.type || 'LIMIT').toUpperCase();

                            tr.innerHTML = `
                                <td><span class="provider-badge">${valProvider}</span></td>
                                <td>${ord.id || ord.orderId || '-'}</td>
                                <td class="${sideClass}">${side}</td>
                                <td>${vol.toFixed(3)}</td>
                                <td>${formatMoney(priceTarget)}</td>
                                <td>${orderType}</td>
                                <td><button class="action-btn" onclick="alert('Order Cancel functionality pending binding!')">✕ Cancel</button></td>
                            `;
                            ordBody.appendChild(tr);
                        });
                    }
                    
                    // Trade History
                    const histBody = document.getElementById('history-body');
                    document.getElementById('history-count').textContent = (m.trade_history && m.trade_history.length) || 0;
                    
                    if (!m.trade_history || m.trade_history.length === 0) {
                        histBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-secondary);">No historical trades yet</td></tr>';
                    } else {
                        histBody.innerHTML = '';
                        // Reverse so newest is on top
                        const revHistory = [...m.trade_history].reverse();
                        revHistory.forEach(trade => {
                            const tr = document.createElement('tr');
                            const valProvider = trade.provider || 'Unknown';
                            const side = (trade.side || trade.type || trade.isBuy ? 'BUY' : 'SELL' || 'UNKNOWN').toUpperCase();
                            const sideClass = side === 'BUY' ? 'side-buy' : (side === 'SELL' ? 'side-sell' : '');
                            const vol = trade.volume || trade.amount || trade.size || trade.notional || 0;
                            const closePx = trade.close_price || trade.price || trade.openPrice || 0;
                            const netFin = trade.pnl || trade.net_pnl || trade.realized_pnl || trade.profit || 0; // Fixed Parsing simulator 'profit'
                            const finClass = netFin >= 0 ? 'positive' : 'negative';

                            tr.innerHTML = `
                                <td><span class="provider-badge">${valProvider}</span></td>
                                <td>${trade.id || trade.tradeID || '-'}</td>
                                <td class="${sideClass}">${side}</td>
                                <td>${vol}</td>
                                <td>${formatMoney(closePx)}</td>
                                <td class="${finClass}">${formatMoneyWithSign(netFin)}</td>
                            `;
                            histBody.appendChild(tr);
                        });
                    }
                    
                    // Parse Config Form securely
                    if (m.config) {
                        const inSymbol = document.getElementById('conf_symbol');
                        const inProv = document.getElementById('conf_provider');
                        const inTf = document.getElementById('conf_tf');
                        const inMode = document.getElementById('conf_mode');
                        const inStrat = document.getElementById('conf_strategy');

                        const inLot = document.getElementById('conf_lot');
                        const inLev = document.getElementById('conf_lev');
                        const inSl = document.getElementById('conf_sl');
                        const inTp = document.getElementById('conf_tp');
                        
                        const inTs = document.getElementById('conf_ts');
                        const inTsStart = document.getElementById('conf_ts_start');
                        const inBe = document.getElementById('conf_be');
                        const inBeOffset = document.getElementById('conf_be_offset');
                        const inAutoLot = document.getElementById('conf_autolot');
                        const inRisk = document.getElementById('conf_risk');
                        const inMaxLoss = document.getElementById('conf_maxloss');
                        const inMaxDd = document.getElementById('conf_maxdd');
                        const inAsia = document.getElementById('conf_asia');
                        const inLond = document.getElementById('conf_london');
                        const inNy = document.getElementById('conf_ny');
                        
                        // Prevent replacing values if the user is actively typing in them
                        if (document.activeElement !== inSymbol && inSymbol.value === '') inSymbol.value = m.config.symbol;
                        if (document.activeElement !== inProv) {
                            const provs = Array.isArray(m.config.provider) ? m.config.provider : [m.config.provider];
                            Array.from(inProv.options).forEach(opt => opt.selected = provs.includes(opt.value));
                        }
                        if (document.activeElement !== inTf && inTf.value === '') inTf.value = m.config.timeframe;
                        if (document.activeElement !== inMode && inMode.value === '') inMode.value = m.config.mode;
                        if (document.activeElement !== inStrat && inStrat.value === '') inStrat.value = m.config.strategy;

                        if (document.activeElement !== inLot && inLot.value === '') inLot.value = m.config.lot;
                        if (document.activeElement !== inLev && inLev.value === '') inLev.value = m.config.leverage;
                        if (document.activeElement !== inSl && inSl.value === '') inSl.value = m.config.sl_pips;
                        if (document.activeElement !== inTp && inTp.value === '') inTp.value = m.config.tp_pips;
                        
                        if (document.activeElement !== inTs) inTs.value = m.config.trailing_stop ? 'true' : 'false';
                        if (document.activeElement !== inTsStart && inTsStart.value === '') inTsStart.value = m.config.trail_start;
                        if (document.activeElement !== inBe) inBe.value = m.config.break_even ? 'true' : 'false';
                        if (document.activeElement !== inBeOffset && inBeOffset.value === '') inBeOffset.value = m.config.break_even_offset;
                        if (document.activeElement !== inAutoLot) inAutoLot.value = m.config.use_auto_lot ? 'true' : 'false';
                        if (document.activeElement !== inRisk && inRisk.value === '') inRisk.value = m.config.risk_percent;
                        if (document.activeElement !== inMaxLoss && inMaxLoss.value === '') inMaxLoss.value = m.config.max_daily_loss;
                        if (document.activeElement !== inMaxDd && inMaxDd.value === '') inMaxDd.value = m.config.max_drawdown;
                        if (document.activeElement !== inAsia) inAsia.value = m.config.use_asia_session ? 'true' : 'false';
                        if (document.activeElement !== inLond) inLond.value = m.config.use_london_open ? 'true' : 'false';
                        if (document.activeElement !== inNy) inNy.value = m.config.use_ny_session ? 'true' : 'false';
                    }
                    
                    // Check Backtest status (outside config block so it always runs)
                    const btStatusMsg = document.getElementById('bt_status_msg');
                    const btBtn = document.getElementById('bt_run_btn');
                    
                    if (m.backtest_status === 'running') {
                        if (btBtn) {
                            btBtn.disabled = true;
                            btBtn.textContent = '⏳ Running Backtest...';
                        }
                        if (btStatusMsg) {
                            btStatusMsg.style.display = 'block';
                            btStatusMsg.style.background = 'rgba(56, 189, 248, 0.1)';
                            btStatusMsg.style.borderColor = 'rgba(56, 189, 248, 0.2)';
                            btStatusMsg.style.color = 'var(--accent-color)';
                            btStatusMsg.textContent = '⏳ Backtest is running... Please wait.';
                        }
                    } else if (m.backtest_status === 'complete' || m.backtest_status === 'error') {
                        if (btBtn) {
                            btBtn.disabled = false;
                            btBtn.textContent = '▶ Run Backtest';
                        }
                        
                        // Parse report if available (only render once)
                        if (m.backtest_report && !document.getElementById('bt_report_rendered')) {
                            const container = document.getElementById('bt_results_container');
                            const target = document.getElementById('bt_report_target');
                            if (container && target) {
                                container.style.display = 'block';
                                
                                if (m.backtest_report.error) {
                                    if (btStatusMsg) {
                                        btStatusMsg.style.display = 'block';
                                        btStatusMsg.style.background = 'rgba(239, 68, 68, 0.1)';
                                        btStatusMsg.style.borderColor = 'rgba(239, 68, 68, 0.2)';
                                        btStatusMsg.style.color = 'var(--danger-color)';
                                        btStatusMsg.textContent = '❌ Backtest failed: ' + m.backtest_report.error;
                                    }
                                    target.innerHTML = `<div id="bt_report_rendered"></div>`;
                                } else if (m.backtest_report.results && m.backtest_report.results.length > 0) {
                                    if (btStatusMsg) {
                                        btStatusMsg.style.display = 'block';
                                        btStatusMsg.style.background = 'rgba(16, 185, 129, 0.1)';
                                        btStatusMsg.style.borderColor = 'rgba(16, 185, 129, 0.2)';
                                        btStatusMsg.style.color = 'var(--success-color)';
                                        btStatusMsg.textContent = '✅ Backtest complete! ' + m.backtest_report.results.length + ' result(s) found.';
                                    }
                                    let tableHTML = `
                                        <table id="bt_report_rendered" style="width: 100%; text-align: left; border-collapse: collapse;">
                                            <thead>
                                                <tr>
                                                    <th style="padding: 8px; border-bottom: 1px solid var(--panel-border);">Strategy</th>
                                                    <th style="padding: 8px; border-bottom: 1px solid var(--panel-border);">Provider</th>
                                                    <th style="padding: 8px; border-bottom: 1px solid var(--panel-border);">Symbol</th>
                                                    <th style="padding: 8px; border-bottom: 1px solid var(--panel-border);">Timeframe</th>
                                                    <th style="padding: 8px; border-bottom: 1px solid var(--panel-border);">Return %</th>
                                                    <th style="padding: 8px; border-bottom: 1px solid var(--panel-border);">Trades</th>
                                                    <th style="padding: 8px; border-bottom: 1px solid var(--panel-border);">Win Rate</th>
                                                    <th style="padding: 8px; border-bottom: 1px solid var(--panel-border);">Max DD</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                    `;
                                    const sortedResults = [...m.backtest_report.results].sort((a,b) => b.result.total_return_pct - a.result.total_return_pct);
                                    sortedResults.forEach(r => {
                                        tableHTML += `
                                            <tr>
                                                <td style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05);">${r.strategy}</td>
                                                <td style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05);">${r.provider}</td>
                                                <td style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05);">${r.symbol || '-'}</td>
                                                <td style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05);">${r.timeframe || '-'}</td>
                                                <td style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05); color: ${r.result.total_return_pct >= 0 ? 'var(--success-color)' : 'var(--danger-color)'}">${r.result.total_return_pct.toFixed(2)}%</td>
                                                <td style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05);">${r.result.total_trades}</td>
                                                <td style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05);">${r.result.win_rate.toFixed(1)}%</td>
                                                <td style="padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.05); color: var(--danger-color);">${r.result.max_drawdown_pct.toFixed(2)}%</td>
                                            </tr>
                                        `;
                                    });
                                    tableHTML += `</tbody></table>`;
                                    target.innerHTML = tableHTML;
                                } else {
                                    if (btStatusMsg) {
                                        btStatusMsg.style.display = 'block';
                                        btStatusMsg.style.background = 'rgba(245, 158, 11, 0.1)';
                                        btStatusMsg.style.borderColor = 'rgba(245, 158, 11, 0.2)';
                                        btStatusMsg.style.color = 'var(--warning-color)';
                                        btStatusMsg.textContent = '⚠️ Backtest completed but no results were returned.';
                                    }
                                    target.innerHTML = '<div id="bt_report_rendered"></div>';
                                }
                            }
                        }
                    } else {
                        // idle state — hide status msg
                        if (btStatusMsg) btStatusMsg.style.display = 'none';
                    }
                }


                // Fetch logs
                const logsRes = await fetch('/logs');
                if (logsRes.ok) {
                    const logs = await logsRes.json();
                    if (logs.length !== lastLogsCount) {
                        const logsContainer = document.getElementById('logs-container');
                        const isScrolledToBottom = logsContainer.scrollHeight - logsContainer.clientHeight <= logsContainer.scrollTop + 10;
                        
                        logsContainer.innerHTML = '';
                        logs.forEach(log => {
                            const div = document.createElement('div');
                            div.className = 'log-entry';
                            div.innerHTML = `
                                <span class="log-time">${log.time}</span>
                                <span class="log-${log.level.toLowerCase()}">${log.message}</span>
                            `;
                            logsContainer.appendChild(div);
                        });
                        
                        if (isScrolledToBottom) {
                            logsContainer.scrollTop = logsContainer.scrollHeight;
                        }
                        lastLogsCount = logs.length;
                    }
                }
                
                // Status
                const healthRes = await fetch('/health');
                const badge = document.getElementById('bot-status');
                
                const btnStart = document.getElementById('btn-start');
                const btnPause = document.getElementById('btn-pause');
                const btnStop = document.getElementById('btn-stop');
                
                if (healthRes.ok) {
                    const h = await healthRes.json();
                    isPaused = h.paused;
                    isStopped = !h.running;
                    
                    if(h.running && !h.paused) {
                        badge.textContent = 'Running';
                        badge.className = 'status-badge running';
                        badge.style.background = 'rgba(16, 185, 129, 0.2)';
                        badge.style.color = 'var(--success-color)';
                        badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                        
                        btnStart.disabled = true;
                        btnPause.disabled = false;
                        btnStop.disabled = false;
                    } else if (h.paused) {
                        badge.textContent = 'Paused';
                        badge.className = 'status-badge';
                        badge.style.background = 'rgba(245, 158, 11, 0.2)';
                        badge.style.color = 'var(--warning-color)';
                        badge.style.borderColor = 'rgba(245, 158, 11, 0.3)';
                        
                        btnStart.disabled = false;
                        btnPause.disabled = true;
                        btnStop.disabled = false;
                    } else {
                        badge.textContent = 'Stopped';
                        badge.className = 'status-badge';
                        badge.style.background = 'rgba(239, 68, 68, 0.2)';
                        badge.style.color = 'var(--danger-color)';
                        badge.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                        
                        btnStart.disabled = true;
                        btnPause.disabled = true;
                        btnStop.disabled = true;
                    }
                }

            } catch (err) {
                const badge = document.getElementById('bot-status');
                badge.textContent = 'Disconnected';
                badge.classList.remove('running');
                badge.style.background = 'rgba(245, 158, 11, 0.2)';
                badge.style.color = 'var(--warning-color)';
                badge.style.borderColor = 'rgba(245, 158, 11, 0.3)';
            }
        }

        updateDashboard();
        setInterval(updateDashboard, 1000);

        // Market Watchlist
        let marketPollInterval = null;
        
        async function fetchMarketPrices() {
            try {
                const res = await fetch('/api/market/prices');
                if (!res.ok) throw new Error('Failed to fetch market prices');
                const data = await res.json();
                
                const tbody = document.getElementById('mkt_table_body');
                const statusDiv = document.getElementById('mkt_status');
                
                if (!data.prices || data.prices.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--text-secondary);">No prices available</td></tr>';
                    return;
                }
                
                statusDiv.style.display = 'none';
                tbody.innerHTML = '';
                
                data.prices.forEach(p => {
                    const tr = document.createElement('tr');
                    const isActive = p.last > 0;
                    const spread = (isActive && p.ask > 0 && p.bid > 0) ? (p.ask - p.bid).toFixed(4) : '-';
                    const priceDisplay = isActive ? p.last.toFixed(p.last > 100 ? 3 : 5) : '-';
                    const bidDisplay = (isActive && p.bid > 0) ? p.bid.toFixed(p.bid > 100 ? 3 : 5) : '-';
                    const askDisplay = (isActive && p.ask > 0) ? p.ask.toFixed(p.ask > 100 ? 3 : 5) : '-';
                    const statusText = isActive ? '🟢 Live' : '⚫ N/A';
                    const statusColor = isActive ? 'var(--success-color)' : 'var(--text-secondary)';
                    const isMainSymbol = p.is_active;
                    const rowBg = isMainSymbol ? 'rgba(56, 189, 248, 0.05)' : 'transparent';
                    
                    tr.innerHTML = `
                        <td style="padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); background: ${rowBg};">
                            <span style="font-weight: 600; color: var(--text-primary);">${p.symbol}</span>
                            ${isMainSymbol ? '<span style="font-size: 10px; margin-left: 6px; padding: 2px 6px; background: rgba(56, 189, 248, 0.15); border-radius: 4px; color: var(--accent-color);">ACTIVE</span>' : ''}
                        </td>
                        <td style="padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); background: ${rowBg}; font-family: monospace; font-weight: 600;">${priceDisplay}</td>
                        <td style="padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); background: ${rowBg}; font-family: monospace; color: var(--success-color);">${bidDisplay}</td>
                        <td style="padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); background: ${rowBg}; font-family: monospace; color: var(--danger-color);">${askDisplay}</td>
                        <td style="padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); background: ${rowBg}; font-family: monospace;">${spread}</td>
                        <td style="padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); background: ${rowBg}; color: ${statusColor};">${statusText}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch(e) {
                const statusDiv = document.getElementById('mkt_status');
                statusDiv.style.display = 'block';
                statusDiv.style.background = 'rgba(239, 68, 68, 0.1)';
                statusDiv.style.color = 'var(--danger-color)';
                statusDiv.textContent = 'Error: ' + e.message;
            }
        }
        
        // Override showTab to manage market polling
        const _origShowTab = showTab;
        showTab = function(tabId, btn) {
            _origShowTab(tabId, btn);
            if (tabId === 'tab-markets') {
                fetchMarketPrices();
                if (!marketPollInterval) {
                    marketPollInterval = setInterval(fetchMarketPrices, 5000);
                }
            } else {
                if (marketPollInterval) {
                    clearInterval(marketPollInterval);
                    marketPollInterval = null;
                }
            }
        };
    </script>
</body>
</html>
"""

CONFIG_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Bot - Configuration</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        
        :root {
            --bg-color: #0f172a;
            --panel-bg: rgba(30, 41, 59, 0.7);
            --panel-border: rgba(255, 255, 255, 0.1);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-color: #38bdf8;
            --success-color: #10b981;
            --danger-color: #ef4444;
            --warning-color: #f59e0b;
        }

        body {
            margin: 0;
            padding: 20px;
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: var(--text-primary);
            min-height: 100vh;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            border-bottom: 1px solid var(--panel-border);
            padding-bottom: 15px;
        }

        h1 {
            font-size: 24px;
            font-weight: 700;
            margin: 0;
            background: linear-gradient(to right, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            color: transparent;
        }

        .btn-back {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--panel-border);
            color: var(--text-primary);
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
        }
        
        .btn-back:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .glass-panel {
            background: var(--panel-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--panel-border);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
        }

        h2 {
            font-size: 18px;
            margin-top: 0;
            margin-bottom: 20px;
            color: var(--accent-color);
        }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }

        .form-group {
            margin-bottom: 16px;
        }

        label {
            display: block;
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        input, select {
            width: 100%;
            padding: 10px;
            border-radius: 8px;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--panel-border);
            color: white;
            font-size: 14px;
            font-family: inherit;
            box-sizing: border-box;
        }

        input:focus, select:focus {
            outline: none;
            border-color: var(--accent-color);
        }

        .btn {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--success-color);
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s ease;
            font-family: inherit;
            width: 100%;
            margin-top: 10px;
        }
        
        .btn:hover {
            background: rgba(16, 185, 129, 0.25);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            border-color: var(--panel-border);
            color: var(--text-primary);
        }
        
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .btn-row {
            display: flex;
            gap: 12px;
            margin-top: 20px;
        }

        .alert {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }

        .alert-success {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--success-color);
        }

        .alert-error {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: var(--danger-color);
        }

        .alert-warning {
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid rgba(245, 158, 11, 0.3);
            color: var(--warning-color);
        }

        .form-group.error input,
        .form-group.error select {
            border-color: var(--danger-color);
        }

        .error-message {
            color: var(--danger-color);
            font-size: 11px;
            margin-top: 4px;
            display: none;
        }

        .form-group.error .error-message {
            display: block;
        }

        .inline-errors {
            margin-bottom: 16px;
        }

        .inline-error {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: var(--danger-color);
            padding: 8px 12px;
            border-radius: 6px;
            margin-bottom: 8px;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Configuration</h1>
            <a href="/" class="btn-back">← Back to Dashboard</a>
        </header>

        <div id="alert" class="alert"></div>
        <div id="inline-errors" class="inline-errors"></div>

        <div class="glass-panel">
            <h2>Trading Settings</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>Mode</label>
                    <select id="conf_mode">
                        <option value="paper">Paper (Simulation)</option>
                        <option value="frontest">Frontest (Demo)</option>
                        <option value="real">Real (Live)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Provider</label>
                    <select id="conf_provider">
                        <option value="simulator">Simulator</option>
                        <option value="exness">Exness</option>
                        <option value="ccxt">CCXT (Binance, Bybit)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Account Type</label>
                    <select id="conf_account">
                        <option value="demo">Demo</option>
                        <option value="real">Real</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Exchange</label>
                    <select id="conf_exchange">
                        <option value="">Select Exchange (CCXT)</option>
                        <option value="binance">Binance</option>
                        <option value="bybit">Bybit</option>
                        <option value="okx">OKX</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Symbol</label>
                    <input type="text" id="conf_symbol" value="XAUUSDm" />
                </div>
                <div class="form-group">
                    <label>Strategy</label>
                    <select id="conf_strategy">
                        <option value="xau_hedging">XAU Hedging</option>
                        <option value="grid">Grid</option>
                        <option value="trend">Trend (EMA)</option>
                        <option value="hft">HFT</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Lot Size</label>
                    <input type="number" id="conf_lot" step="0.01" min="0.001" max="100" />
                </div>
                <div class="form-group">
                    <label>Leverage</label>
                    <input type="number" id="conf_leverage" step="1" min="10" max="5000" />
                </div>
                <div class="form-group">
                    <label>Balance</label>
                    <input type="number" id="conf_balance" step="0.01" min="0" />
                </div>
                <div class="form-group">
                    <label>Stop Loss (Pips)</label>
                    <input type="number" id="conf_sl_pips" step="1" min="0" max="10000" />
                </div>
                <div class="form-group">
                    <label>Take Profit (Pips)</label>
                    <input type="number" id="conf_tp_pips" step="1" min="0" max="10000" />
                </div>
                <div class="form-group">
                    <label>Days to Simulate</label>
                    <input type="number" id="conf_days" step="1" min="1" max="365" />
                </div>
            </div>
        </div>

        <div class="glass-panel">
            <h2>Advanced Settings</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>Trailing Stop</label>
                    <select id="conf_trailing_stop">
                        <option value="false">Disabled</option>
                        <option value="true">Enabled</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Trail Start (Pips)</label>
                    <input type="number" id="conf_trail_start" step="1" min="0" max="10000" />
                </div>
                <div class="form-group">
                    <label>Break Even</label>
                    <select id="conf_break_even">
                        <option value="false">Disabled</option>
                        <option value="true">Enabled</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Break Even Offset (Pips)</label>
                    <input type="number" id="conf_break_even_offset" step="1" min="0" max="10000" />
                </div>
                <div class="form-group">
                    <label>Auto Lot</label>
                    <select id="conf_use_auto_lot">
                        <option value="false">Disabled</option>
                        <option value="true">Enabled</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Auto Lot (Risk %)</label>
                    <input type="number" id="conf_risk_percent" step="0.1" min="0.1" max="100" />
                </div>
            </div>
        </div>

        <div class="glass-panel">
            <h2>Risk Management</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>Max Daily Loss ($)</label>
                    <input type="number" id="conf_max_daily_loss" step="0.01" min="0" />
                </div>
                <div class="form-group">
                    <label>Max Drawdown (%)</label>
                    <input type="number" id="conf_max_drawdown" step="0.1" min="0" max="100" />
                </div>
            </div>
        </div>

        <div class="glass-panel">
            <h2>Session Filters</h2>
            <div class="form-grid">
                <div class="form-group">
                    <label>Asia Session</label>
                    <select id="conf_use_asia_session">
                        <option value="true">Enabled</option>
                        <option value="false">Disabled</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>London Open</label>
                    <select id="conf_use_london_open">
                        <option value="true">Enabled</option>
                        <option value="false">Disabled</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>NY Session</label>
                    <select id="conf_use_ny_session">
                        <option value="true">Enabled</option>
                        <option value="false">Disabled</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="btn-row">
            <button class="btn btn-secondary" onclick="validateConfig()">Validate</button>
            <button class="btn" onclick="saveConfig()">Save Configuration</button>
        </div>
    </div>

    <script>
        const fieldMap = {
            'conf_mode': 'mode',
            'conf_provider': 'provider',
            'conf_account': 'account',
            'conf_exchange': 'exchange',
            'conf_symbol': 'symbol',
            'conf_strategy': 'strategy',
            'conf_lot': 'lot',
            'conf_leverage': 'leverage',
            'conf_balance': 'balance',
            'conf_sl_pips': 'sl_pips',
            'conf_tp_pips': 'tp_pips',
            'conf_days': 'days',
            'conf_trailing_stop': 'trailing_stop',
            'conf_trail_start': 'trail_start',
            'conf_break_even': 'break_even',
            'conf_break_even_offset': 'break_even_offset',
            'conf_use_auto_lot': 'use_auto_lot',
            'conf_risk_percent': 'risk_percent',
            'conf_max_daily_loss': 'max_daily_loss',
            'conf_max_drawdown': 'max_drawdown',
            'conf_use_asia_session': 'use_asia_session',
            'conf_use_london_open': 'use_london_open',
            'conf_use_ny_session': 'use_ny_session'
        };

        function clearErrors() {
            document.querySelectorAll('.form-group').forEach(el => el.classList.remove('error'));
            document.getElementById('inline-errors').innerHTML = '';
        }

        function showFieldError(fieldId, message) {
            const field = document.getElementById(fieldId);
            if (field) {
                const group = field.closest('.form-group');
                if (group) {
                    group.classList.add('error');
                    let errorEl = group.querySelector('.error-message');
                    if (!errorEl) {
                        errorEl = document.createElement('div');
                        errorEl.className = 'error-message';
                        group.appendChild(errorEl);
                    }
                    errorEl.textContent = message;
                }
            }
        }

        function showAlert(message, type) {
            const alert = document.getElementById('alert');
            alert.className = 'alert alert-' + type;
            alert.textContent = message;
            alert.style.display = 'block';
            setTimeout(() => { alert.style.display = 'none'; }, 5000);
        }

        function showInlineErrors(errors) {
            const container = document.getElementById('inline-errors');
            container.innerHTML = '';
            
            // Show inline errors for each field
            errors.forEach(err => {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'inline-error';
                errorDiv.textContent = err;
                container.appendChild(errorDiv);
            });
        }

        async function loadConfig() {
            clearErrors();
            try {
                const res = await fetch('/config');
                if (!res.ok) throw new Error('Failed to load config');
                const cfg = await res.json();
                
                Object.keys(fieldMap).forEach(key => {
                    const configKey = fieldMap[key];
                    const el = document.getElementById(key);
                    if (el && cfg[configKey] !== undefined) {
                        if (el.tagName === 'SELECT') {
                            el.value = String(cfg[configKey]);
                        } else {
                            el.value = cfg[configKey];
                        }
                    }
                });
            } catch (err) {
                console.error('Error loading config:', err);
            }
        }

        function getFormData() {
            const data = {};
            Object.keys(fieldMap).forEach(key => {
                const el = document.getElementById(key);
                const configKey = fieldMap[key];
                if (el) {
                    if (el.tagName === 'SELECT') {
                        const val = el.value;
                        if (configKey === 'provider') data[configKey] = [val];
                        else if (val === 'true') data[configKey] = true;
                        else if (val === 'false') data[configKey] = false;
                        else data[configKey] = val;
                    } else if (el.type === 'number') {
                        data[configKey] = parseFloat(el.value) || 0;
                    } else {
                        data[configKey] = el.value;
                    }
                }
            });
            return data;
        }

        async function validateConfig() {
            clearErrors();
            try {
                const data = getFormData();
                const res = await fetch('/config/validate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await res.json();
                
                if (result.valid) {
                    showAlert('Configuration is valid!', 'success');
                } else {
                    showInlineErrors(result.errors);
                    showAlert('Validation failed. Please check the errors below.', 'error');
                }
            } catch (err) {
                showAlert('Validation failed: ' + err.message, 'error');
            }
        }

        async function saveConfig() {
            clearErrors();
            try {
                const data = getFormData();
                const res = await fetch('/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await res.json();
                
                if (result.ok) {
                    showAlert('Configuration saved successfully!', 'success');
                } else if (result.errors) {
                    showInlineErrors(result.errors);
                    showAlert('Save failed. Please check the errors below.', 'error');
                } else {
                    showAlert('Save failed: ' + (result.error || 'Unknown error'), 'error');
                }
            } catch (err) {
                showAlert('Save failed: ' + err.message, 'error');
            }
        }

        loadConfig();
    </script>
</body>
</html>
"""


class WebInterface(BaseInterface):
    def __init__(
        self,
        config: Optional[InterfaceConfig] = None,
        host: str = "127.0.0.1",
        port: int = 8080,
    ):
        super().__init__(config)
        self.host = host
        self.port = port
        self.server: Optional[ThreadingHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.logs = []
        self.metrics = {
            "price": 0.0,
            "balance": config.balance if config else 100.0,
            "equity": config.balance if config else 100.0,
            "pnl": 0.0,
            "margin": 0.0,
            "free_margin": config.balance if config else 100.0,
            "trades": 0,
            "positions": [],
        }
        self.backtest_status = "idle"
        self.backtest_report = None
        self.backtest_thread: Optional[threading.Thread] = None
        
        # Market watchlist
        self.MARKET_WATCHLIST = [
            "XAUUSDm", "BTCUSDT", "ETHUSDT", "EURUSD", "XAGUSD",
            "GBPUSD", "USDJPY", "BTCUSD"
        ]
        self._market_price_cache = {}
        self._market_cache_time = 0
        self._market_cache_ttl = 2.0  # seconds

    def log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self.logs.append({"time": timestamp, "level": level, "message": message})
            if len(self.logs) > 200:
                self.logs = self.logs[-200:]

    # Add a pseudo paused state to track Web UI side
    @property
    def paused(self):
        return getattr(self, "_paused", False)

    @paused.setter
    def paused(self, value):
        self._paused = value

    def update_metrics(self, metrics: dict):
        with self._lock:
            self.metrics.update(metrics)

    def run_backtest_task(self, strategies: list, providers: list):
        with self._lock:
            self.backtest_status = "running"
            self.backtest_report = None
        
        try:
            report = run_strategy_comparison(strategies=strategies, providers=providers)
            with self._lock:
                self.backtest_status = "complete"
                self.backtest_report = report.to_dict() if report else None
        except Exception as e:
            with self._lock:
                self.backtest_status = "error"
                self.backtest_report = {"error": str(e)}

    def get_market_prices(self):
        """Fetch prices for all watchlist symbols from the primary exchange."""
        import time as _time
        now = _time.time()
        
        # Return cached if fresh
        if now - self._market_cache_time < self._market_cache_ttl and self._market_price_cache:
            return self._market_price_cache
        
        active_symbol = self.config.symbol if self.config else "XAUUSDm"
        prices = []
        
        # Get the trading engine reference
        engine = getattr(self, '_engine', None)
        primary_exchange = None
        if engine and hasattr(engine, 'exchanges') and engine.exchanges:
            primary_exchange = engine.exchanges[0]
        
        for symbol in self.MARKET_WATCHLIST:
            entry = {
                "symbol": symbol,
                "last": 0.0,
                "bid": 0.0,
                "ask": 0.0,
                "is_active": symbol == active_symbol,
            }
            
            # If this is the active symbol, use the metrics price
            if symbol == active_symbol:
                with self._lock:
                    entry["last"] = self.metrics.get("price", 0.0)
                    entry["bid"] = entry["last"] - 0.02
                    entry["ask"] = entry["last"] + 0.02
            elif primary_exchange:
                try:
                    price = primary_exchange.get_price(symbol)
                    if price and price > 0:
                        entry["last"] = price
                        entry["bid"] = price - 0.02
                        entry["ask"] = price + 0.02
                except Exception:
                    pass
            
            prices.append(entry)
        
        # Sort: active symbol first, then by symbol name
        prices.sort(key=lambda p: (0 if p["is_active"] else 1, p["symbol"]))
        
        self._market_price_cache = prices
        self._market_cache_time = now
        return prices

    def _make_handler(self):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, payload, code=200):
                body = json.dumps(payload, default=str).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/health":
                    return self._json(
                        {"ok": True, "running": parent.running, "paused": parent.paused}
                    )
                if self.path == "/metrics":
                    with parent._lock:
                        payload = dict(parent.metrics)
                        if parent.config:
                            payload["config"] = parent.config.to_dict()
                        payload["backtest_status"] = parent.backtest_status
                        payload["backtest_report"] = parent.backtest_report
                        return self._json(payload)
                if self.path == "/logs":
                    with parent._lock:
                        return self._json(parent.logs[-100:])
                if self.path == "/config":
                    # Return current config as JSON (without credentials)
                    config_dict = {}
                    if parent.config:
                        config_dict = parent.config.to_dict()
                    return self._json(config_dict)
                if self.path == "/config/page":
                    # Return HTML config page
                    html = CONFIG_PAGE_HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html)))
                    self.end_headers()
                    self.wfile.write(html)
                    return
                if self.path == "/api/market/prices":
                    try:
                        prices = parent.get_market_prices()
                        return self._json({"prices": prices})
                    except Exception as e:
                        return self._json({"error": str(e)}, 500)
                if self.path == "/":
                    html = DASHBOARD_HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html)))
                    self.end_headers()
                    self.wfile.write(html)
                    return
                self._json({"error": "not found"}, 404)

            def do_POST(self):
                if self.path == "/api/control/start":
                    if parent.on_resume_callback:
                        parent.on_resume_callback()
                    parent.paused = False
                    return self._json({"ok": True})
                if self.path == "/api/control/pause":
                    if parent.on_pause_callback:
                        parent.on_pause_callback()
                    parent.paused = True
                    return self._json({"ok": True})
                if self.path == "/api/control/stop":
                    if parent.on_stop_callback:
                        parent.on_stop_callback()
                    parent.stop()
                    return self._json({"ok": True})
                if self.path == "/api/control/close_all":
                    if parent.on_close_all_callback:
                        parent.on_close_all_callback()
                    return self._json({"ok": True})
                if self.path == "/api/control/backtest":
                    content_length = int(self.headers.get("Content-Length", 0))
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode("utf-8")) if post_data else {}
                    
                    strategies = data.get("strategies", ["HFT"])
                    if "all" in strategies:
                        strategies = None
                        
                    providers = data.get("providers", ["simulator"])
                    if "all" in providers:
                        providers = ["simulator", "ostium", "exness", "ccxt"]
                        
                    with parent._lock:
                        if parent.backtest_status == "running":
                            return self._json({"error": "Backtest already running"}, 400)
                        
                        parent.backtest_thread = threading.Thread(
                            target=parent.run_backtest_task,
                            args=(strategies, providers),
                            daemon=True
                        )
                        parent.backtest_thread.start()
                    
                    return self._json({"ok": True, "message": "Backtest started"})
                if self.path == "/api/control/restart":
                    # For a clean restart, we want to run this slightly deferred so the response sends cleanly.
                    if parent.on_restart_callback:
                        threading.Timer(1.0, parent.on_restart_callback).start()
                    return self._json({"ok": True})
                if self.path == "/api/control/close_position":
                    content_length = int(self.headers.get("Content-Length", 0))
                    if content_length > 0:
                        try:
                            body = self.rfile.read(content_length).decode("utf-8")
                            data = json.loads(body)
                            pos_id = data.get("id")
                            provider = data.get("provider")
                            if pos_id and parent.on_close_position_callback:
                                parent.on_close_position_callback(
                                    pos_id=pos_id, provider_name=provider
                                )
                                return self._json({"ok": True})
                        except Exception as e:
                            parent.log(f"Error executing close position: {e}", "error")
                            return self._json({"error": "Bad Request"}, 400)
                    return self._json({"error": "Missing params"}, 400)
                if self.path == "/api/control/config":
                    content_length = int(self.headers.get("Content-Length", 0))
                    if content_length > 0:
                        try:
                            body = self.rfile.read(content_length).decode("utf-8")
                            data = json.loads(body)
                            if parent.on_config_update_callback:
                                parent.on_config_update_callback(data)
                            return self._json({"ok": True})
                        except Exception as e:
                            parent.log(f"Error updating config: {e}", "error")
                            return self._json({"error": "Bad Request"}, 400)
                    return self._json({"error": "Missing params"}, 400)
                if self.path == "/config":
                    content_length = int(self.headers.get("Content-Length", 0))
                    if content_length > 0:
                        try:
                            body = self.rfile.read(content_length).decode("utf-8")
                            data = json.loads(body)

                            if parent.config:
                                for key, value in data.items():
                                    if hasattr(parent.config, key):
                                        setattr(parent.config, key, value)

                                errors = parent.config.validate()
                                if errors:
                                    return self._json(
                                        {"ok": False, "errors": errors}, 400
                                    )

                                try:
                                    save_config(parent.config)
                                    parent.log("Configuration saved via web", "info")
                                except Exception as e:
                                    parent.log(f"Error saving config: {e}", "error")
                                    return self._json(
                                        {"ok": False, "error": str(e)}, 500
                                    )

                                return self._json({"ok": True})
                            else:
                                return self._json({"error": "No config loaded"}, 400)
                        except json.JSONDecodeError as e:
                            return self._json({"error": "Invalid JSON"}, 400)
                        except Exception as e:
                            parent.log(f"Error updating config: {e}", "error")
                            return self._json({"error": str(e)}, 400)
                    return self._json({"error": "Missing body"}, 400)
                if self.path == "/config/validate":
                    content_length = int(self.headers.get("Content-Length", 0))
                    if content_length > 0:
                        try:
                            body = self.rfile.read(content_length).decode("utf-8")
                            data = json.loads(body)

                            temp_config = InterfaceConfig(**data)
                            errors = temp_config.validate()

                            if errors:
                                return self._json(
                                    {"valid": False, "errors": errors}, 200
                                )

                            return self._json({"valid": True, "errors": []}, 200)
                        except json.JSONDecodeError as e:
                            return self._json(
                                {"valid": False, "errors": ["Invalid JSON: " + str(e)]},
                                400,
                            )
                        except Exception as e:
                            return self._json({"valid": False, "errors": [str(e)]}, 400)
                    return self._json({"valid": False, "errors": ["Missing body"]}, 400)
                self._json({"error": "not found"}, 404)

            def log_message(self, format, *args):
                return

        return Handler

    def run(self):
        self.running = True

        def signal_handler(sig, frame):
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.server = ThreadingHTTPServer((self.host, self.port), self._make_handler())
        self.server_thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.server_thread.start()

        self.log(f"Web interface serving on http://{self.host}:{self.port}", "info")

        try:
            webbrowser.open(f"http://{self.host}:{self.port}", new=2)
        except Exception:
            pass

        if self.on_start_callback:
            self.on_start_callback(self.config)

        while self.running:
            threading.Event().wait(0.1)

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.on_stop_callback:
            self.on_stop_callback()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2)
        self.server_thread = None
