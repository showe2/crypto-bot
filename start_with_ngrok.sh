#!/usr/bin/env bash

set -e  # Exit on first error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Configuration
PORT="${PORT:-8000}"
NGROK_CONFIG_FILE=".ngrok.yml"
NGROK_LOG_FILE="ngrok.log"

# ==============================================
# FUNCTIONS
# ==============================================

check_ngrok() {
    if ! command -v ngrok &> /dev/null; then
        log_error "ngrok is not installed!"
        log_info "Install ngrok:"
        log_info "  macOS: brew install ngrok"
        log_info "  Windows: choco install ngrok"
        log_info "  Linux: https://ngrok.com/download"
        exit 1
    fi
    
    log_success "ngrok found: $(ngrok version | head -n1)"
}

check_ngrok_auth() {
    # Check if authtoken is configured
    if ! ngrok config check &> /dev/null; then
        log_warn "ngrok authtoken not configured"
        log_info "Get your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken"
        log_info "Then run: ngrok config add-authtoken YOUR_TOKEN"
        
        read -p "Do you want to continue without auth? (free tier has limits) [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_success "ngrok authtoken configured"
    fi
}

create_ngrok_config() {
    log_step "Creating ngrok configuration..."
    
    cat > "$NGROK_CONFIG_FILE" << EOF
version: "2"
authtoken_from_env: true
tunnels:
  webhook-dev:
    addr: $PORT
    proto: http
    hostname: 
    bind_tls: true
    inspect: true
    schemes:
      - https
      - http
log_level: info
log_format: json
log: $NGROK_LOG_FILE
EOF
    
    log_success "ngrok config created: $NGROK_CONFIG_FILE"
}

start_ngrok() {
    log_step "Starting ngrok tunnel..."
    
    # Kill any existing ngrok processes
    pkill -f ngrok || true
    sleep 2
    
    # Start ngrok in background
    if [ -f "$NGROK_CONFIG_FILE" ]; then
        ngrok start webhook-dev --config="$NGROK_CONFIG_FILE" > /dev/null 2>&1 &
    else
        ngrok http $PORT > /dev/null 2>&1 &
    fi
    
    NGROK_PID=$!
    log_info "ngrok started with PID: $NGROK_PID"
    
    # Wait for ngrok to start
    log_info "Waiting for ngrok to initialize..."
    sleep 5
    
    # Get the public URL
    get_ngrok_url
}

