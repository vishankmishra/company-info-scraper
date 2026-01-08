#!/bin/bash

# VM Deployment Script for Company Info Scraper
# This script automates the setup process on a fresh VM

set -e  # Exit on error

echo "=========================================="
echo "Company Info Scraper - VM Deployment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/company-scraper"
APP_USER="scraper"
OLLAMA_USER="ollama"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${GREEN}Step 1: Updating system packages...${NC}"
apt update && apt upgrade -y

echo -e "${GREEN}Step 2: Installing system dependencies...${NC}"
apt install -y python3 python3-pip python3-venv git curl wget

echo -e "${GREEN}Step 3: Installing Playwright system dependencies...${NC}"
apt install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libasound2 libpango-1.0-0 libatk-1.0-0 libcairo-gobject2 \
  libgtk-3-0 libgdk-pixbuf2.0-0

echo -e "${GREEN}Step 4: Installing Ollama...${NC}"
curl https://ollama.ai/install.sh | sh

echo -e "${GREEN}Step 5: Creating application user...${NC}"
useradd -r -s /bin/bash -d $APP_DIR $APP_USER || echo "User $APP_USER already exists"

echo -e "${GREEN}Step 6: Setting up application directory...${NC}"
mkdir -p $APP_DIR
chown $APP_USER:$APP_USER $APP_DIR

# Copy project files (assuming script is run from project root)
if [ -f "main.py" ]; then
    echo -e "${GREEN}Copying project files...${NC}"
    cp -r . $APP_DIR/
    chown -R $APP_USER:$APP_USER $APP_DIR
else
    echo -e "${YELLOW}Warning: Project files not found. Please copy them manually to $APP_DIR${NC}"
fi

echo -e "${GREEN}Step 7: Setting up Python environment...${NC}"
cd $APP_DIR
sudo -u $APP_USER python3 -m venv venv
sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip
sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r requirements.txt

echo -e "${GREEN}Step 8: Installing Playwright browsers...${NC}"
sudo -u $APP_USER $APP_DIR/venv/bin/playwright install

echo -e "${GREEN}Step 9: Creating necessary directories...${NC}"
sudo -u $APP_USER mkdir -p $APP_DIR/logs $APP_DIR/data $APP_DIR/output

echo -e "${GREEN}Step 10: Pulling Ollama model...${NC}"
ollama pull llama3 || echo -e "${YELLOW}Warning: Could not pull llama3 model. Run 'ollama pull llama3' manually.${NC}"

echo -e "${GREEN}Step 11: Creating systemd service files...${NC}"

# Ollama service
cat > /etc/systemd/system/ollama.service << EOF
[Unit]
Description=Ollama Service
After=network.target

[Service]
Type=simple
User=$OLLAMA_USER
Group=$OLLAMA_USER
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Scraper service
cat > /etc/systemd/system/company-scraper.service << EOF
[Unit]
Description=Company Info Scraper Service
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStartPre=/bin/bash -c '$APP_DIR/venv/bin/python -c "import ollama; ollama.list()" || exit 1'
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/main.py --batch $APP_DIR/data/domains.txt
Restart=always
RestartSec=10
StandardOutput=append:$APP_DIR/logs/service.log
StandardError=append:$APP_DIR/logs/service.error.log

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}Step 12: Setting up log rotation...${NC}"
cat > /etc/logrotate.d/company-scraper << EOF
$APP_DIR/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $APP_USER $APP_USER
}
EOF

echo -e "${GREEN}Step 13: Creating monitoring scripts...${NC}"

# Health check script
cat > $APP_DIR/health_check.sh << 'HEALTH_EOF'
#!/bin/bash
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "ERROR: Ollama not responding"
    exit 1
fi
if ! systemctl is-active --quiet company-scraper.service; then
    echo "ERROR: Scraper service not running"
    exit 1
fi
echo "Health check passed"
exit 0
HEALTH_EOF

chmod +x $APP_DIR/health_check.sh
chown $APP_USER:$APP_USER $APP_DIR/health_check.sh

echo -e "${GREEN}Step 14: Enabling and starting services...${NC}"
systemctl daemon-reload
systemctl enable ollama.service
systemctl start ollama.service
sleep 5  # Wait for Ollama to start

# Create sample domains file if it doesn't exist
if [ ! -f "$APP_DIR/data/domains.txt" ]; then
    echo "# Add domains here, one per line" > $APP_DIR/data/domains.txt
    chown $APP_USER:$APP_USER $APP_DIR/data/domains.txt
fi

echo -e "${GREEN}Step 15: Verifying installation...${NC}"
if systemctl is-active --quiet ollama.service; then
    echo -e "${GREEN}✓ Ollama service is running${NC}"
else
    echo -e "${RED}✗ Ollama service failed to start${NC}"
fi

if [ -f "$APP_DIR/main.py" ]; then
    echo -e "${GREEN}✓ Application files found${NC}"
else
    echo -e "${YELLOW}⚠ Application files not found. Please copy them to $APP_DIR${NC}"
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Deployment completed!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Add domains to: $APP_DIR/data/domains.txt"
echo "2. Configure settings in: $APP_DIR/config.yaml"
echo "3. Start the scraper service:"
echo "   sudo systemctl start company-scraper.service"
echo "4. Check status:"
echo "   sudo systemctl status company-scraper.service"
echo "5. View logs:"
echo "   sudo journalctl -u company-scraper.service -f"
echo ""
echo "To enable auto-start on boot:"
echo "   sudo systemctl enable company-scraper.service"
echo ""

