# OpenClaw Integration Guide

This document explains how to integrate Daily Stock Analysis (DSA) with [OpenClaw](https://github.com/nicholasxuu/OpenClaw) for voice-controlled stock analysis.

## Overview

OpenClaw is a voice assistant framework that can execute local commands. DSA provides a CLI tool (`dsa-cli`) that OpenClaw can call directly to perform stock analysis.

```
User Voice Command → OpenClaw → dsa-cli → DSA Analysis → Response
```

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Node.js | ≥22 | OpenClaw dependency |
| Python | ≥3.10 | DSA dependency |
| Operating System | Linux/macOS/Windows | Tested on Linux |

## Installation

### Step 1: Install DSA

```bash
# Clone the repository
git clone https://github.com/Zhangbu/daily_stock_analysis.git
cd daily_stock_analysis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Step 2: Configure DSA

Edit `.env` file:

```env
# Required: AI Model Configuration
MODEL_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key

# Alternative: OpenAI
# MODEL_PROVIDER=openai
# OPENAI_API_KEY=your_openai_api_key

# Optional: News Search APIs (for news command)
TAVILY_API_KEY=your_tavily_key
# or
SERPAPI_API_KEY=your_serpapi_key
# or
BOCHA_API_KEY=your_bocha_key

# Data Source (default: akshare, free)
DATA_PROVIDER=akshare
```

### Step 3: Verify DSA CLI

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Test quote command
./dsa-cli quote 600519 --json

# Expected output: JSON with stock price, change %, etc.
```

### Step 4: Install OpenClaw

Follow the [OpenClaw installation guide](https://github.com/nicholasxuu/OpenClaw):

```bash
# Clone OpenClaw
git clone https://github.com/nicholasxuu/OpenClaw.git
cd OpenClaw

# Install dependencies
npm install

# Build
npm run build
```

### Step 5: Deploy DSA Skill to OpenClaw

Copy the skill file to OpenClaw's skills directory:

```bash
# Create skills directory if not exists
mkdir -p OpenClaw/skills/dsa

# Copy SKILL.md
cp daily_stock_analysis/skills/dsa/SKILL.md OpenClaw/skills/dsa/
```

### Step 6: Configure OpenClaw to Use DSA

Create or edit OpenClaw's configuration to include the DSA skill path:

```json
{
  "skills": {
    "paths": ["./skills/dsa"]
  }
}
```

Ensure `dsa-cli` is in PATH or use absolute path:

```bash
# Option 1: Add to PATH
export PATH="/path/to/daily_stock_analysis:$PATH"

# Option 2: Create symlink
sudo ln -s /path/to/daily_stock_analysis/dsa-cli /usr/local/bin/dsa-cli

# Option 3: Use absolute path in SKILL.md (modify the commands)
```

## Usage

### Voice Commands

Once configured, you can use voice commands like:

| Voice Command | DSA CLI Command |
|---------------|-----------------|
| "分析茅台" | `dsa-cli analyze 600519 --json` |
| "茅台多少钱" | `dsa-cli quote 600519 --json` |
| "茅台走势" | `dsa-cli trend 600519 --json` |
| "茅台新闻" | `dsa-cli news 600519 --json` |
| "分析茅台和平安" | `dsa-cli batch 600519,000001 --json` |

### CLI Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `analyze` | Full AI analysis with sentiment score | `dsa-cli analyze 600519 --json` |
| `quote` | Real-time price and change | `dsa-cli quote 600519 --json` |
| `trend` | Technical trend analysis (MA/MACD/RSI) | `dsa-cli trend 600519 --json` |
| `news` | Search recent stock news | `dsa-cli news 600519 --json --days 7` |
| `ma` | Moving average analysis | `dsa-cli ma 600519 --json` |
| `pattern` | K-line pattern recognition | `dsa-cli pattern 600519 --json` |
| `volume` | Volume-price analysis | `dsa-cli volume 600519 --json` |
| `levels` | Support/resistance levels | `dsa-cli levels 600519 --json` |
| `batch` | Multiple stocks at once | `dsa-cli batch 600519,000858 --json` |

### Output Modes

| Mode | Flag | Use Case |
|------|------|----------|
| JSON | `--json` | OpenClaw parsing (recommended) |
| Brief | `--brief` | Reduced token consumption |
| Human | (default) | Terminal viewing |

## Stock Code Format

| Market | Format | Examples |
|--------|--------|----------|
| A-shares (Shanghai) | 6-digit | 600519, 601398 |
| A-shares (Shenzhen) | 6-digit | 000001, 000858 |
| A-shares (ChiNext) | 6-digit | 300750, 300059 |
| US Stocks | Ticker | AAPL, TSLA, NVDA |
| Hong Kong | 5-digit | 00700, 03690 |

You can also use Chinese stock names:
- "茅台" → 600519
- "平安银行" → 000001
- "五粮液" → 000858

## Configuration Details

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MODEL_PROVIDER` | Yes | `gemini` or `openai` |
| `GEMINI_API_KEY` | If using Gemini | Google AI API key |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `DATA_PROVIDER` | No | Default: `akshare` (free) |
| `TAVILY_API_KEY` | No | For news search |
| `SERPAPI_API_KEY` | No | Alternative news source |
| `BOCHA_API_KEY` | No | Alternative news source |

### Supported Data Providers

| Provider | Free | Speed | Coverage |
|----------|------|-------|----------|
| akshare | ✅ | Medium | A-shares only |
| efinance | ✅ | Fast | A-shares only |
| tushare | ❌ | Fast | A-shares only |
| yfinance | ✅ | Slow | US/HK stocks |

### Supported AI Models

| Provider | Models | Notes |
|----------|--------|-------|
| Gemini | gemini-2.0-flash, gemini-1.5-pro | Recommended |
| OpenAI | gpt-4o, gpt-4-turbo | Good quality |
| LiteLLM | Any supported model | Use `LITELLM_API_BASE` |

## Troubleshooting

### "command not found: dsa-cli"

```bash
# Solution 1: Use absolute path
/path/to/daily_stock_analysis/dsa-cli quote 600519 --json

# Solution 2: Add to PATH
export PATH="/path/to/daily_stock_analysis:$PATH"

# Solution 3: Create symlink
sudo ln -s /path/to/daily_stock_analysis/dsa-cli /usr/local/bin/dsa-cli
```

### "No module named 'src'"

```bash
# Make sure you're in the project directory
cd /path/to/daily_stock_analysis

# Or activate virtual environment
source venv/bin/activate
```

### "API key not configured"

```bash
# Check .env file exists
cat .env

# Verify environment is loaded
python -c "import os; print(os.getenv('GEMINI_API_KEY'))"
```

### "No quote data for XXX"

1. Check if stock code is correct
2. Market may be closed (A-shares: 9:30-15:00 UTC+8)
3. Try alternative data provider in `.env`

### Slow Analysis

1. Use `--brief` for faster response
2. Check network connection
3. Use local data provider (akshare)
4. Enable caching (default: enabled)

## Android/Termux Setup

For Android devices using Termux:

```bash
# Install dependencies
pkg install python nodejs

# Clone repository
git clone https://github.com/Zhangbu/daily_stock_analysis.git
cd daily_stock_analysis

# Create venv
python -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env

# Test
./dsa-cli quote 600519 --json
```

## Docker Deployment

```bash
# Build image
docker build -t dsa -f docker/Dockerfile .

# Run container
docker run -it --rm \
  -v $(pwd)/.env:/app/.env \
  dsa ./dsa-cli quote 600519 --json
```

## API Alternative

If you prefer HTTP API over CLI:

```bash
# Start API server
python main.py --mode api

# Or use uvicorn
uvicorn api.app:app --host 0.0.0.0 --port 8000

# API calls
curl http://localhost:8000/api/v1/quote/600519
curl -X POST http://localhost:8000/api/v1/analysis/analyze \
  -H "Content-Type: application/json" \
  -d '{"stock_code": "600519"}'
```

OpenClaw can use HTTP requests instead of CLI commands if preferred.

## Resources

- [DSA Repository](https://github.com/Zhangbu/daily_stock_analysis)
- [OpenClaw Repository](https://github.com/nicholasxuu/OpenClaw)
- [API Documentation](./api_spec.json)
- [Full Guide](./full-guide.md)

## Support

For issues or questions:
1. Check [FAQ](./FAQ.md)
2. Open an [Issue](https://github.com/Zhangbu/daily_stock_analysis/issues)
3. Join discussions in the community