get_ngrok_url() {
    log_step "Getting ngrok public URL..."
    
    # Try to get URL from ngrok API
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        log_info "Attempt $attempt/$max_attempts to get ngrok URL..."
        
        if NGROK_URL=$(curl -s localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for tunnel in data.get('tunnels', []):
        if tunnel.get('proto') == 'https':
            print(tunnel['public_url'])
            break
except:
    pass
" 2>/dev/null); then
            if [ ! -z "$NGROK_URL" ] && [ "$NGROK_URL" != "null" ]; then
                log_success "ngrok URL obtained: $NGROK_URL"
                export NGROK_URL
                return 0
            fi
        fi
        
        sleep 2
        ((attempt++))
    done
    
    log_error "Failed to get ngrok URL!"
    log_info "Check ngrok status manually: curl localhost:4040/api/tunnels"
    return 1
}

update_env_file() {
    log_step "Updating .env file with ngrok URL..."
    
    if [ -z "$NGROK_URL" ]; then
        log_error "No ngrok URL to update"
        return 1
    fi
    
    # Backup original .env
    if [ -f ".env" ]; then
        cp .env .env.backup
        log_info "Backed up .env to .env.backup"
    fi
    
    # Update WEBHOOK_BASE_URL
    if [ -f ".env" ]; then
        # Remove existing WEBHOOK_BASE_URL line
        grep -v "^WEBHOOK_BASE_URL=" .env > .env.tmp || true
        mv .env.tmp .env
    else
        touch .env
    fi
    
    # Add new WEBHOOK_BASE_URL
    echo "WEBHOOK_BASE_URL=$NGROK_URL" >> .env
    
    # Add webhook secret if not exists
    if ! grep -q "^HELIUS_WEBHOOK_SECRET=" .env; then
        echo "HELIUS_WEBHOOK_SECRET=dev_webhook_secret_$(date +%s)" >> .env
        log_info "Added new HELIUS_WEBHOOK_SECRET to .env"
    fi
    
    log_success ".env updated with ngrok URL"
}

show_webhook_urls() {
    if [ -z "$NGROK_URL" ]; then
        log_error "No ngrok URL available"
        return 1
    fi
    
    log_success "🎉 Setup Complete!"
    echo ""
    echo -e "${PURPLE}================================================${NC}"
    echo -e "${PURPLE}           WEBHOOK DEVELOPMENT URLS${NC}"
    echo -e "${PURPLE}================================================${NC}"
    echo ""
    echo -e "${CYAN}📦 Mint WebHook:${NC}"
    echo -e "   $NGROK_URL/webhooks/helius/mint"
    echo ""
    echo -e "${CYAN}🏊 Pool WebHook:${NC}"
    echo -e "   $NGROK_URL/webhooks/helius/pool"
    echo ""
    echo -e "${CYAN}💸 Transaction WebHook:${NC}"
    echo -e "   $NGROK_URL/webhooks/helius/tx"
    echo ""
    echo -e "${CYAN}📊 Status & Monitoring:${NC}"
    echo -e "   $NGROK_URL/webhooks/status"
    echo -e "   $NGROK_URL/webhooks/health"
    echo -e "   $NGROK_URL/webhooks/queue/stats"
    echo ""
    echo -e "${CYAN}📖 API Documentation:${NC}"
    echo -e "   $NGROK_URL/docs"
    echo ""
    echo -e "${YELLOW}🔧 Configuration:${NC}"
    echo -e "   WEBHOOK_BASE_URL: $NGROK_URL"
    echo -e "   Local server: http://localhost:$PORT"
    echo -e "   ngrok inspector: http://localhost:4040"
    echo ""
    echo -e "${PURPLE}================================================${NC}"
    echo ""
    echo -e "${GREEN}Copy these URLs to your Helius Dashboard!${NC}"
    echo ""
}

start_application() {
    log_step "Starting application..."
    
    # Source the updated .env file
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
    fi
    
    log_info "Starting server on port $PORT..."
    
    # Check if start.sh exists
    if [ -f "start.sh" ]; then
        chmod +x start.sh
        exec ./start.sh
    else
        # Fallback to direct uvicorn
        exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --reload
    fi
}

cleanup() {
    log_info "Cleaning up..."
    
    # Kill ngrok
    if [ ! -z "$NGROK_PID" ]; then
        kill $NGROK_PID 2>/dev/null || true
    fi
    pkill -f ngrok || true
    
    # Restore original .env if needed
    if [ -f ".env.backup" ]; then
        log_info "Restore original .env? [y/N]"
        read -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            mv .env.backup .env
            log_info "Original .env restored"
        fi
    fi
    
    log_info "Cleanup complete"
}

# ==============================================
# MAIN EXECUTION
# ==============================================

main() {
    echo -e "${PURPLE}"
    echo "==============================================="
    echo "    SOLANA TOKEN ANALYSIS + NGROK SETUP"
    echo "==============================================="
    echo -e "${NC}"
    
    # Handle help
    if [[ "$1" == "--help" || "$1" == "-h" ]]; then
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h         Show this help"
        echo "  --port PORT        Specify port (default: 8000)"
        echo "  --config-only      Only create ngrok config"
        echo ""
        echo "Environment variables:"
        echo "  PORT              Server port (default: 8000)"
        echo ""
        exit 0
    fi
    
    # Handle port option
    if [[ "$1" == "--port" && ! -z "$2" ]]; then
        PORT="$2"
        shift 2
    fi
    
    # Set trap for cleanup
    trap cleanup EXIT INT TERM
    
    log_info "Port: $PORT"
    
    # Step 1: Check ngrok
    check_ngrok
    
    # Step 2: Check ngrok auth
    check_ngrok_auth
    
    # Step 3: Create ngrok config
    create_ngrok_config
    
    # Exit early if only config
    if [[ "$1" == "--config-only" ]]; then
        log_success "ngrok configuration created"
        exit 0
    fi
    
    # Step 4: Start ngrok
    start_ngrok
    
    # Step 5: Update .env
    update_env_file
    
    # Step 6: Show URLs
    show_webhook_urls
    
    # Step 7: Start application
    echo -e "${YELLOW}Press Enter to start the application...${NC}"
    read
    
    start_application
}

# Run main
main "$@"