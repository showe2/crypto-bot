#!/usr/bin/env bash

set -e  # Exit on first error

# ==============================================
# SOLANA TOKEN ANALYSIS SYSTEM STARTUP SCRIPT
# ==============================================

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

# ==============================================
# CONFIGURATION
# ==============================================

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Virtual environment directory
VENV_DIR=".venv"

# Python executable preference (simplified)
PYTHON_CMD="python"

# Default values
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="8000"
DEFAULT_ENV="development"

# ==============================================
# FUNCTIONS
# ==============================================

# Check if Python is available
check_python() {
    if ! command -v python &> /dev/null; then
        log_error "Python is not installed or not in PATH."
        log_info "Please install Python and make sure it's accessible as 'python'"
        exit 1
    fi
    
    log_success "Python found: $(python --version 2>&1)"
}

# Check system dependencies
check_system_dependencies() {
    log_step "Checking system dependencies..."
    
    # Check for Redis (optional)
    if command -v redis-server &> /dev/null; then
        if pgrep redis-server > /dev/null; then
            log_success "Redis server is running"
        else
            log_warn "Redis server is installed but not running"
            log_info "You can start it with: redis-server"
        fi
    else
        log_warn "Redis server not found (optional for caching)"
        log_info "Install with: sudo apt-get install redis-server (Ubuntu/Debian)"
        log_info "           or: brew install redis (macOS)"
    fi
    
    # Check for Git (for development)
    if command -v git &> /dev/null; then
        log_success "Git is available"
    else
        log_warn "Git not found (recommended for development)"
    fi
}

# Create and activate virtual environment
setup_virtual_environment() {
    log_step "Setting up virtual environment..."
    
    if [ ! -d "$VENV_DIR" ]; then
        log_info "Creating virtual environment with python..."
        python -m venv "$VENV_DIR"
        log_success "Virtual environment created"
    else
        log_info "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    log_info "Activating virtual environment..."
    
    # Detect OS and activate accordingly
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        # Windows/Git Bash
        source "$VENV_DIR/Scripts/activate"
    else
        # Unix-like systems
        source "$VENV_DIR/bin/activate"
    fi
    
    # Verify activation
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        log_success "Virtual environment activated: $VIRTUAL_ENV"
    else
        log_error "Failed to activate virtual environment"
        exit 1
    fi
    
    # Upgrade pip
    log_info "Upgrading pip..."
    python -m pip install --upgrade pip
}

# Install dependencies
install_dependencies() {
    log_step "Installing Python dependencies..."
    
    if [ ! -f "requirements.txt" ]; then
        log_error "requirements.txt not found!"
        exit 1
    fi
    
    # Install basic requirements first
    log_info "Installing core dependencies..."
    pip install -r requirements.txt
    
    # Check and install optional dependencies
    log_info "Checking optional dependencies..."
    
    # Check ChromaDB
    if python -c "import chromadb, sentence_transformers" 2>/dev/null; then
        log_success "ChromaDB already installed"
    else
        log_info "ChromaDB not found, installing..."
        
        # Try different installation methods
        if install_chromadb; then
            log_success "ChromaDB installed successfully"
        else
            log_warn "ChromaDB installation failed - continuing without it"
        fi
    fi
    
    # Check Redis
    if python -c "import redis" 2>/dev/null; then
        log_success "Redis client already installed"
    else
        log_info "Installing Redis client..."
        pip install redis
    fi
    
    log_success "Dependencies installation completed"
    
    # Optional: Install development dependencies
    if [ -f "requirements-dev.txt" ]; then
        read -p "Install development dependencies? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Installing development dependencies..."
            pip install -r requirements-dev.txt
        fi
    fi
}

