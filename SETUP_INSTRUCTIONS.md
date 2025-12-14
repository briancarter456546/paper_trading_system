# PAPER TRADING SYSTEM - SETUP INSTRUCTIONS

## Overview

This system paper trades the proven credit-based ETF signals:
- **JNK → IWM** (high-yield bonds → small-caps, with PLTM booster)
- **ANGL → COPX** (fallen angels → copper miners)
- **HYG → MDY** (high-yield → mid-caps)

It runs daily at market close, detects the current regime, generates signals, and tracks performance.

---

## Quick Start for Anaconda/Jupyter Users (5 Minutes)

If you already use Jupyter Notebooks with Anaconda, you know the terminal. This is the same thing—just no GUI.

### Step 1: Download Files

Download all files and put them in a folder:
```
~/paper_trading_system/
├── requirements.txt
├── data_fetcher.py
├── regime_detector.py
├── signal_generator.py
├── paper_trading_engine.py
├── cron_runner.py
└── data/
    └── regime_fingerprints_derived.json
```

### Step 2: Open Terminal

- **Windows:** Start Menu → "Anaconda Prompt"
- **Mac:** Applications → Utilities → Terminal
- **Linux:** Open Terminal

This is the same terminal you use for Jupyter. Just no notebook GUI.

### Step 3: One-Time Setup (Copy-Paste This)

```bash
# Navigate to your folder
cd ~/paper_trading_system

# Create conda environment (recommended)
conda create -n paper_trading python=3.11 -y
conda activate paper_trading

# Install dependencies
pip install -r requirements.txt

# Create data and logs directories
mkdir -p data logs

# Test it works
python cron_runner.py
```

You should see output like:
```
======================================================================
PAPER TRADING SYSTEM - DAILY RUN
======================================================================
Time: 2025-01-15 16:30:00
STEP 1: FETCHING MARKET DATA
✓ Fetched 100 days of data
...
```

### Step 4: Set Up Daily Automation

**Option A: GitHub Actions (Recommended - Free, Runs Automatically)**

```bash
# Initialize Git
git init
git add .
git commit -m "Initial paper trading setup"

# Create GitHub Actions workflow
mkdir -p .github/workflows

cat > .github/workflows/daily_trading.yml << 'EOF'
name: Daily Paper Trading
on:
  schedule:
    - cron: '30 21 * * 1-5'  # 4:30 PM EST (21:30 UTC) Mon-Fri
  workflow_dispatch:  # Allow manual runs

jobs:
  trade:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run paper trading
        run: python cron_runner.py
      - name: Commit results
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add data/
          git diff --quiet && git diff --staged --quiet || git commit -m "Daily trading run $(date +%Y-%m-%d)"
          git push
EOF

# Add and commit the workflow
git add .github/
git commit -m "Add GitHub Actions workflow"

# Push to GitHub (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/paper_trading_system.git
git push -u origin main
```

**Option B: Local Cron (Mac/Linux)**

```bash
# Edit crontab
crontab -e

# Add this line (4:30 PM EST Monday-Friday):
30 16 * * 1-5 cd ~/paper_trading_system && ~/anaconda3/envs/paper_trading/bin/python cron_runner.py >> logs/cron.log 2>&1
```

**Option C: Windows Task Scheduler**

1. Open Task Scheduler
2. Create Basic Task → "Paper Trading Daily"
3. Trigger: Daily at 4:30 PM
4. Action: Start a program
5. Program: `C:\Users\YOU\anaconda3\envs\paper_trading\python.exe`
6. Arguments: `cron_runner.py`
7. Start in: `C:\Users\YOU\paper_trading_system`

---

## Standard Setup (Non-Anaconda Users)

### Step 1: Install Dependencies

```bash
cd paper_trading_system
pip install -r requirements.txt
```

### Step 2: Create Data Directory

```bash
mkdir -p data logs
```

### Step 3: Copy Fingerprints File

Copy your `regime_fingerprints_derived.json` file to the `data/` directory:

```bash
cp /path/to/regime_fingerprints_derived.json data/
```

### Step 4: Test Run

```bash
python cron_runner.py
```

You should see output showing:
- Market data fetched
- Regime detected
- Signals generated (or "No signals fired")
- Performance metrics

### Step 5: Set Up Cron (Automated Daily Runs)

Edit your crontab:

```bash
crontab -e
```

Add this line (runs at 4:30 PM EST Monday-Friday):

```
30 16 * * 1-5 cd /full/path/to/paper_trading_system && /usr/bin/python3 cron_runner.py >> logs/cron.log 2>&1
```

**Note:** Adjust the time for your timezone. 4:30 PM EST = 21:30 UTC.

---

## File Structure

```
paper_trading_system/
├── requirements.txt          # Python dependencies
├── data_fetcher.py           # Fetches prices, calculates factors
├── regime_detector.py        # Detects market regime
├── signal_generator.py       # Generates trading signals
├── paper_trading_engine.py   # Executes & tracks trades
├── cron_runner.py            # Main entry point (run daily)
├── data/
│   ├── regime_fingerprints_derived.json  # YOU PROVIDE THIS
│   └── positions_log.db      # Auto-created SQLite database
└── logs/
    └── cron.log              # Cron output logs
```

---

## What Each Module Does

