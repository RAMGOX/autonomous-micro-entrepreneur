# 📱 Telegram Bot & Mini-App Integration (Robinhood EVM MCP)

Bounty Issue #6 Solution
Operator Wallet: `0x02c1F87F514493F359Afc0B3ff6b587434770361`

## Overview
Lightweight Telegram Bot and WebApp Mini-App connecting directly to the EVM MCP server.

### Features
1. **Interactive Commands**: `/start`, `/launch`, `/trust`, `/reserves`, `/portfolio`.
2. **Native WebApp Integration**: Launches the full dark-mode Mini-App inside Telegram via `https://telegram.org/js/telegram-web-app.js`.
3. **Oracle & Staking Hub**: Displays live XAU/XAG gold/silver reserves and lets users deploy meme coins in 1 click.

### Setup Instructions
1. Set environment variables:
   ```env
   TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"
   TELEGRAM_MINI_APP_URL="https://your-domain.com/telegram_webapp.html"
   ```
2. Run the bot:
   ```bash
   python telegram_bot.py
   ```