# Function to install ChromaDB with multiple fallback methods
install_chromadb() {
    log_info "Attempting ChromaDB installation..."
    
    # Method 1: Try standard installation
    log_info "Method 1: Standard installation..."
    if pip install chromadb==0.5.23 sentence-transformers==2.7.0 2>/dev/null; then
        if python -c "import chromadb, sentence_transformers" 2>/dev/null; then
            log_success "Standard installation successful"
            return 0
        fi
    fi
    
    # Method 2: Try with pre-compiled wheels only
    log_info "Method 2: Pre-compiled wheels only..."
    if pip install --only-binary=all chromadb sentence-transformers 2>/dev/null; then
        if python -c "import chromadb, sentence_transformers" 2>/dev/null; then
            log_success "Pre-compiled wheels installation successful"
            return 0
        fi
    fi
    
    # Method 3: Install dependencies separately
    log_info "Method 3: Installing dependencies separately..."
    
    # Install torch first (CPU version for compatibility)
    if pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu 2>/dev/null; then
        log_info "PyTorch installed"
    fi
    
    # Install other dependencies
    pip install numpy pandas requests 2>/dev/null
    pip install onnxruntime 2>/dev/null
    
    # Try ChromaDB again
    if pip install chromadb sentence-transformers 2>/dev/null; then
        if python -c "import chromadb, sentence_transformers" 2>/dev/null; then
            log_success "Separate dependencies installation successful"
            return 0
        fi
    fi
    
    # Method 4: Try lighter version
    log_info "Method 4: Trying lighter ChromaDB installation..."
    if pip install chromadb[default] 2>/dev/null; then
        if python -c "import chromadb" 2>/dev/null; then
            log_info "Light ChromaDB installed, installing sentence-transformers..."
            if pip install sentence-transformers 2>/dev/null; then
                log_success "Light installation successful"
                return 0
            fi
        fi
    fi
    
    log_warn "All ChromaDB installation methods failed"
    log_info "ChromaDB will be disabled - system will work without vector storage"
    return 1
}

# Setup environment file
setup_environment_file() {
    log_step "Setting up environment configuration..."
    
    if [ -f ".env.example" ] && [ ! -f ".env" ]; then
        log_info "Creating .env from .env.example..."
        cp .env.example .env
        log_success ".env file created"
        log_warn "Please edit .env file with your API keys and configuration"
        log_info "Important settings to configure:"
        log_info "  - HELIUS_API_KEY: Solana RPC provider"
        log_info "  - REDIS_URL: Redis connection string"
        log_info "  - LOG_LEVEL: Logging level (DEBUG/INFO/WARNING/ERROR)"
        log_info "  - AI model API keys: MISTRAL_API_KEY, LLAMA_API_KEY"
    elif [ -f ".env" ]; then
        log_success ".env file already exists"
    else
        log_warn "No .env.example file found - you may need to create .env manually"
    fi
}

# Create required directories
create_directories() {
    log_step "Creating required directories..."
    
    # Read directories from .env or use defaults
    if [ -f ".env" ]; then
        source .env
    fi
    
    # Directory list with defaults
    DIRS=(
        "${CHROMA_DB_PATH:-./shared_data/chroma}"
        "${KNOWLEDGE_BASE_PATH:-./shared_data/knowledge_base}"
        "${LOGS_DIR:-./shared_data/logs}"
        "./shared_data/cache"
        "./shared_data/temp"
    )
    
    for dir in "${DIRS[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log_info "Created directory: $dir"
        fi
    done
    
    log_success "All required directories are ready"
}

# Health check
run_health_check() {
    log_step "Running system health check..."
    
    # Load environment variables
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi
    
    # Check if we can import main modules
    python -c "
import sys
sys.path.append('.')

try:
    from app.core.config import get_settings
    from app.core.logging import setup_logging
    print('✅ Core modules can be imported')
    
    # Test configuration
    settings = get_settings()
    print(f'✅ Configuration loaded (ENV: {settings.ENV})')
    
    # Test logging setup
    setup_logging()
    print('✅ Logging system initialized')
    
except Exception as e:
    print(f'❌ Health check failed: {e}')
    sys.exit(1)
" || {
        log_error "Health check failed!"
        exit 1
    }
    
    # Check optional dependencies
    log_info "Checking optional dependencies..."
    
    # Check ChromaDB
    python -c "
try:
    import chromadb
    import sentence_transformers
    print('✅ ChromaDB: Available')
except ImportError:
    print('⚠️  ChromaDB: Not available (optional)')
"
    
    # Check Redis client
    python -c "
try:
    import redis
    print('✅ Redis client: Available')
except ImportError:
    print('⚠️  Redis client: Not available (optional)')
"
    
    # Test app imports
    python -c "
try:
    from app.utils.redis_client import check_redis_health
    from app.utils.cache import get_cache_health
    from app.utils.chroma_client import check_chroma_health
    print('✅ Utils modules: Available')
except ImportError as e:
    print(f'⚠️  Some utils modules not available: {e}')
"
    
    log_success "Health check passed"
}

# Load environment variables and get runtime configuration
load_runtime_config() {
    # Load environment variables from .env
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi
    
    # Set runtime variables with fallbacks
    HOST="${HOST:-$DEFAULT_HOST}"
    PORT="${PORT:-$DEFAULT_PORT}"
    ENV="${ENV:-$DEFAULT_ENV}"
    
    log_info "Runtime configuration:"
    log_info "  Environment: $ENV"
    log_info "  Host: $HOST"
    log_info "  Port: $PORT"
    log_info "  Debug: ${DEBUG:-false}"
}

