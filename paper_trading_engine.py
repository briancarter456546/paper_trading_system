"""
PAPER TRADING ENGINE MODULE
Executes simulated trades and tracks performance in SQLite database.
"""

import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path


# Configuration
SLIPPAGE = 0.0005  # 0.05%
HOLD_DAYS = 5
DB_PATH = 'data/positions_log.db'
INITIAL_CAPITAL = 100000  # $100k paper trading account


@dataclass
class Position:
    """Represents an open position."""
    id: int
    signal_name: str
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    position_size_pct: float
    is_boosted: bool
    regime_at_entry: str
    target_exit_date: str
    status: str  # 'OPEN' or 'CLOSED'
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None


class PaperTradingEngine:
    """Manages paper trading execution and tracking."""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_name TEXT NOT NULL,
                ticker TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                position_size_pct REAL NOT NULL,
                is_boosted INTEGER NOT NULL,
                regime_at_entry TEXT NOT NULL,
                target_exit_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                exit_date TEXT,
                exit_price REAL,
                pnl REAL,
                pnl_pct REAL
            )
        ''')
        
        # Daily metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date TEXT PRIMARY KEY,
                total_trades INTEGER,
                wins INTEGER,
                losses INTEGER,
                win_rate REAL,
                avg_return REAL,
                total_pnl REAL,
                regime TEXT,
                regime_confidence REAL
            )
        ''')
        
        # Signals log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                signal_name TEXT NOT NULL,
                trigger_ticker TEXT NOT NULL,
                target_ticker TEXT NOT NULL,
                trigger_momentum REAL NOT NULL,
                is_killed INTEGER NOT NULL,
                kill_reason TEXT,
                is_boosted INTEGER NOT NULL,
                regime TEXT NOT NULL,
                action_taken TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def enter_position(self, signal, current_date: str, capital: float = INITIAL_CAPITAL):
        """
        Enter a new position based on signal.
        
        Args:
            signal: Signal object from signal_generator
            current_date: Entry date string (YYYY-MM-DD)
            capital: Available capital
            
        Returns:
            Position object or None if killed
        """
        # Log the signal regardless of action
        self._log_signal(signal, current_date)
        
        # Don't enter if killed
        if signal.is_killed:
            return None
        
        # Calculate position size
        position_value = capital * (signal.position_size / 100)
        
        # Apply slippage to entry (buy at ask)
        entry_price_with_slip = signal.entry_price * (1 + SLIPPAGE)
        
        # Calculate shares
        shares = int(position_value / entry_price_with_slip)
        if shares == 0:
            return None
        
        # Calculate target exit date (5 trading days)
        # Simple approximation: add 7 calendar days (covers weekends)
        entry_dt = datetime.strptime(current_date, '%Y-%m-%d')
        target_exit_dt = entry_dt + timedelta(days=7)
        target_exit_date = target_exit_dt.strftime('%Y-%m-%d')
        
        # Insert into database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO positions 
            (signal_name, ticker, entry_date, entry_price, shares, 
             position_size_pct, is_boosted, regime_at_entry, target_exit_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
        ''', (
            signal.name,
            signal.target_ticker,
            current_date,
            entry_price_with_slip,
            shares,
            signal.position_size,
            1 if signal.is_boosted else 0,
            signal.regime,
            target_exit_date,
        ))
        
        position_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return Position(
            id=position_id,
            signal_name=signal.name,
            ticker=signal.target_ticker,
            entry_date=current_date,
            entry_price=entry_price_with_slip,
            shares=shares,
            position_size_pct=signal.position_size,
            is_boosted=signal.is_boosted,
            regime_at_entry=signal.regime,
            target_exit_date=target_exit_date,
            status='OPEN',
        )
    
    def _log_signal(self, signal, current_date: str):
        """Log signal to database."""
        action = 'KILLED' if signal.is_killed else 'ENTERED'
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO signals_log
            (date, signal_name, trigger_ticker, target_ticker, trigger_momentum,
             is_killed, kill_reason, is_boosted, regime, action_taken)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            current_date,
            signal.name,
            signal.trigger_ticker,
            signal.target_ticker,
            signal.trigger_momentum,
            1 if signal.is_killed else 0,
            signal.kill_reason,
            1 if signal.is_boosted else 0,
            signal.regime,
            action,
        ))
        
        conn.commit()
        conn.close()
    
    def check_exits(self, current_date: str, current_prices: dict) -> List[Position]:
        """
        Check for positions that need to be closed today.
        
        Args:
            current_date: Current date string (YYYY-MM-DD)
            current_prices: Dict of ticker: price
            
        Returns:
            List of closed Position objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find positions to close (target_exit_date <= current_date)
        cursor.execute('''
            SELECT id, signal_name, ticker, entry_date, entry_price, shares,
                   position_size_pct, is_boosted, regime_at_entry, target_exit_date
            FROM positions
            WHERE status = 'OPEN' AND target_exit_date <= ?
        ''', (current_date,))
        
        rows = cursor.fetchall()
        closed_positions = []
        
        for row in rows:
            position_id, signal_name, ticker, entry_date, entry_price, shares, \
                position_size_pct, is_boosted, regime_at_entry, target_exit_date = row
            
            # Get exit price
            if ticker not in current_prices:
                continue
            
            # Apply slippage to exit (sell at bid)
            exit_price = current_prices[ticker] * (1 - SLIPPAGE)
            
            # Calculate P&L
            pnl = (exit_price - entry_price) * shares
            pnl_pct = (exit_price / entry_price - 1) * 100
            
            # Update database
            cursor.execute('''
                UPDATE positions
                SET status = 'CLOSED', exit_date = ?, exit_price = ?, pnl = ?, pnl_pct = ?
                WHERE id = ?
            ''', (current_date, exit_price, pnl, pnl_pct, position_id))
            
            closed_positions.append(Position(
                id=position_id,
                signal_name=signal_name,
                ticker=ticker,
                entry_date=entry_date,
                entry_price=entry_price,
                shares=shares,
                position_size_pct=position_size_pct,
                is_boosted=bool(is_boosted),
                regime_at_entry=regime_at_entry,
                target_exit_date=target_exit_date,
                status='CLOSED',
                exit_date=current_date,
                exit_price=exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
            ))
        
        conn.commit()
        conn.close()
        
        return closed_positions
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, signal_name, ticker, entry_date, entry_price, shares,
                   position_size_pct, is_boosted, regime_at_entry, target_exit_date
            FROM positions
            WHERE status = 'OPEN'
        ''')
        
        positions = []
        for row in cursor.fetchall():
            positions.append(Position(
                id=row[0],
                signal_name=row[1],
                ticker=row[2],
                entry_date=row[3],
                entry_price=row[4],
                shares=row[5],
                position_size_pct=row[6],
                is_boosted=bool(row[7]),
                regime_at_entry=row[8],
                target_exit_date=row[9],
                status='OPEN',
            ))
        
        conn.close()
        return positions
    
    def get_performance_metrics(self) -> dict:
        """Calculate overall performance metrics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END),
                   AVG(pnl_pct),
                   SUM(pnl),
                   AVG(CASE WHEN pnl > 0 THEN pnl_pct END),
                   AVG(CASE WHEN pnl <= 0 THEN pnl_pct END)
            FROM positions
            WHERE status = 'CLOSED'
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        total_trades = row[0] or 0
        wins = row[1] or 0
        losses = row[2] or 0
        avg_return = row[3] or 0
        total_pnl = row[4] or 0
        avg_win = row[5] or 0
        avg_loss = row[6] or 0
        
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': round(win_rate, 1),
            'avg_return': round(avg_return, 3),
            'total_pnl': round(total_pnl, 2),
            'avg_win': round(avg_win, 3),
            'avg_loss': round(avg_loss, 3),
        }
    
    def save_daily_metrics(self, current_date: str, regime: str, regime_confidence: float):
        """Save daily metrics snapshot."""
        metrics = self.get_performance_metrics()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO daily_metrics
            (date, total_trades, wins, losses, win_rate, avg_return, total_pnl, regime, regime_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            current_date,
            metrics['total_trades'],
            metrics['wins'],
            metrics['losses'],
            metrics['win_rate'],
            metrics['avg_return'],
            metrics['total_pnl'],
            regime,
            regime_confidence,
        ))
        
        conn.commit()
        conn.close()


def format_position_summary(positions: List[Position], title: str) -> str:
    """Format positions for display/logging."""
    if not positions:
        return f"{title}: None"
    
    lines = [f"{title}:", "-" * 50]
    
    for p in positions:
        if p.status == 'CLOSED':
            emoji = "✅" if p.pnl > 0 else "❌"
            lines.append(f"{emoji} {p.signal_name}: {p.ticker}")
            lines.append(f"   Entry: ${p.entry_price:.2f} on {p.entry_date}")
            lines.append(f"   Exit:  ${p.exit_price:.2f} on {p.exit_date}")
            lines.append(f"   P&L:   ${p.pnl:.2f} ({p.pnl_pct:+.2f}%)")
        else:
            lines.append(f"📊 {p.signal_name}: {p.ticker}")
            lines.append(f"   Entry: ${p.entry_price:.2f} on {p.entry_date}")
            lines.append(f"   Target Exit: {p.target_exit_date}")
            lines.append(f"   Shares: {p.shares}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Test the engine
    engine = PaperTradingEngine(db_path='data/test_positions.db')
    
    print("Paper Trading Engine initialized")
    print(f"Database: {engine.db_path}")
    
    metrics = engine.get_performance_metrics()
    print(f"\nCurrent Metrics: {metrics}")
    
    positions = engine.get_open_positions()
    print(format_position_summary(positions, "\nOpen Positions"))