### data_fetcher.py
- Fetches daily prices from Yahoo Finance (free)
- Calculates 10 regime factors (momentum, VIX, correlations)
- Calculates 10-day momentum for signal triggers

### regime_detector.py
- Loads regime fingerprints from JSON
- Scores current factors against each regime
- Returns detected regime + confidence score

### signal_generator.py
- Checks if JNK, ANGL, or HYG momentum > 1.5%
- Applies UUP kill switch (for JNK/HYG)
- Applies PLTM booster (for JNK)
- Returns list of active signals

### paper_trading_engine.py
- Enters positions at close + 0.05% slippage
- Exits positions after 5 trading days at close - 0.05% slippage
- Tracks all trades in SQLite database
- Calculates win rate, average return, total P&L

### cron_runner.py
- Orchestrates the daily workflow
- Prints detailed log of all actions
- Saves daily metrics snapshot

---

## Database Schema

The SQLite database (`data/positions_log.db`) contains:

### positions table
| Column | Description |
|--------|-------------|
| id | Unique position ID |
| signal_name | JNK_IWM, ANGL_COPX, or HYG_MDY |
| ticker | Target ETF (IWM, COPX, MDY) |
| entry_date | Date position opened |
| entry_price | Entry price with slippage |
| shares | Number of shares |
| position_size_pct | Position size as % of portfolio |
| is_boosted | 1 if PLTM booster was active |
| regime_at_entry | Regime when trade was entered |
| target_exit_date | Expected exit date |
| status | OPEN or CLOSED |
| exit_date | Date position closed (if closed) |
| exit_price | Exit price with slippage (if closed) |
| pnl | Dollar P&L (if closed) |
| pnl_pct | Percentage P&L (if closed) |

### signals_log table
| Column | Description |
|--------|-------------|
| date | Signal date |
| signal_name | Which signal fired |
| trigger_momentum | Momentum that triggered |
| is_killed | Was it killed by UUP? |
| is_boosted | Was PLTM booster active? |
| action_taken | ENTERED or KILLED |

### daily_metrics table
| Column | Description |
|--------|-------------|
| date | Date |
| total_trades | Cumulative trades |
| wins | Cumulative wins |
| win_rate | Current win rate |
| total_pnl | Cumulative P&L |
| regime | Detected regime |

---

## Viewing Results

### Option 1: Command Line

```bash
sqlite3 data/positions_log.db

-- All closed trades
SELECT * FROM positions WHERE status='CLOSED';

-- Win rate by signal
SELECT signal_name, 
       COUNT(*) as trades,
       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
       ROUND(AVG(pnl_pct), 2) as avg_return
FROM positions 
WHERE status='CLOSED'
GROUP BY signal_name;

-- Win rate by regime
SELECT regime_at_entry,
       COUNT(*) as trades,
       ROUND(100.0 * SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
FROM positions
WHERE status='CLOSED'
GROUP BY regime_at_entry;
```

### Option 2: Export to CSV

```bash
sqlite3 -header -csv data/positions_log.db \
  "SELECT * FROM positions WHERE status='CLOSED'" > closed_trades.csv
```

### Option 3: Python

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/positions_log.db')
df = pd.read_sql('SELECT * FROM positions WHERE status="CLOSED"', conn)
print(df)
```

---

## Configuration

### Position Sizing

Edit `paper_trading_engine.py`:

```python
INITIAL_CAPITAL = 100000  # Change this to your paper trading capital
```

### Slippage Assumption

Edit `paper_trading_engine.py`:

```python
SLIPPAGE = 0.0005  # 0.05% - adjust based on real fills
```

### Momentum Threshold

Edit `signal_generator.py`:

```python
MOMENTUM_THRESHOLD = 0.015  # 1.5%
```

---

## Troubleshooting

### "No module named 'yfinance'"
```bash
pip install yfinance
```

### "FileNotFoundError: regime_fingerprints_derived.json"
Copy the fingerprints file to `data/` directory.

### "No signals fired" every day
Normal - signals only fire when momentum > 1.5%. This happens ~2-4 times per week on average.

### Cron not running
Check cron logs:
```bash
tail -f logs/cron.log
```

Verify cron is active:
```bash
crontab -l
```

---

## Expected Results

After 4-8 weeks of paper trading, you should see:

| Metric | Expected | Red Flag |
|--------|----------|----------|
| Win Rate | 58-65% | <50% |
| Avg Return | +0.4% to +0.8% | Negative |
| Trades/Week | 2-5 | 0 (system broken) |
| Slippage Impact | <0.15% | >0.25% |

If results match expectations → Ready to scale to real trading
If results diverge significantly → Debug before proceeding

---

## Next Steps

1. **Run for 2-4 weeks** - Collect paper trading data
2. **Compare to historical** - Is win rate close to 60%?
3. **Check slippage** - Is 0.05% assumption realistic?
4. **Validate regime detection** - Does current regime match market conditions?
5. **If all pass** - Consider small real positions (0.1-0.5%)

---

## Support

This system implements the findings from the Sector Sequence Project. See:
- `sector_sequence_master.md` - Full research documentation
- `trading_guide_beginner.md` - Beginner-friendly trading guide
- `backtest_8regime.md` - Backtest script used to validate signals