# Start the application
start_application() {
    log_step "Starting Solana Token Analysis System..."
    
    # Build the uvicorn command
    UVICORN_CMD="uvicorn app.main:app --host $HOST --port $PORT"
    
    # Add development-specific options
    if [ "$ENV" = "development" ]; then
        UVICORN_CMD="$UVICORN_CMD --reload --log-level debug"
        log_info "Development mode: auto-reload enabled"
    else
        UVICORN_CMD="$UVICORN_CMD --log-level info"
    fi
    
    # Add workers for production
    if [ "$ENV" = "production" ]; then
        WORKERS="${WORKERS:-4}"
        UVICORN_CMD="$UVICORN_CMD --workers $WORKERS"
        log_info "Production mode: using $WORKERS workers"
    fi
    
    log_success "🚀 Starting server on http://$HOST:$PORT"
    log_info "API documentation: http://$HOST:$PORT/docs"
    log_info "System status: http://$HOST:$PORT/health"
    log_info ""
    log_info "Press Ctrl+C to stop the server"
    log_info ""
    
    # Execute the command
    exec $UVICORN_CMD
}

# ==============================================
# MAIN EXECUTION
# ==============================================

main() {
    echo -e "${PURPLE}"
    echo "==============================================="
    echo "  SOLANA TOKEN ANALYSIS AI SYSTEM"
    echo "==============================================="
    echo -e "${NC}"
    
    # Debug information for troubleshooting
    log_info "System information:"
    log_info "  OS: $OSTYPE"
    log_info "  Shell: $SHELL"
    log_info "  Working directory: $(pwd)"
    
    # Check if help was requested
    if [[ "$1" == "--help" || "$1" == "-h" ]]; then
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h         Show this help message"
        echo "  --check-only       Run health check only"
        echo "  --install-only     Install dependencies only"
        echo "  --install-chromadb Force ChromaDB installation"
        echo "  --debug            Enable debug output"
        echo ""
        echo "Environment variables:"
        echo "  HOST          Server host (default: $DEFAULT_HOST)"
        echo "  PORT          Server port (default: $DEFAULT_PORT)"
        echo "  ENV           Environment mode (default: $DEFAULT_ENV)"
        echo ""
        exit 0
    fi
    
    # Force ChromaDB installation if requested
    if [[ "$1" == "--install-chromadb" || "$2" == "--install-chromadb" ]]; then
        log_step "Force installing ChromaDB..."
        
        # Check if virtual environment exists
        if [ ! -d "$VENV_DIR" ]; then
            log_error "Virtual environment not found. Run ./start.sh first"
            exit 1
        fi
        
        # Activate virtual environment
        if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
            source "$VENV_DIR/Scripts/activate"
        else
            source "$VENV_DIR/bin/activate"
        fi
        
        # Make install script executable and run it
        chmod +x install_chromadb.sh 2>/dev/null || true
        if [ -f "install_chromadb.sh" ]; then
            ./install_chromadb.sh
        else
            # Fallback to inline installation
            log_info "Using inline ChromaDB installation..."
            if install_chromadb; then
                log_success "ChromaDB installation completed!"
            else
                log_error "ChromaDB installation failed"
                exit 1
            fi
        fi
        exit 0
    fi
    
    # Enable debug mode if requested
    if [[ "$1" == "--debug" || "$2" == "--debug" ]]; then
        set -x
        log_info "Debug mode enabled"
    fi
    
    # Step 1: Check Python
    check_python
    
    # Step 2: Check system dependencies
    check_system_dependencies
    
    # Step 3: Setup virtual environment
    setup_virtual_environment
    
    # Step 4: Install dependencies
    if [[ "$1" != "--check-only" ]]; then
        install_dependencies
    fi
    
    # Step 5: Setup environment
    setup_environment_file
    
    # Step 6: Create directories
    create_directories
    
    # Step 7: Run health check
    run_health_check
    
    # Exit if only checking
    if [[ "$1" == "--check-only" ]]; then
        log_success "System check completed successfully!"
        exit 0
    fi
    
    # Exit if only installing
    if [[ "$1" == "--install-only" ]]; then
        log_success "Installation completed successfully!"
        exit 0
    fi
    
    # Step 8: Load runtime configuration
    load_runtime_config
    
    # Step 9: Start the application
    start_application
}

# Handle script interruption
trap 'echo -e "\n${YELLOW}Shutting down...${NC}"; exit 0' INT TERM

# Run main function
main "$@"