#!/bin/bash
set -e

echo "GAR ARC Bot — installer"
echo "========================"

# system deps
echo "[1/4] installing system packages..."
sudo apt-get update -q
sudo apt-get install -y -q python3 python3-pip python3-venv git tesseract-ocr

# clone
echo "[2/4] cloning repo..."
git clone https://github.com/Ljs4426/GAR_ARC_BOT.git
cd GAR_ARC_BOT/discord-bot

# python deps
echo "[3/4] installing python packages..."
pip3 install -r requirements.txt --quiet

# env
echo "[4/4] setting up config..."
cp .env.example .env

echo ""
echo "done. edit your config then start the bot:"
echo ""
echo "  cd GAR_ARC_BOT/discord-bot"
echo "  nano .env"
echo "  python3 main.py"
echo ""
