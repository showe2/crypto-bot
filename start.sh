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

# Python executable preference
PYTHON_CMD="python"

# Default values
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="8000"
DEFAULT_ENV="development"

# ChromaDB version compatibility matrix
CHROMADB_VERSION="0.4.24"
SENTENCE_TRANSFORMERS_VERSION="2.7.0"

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

# Check if ChromaDB is already properly installed
check_chromadb_installed() {
    log_info "Checking existing ChromaDB installation..."
    
    if python -c "
import chromadb
import sentence_transformers
print(f'ChromaDB version: {chromadb.__version__}')
print(f'SentenceTransformers version: {sentence_transformers.__version__}')

# Test basic functionality
client = chromadb.Client()
collection = client.create_collection('test_collection_$(date +%s)')
collection.add(documents=['test'], ids=['test_id'])
results = collection.query(query_texts=['test'], n_results=1)
client.delete_collection('test_collection_$(date +%s)')
print('✅ ChromaDB functionality test passed')
" 2>/dev/null; then
        log_success "ChromaDB is already properly installed and working"
        return 0
    else
        log_info "ChromaDB needs to be installed or is not working properly"
        return 1
    fi
}

# Install ChromaDB
install_chromadb() {
    log_step "Installing ChromaDB..."
    
    # First check if it's already working
    if check_chromadb_installed; then
        return 0
    fi
    
    # Clean any existing broken installations
    log_info "Cleaning any existing ChromaDB installations..."
    pip uninstall -y chromadb sentence-transformers 2>/dev/null || true
    
    # Detect system architecture and Python version for optimal installation
    PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    ARCHITECTURE=$(python -c "import platform; print(platform.machine())")
    
    log_info "System info: Python $PYTHON_VERSION, Architecture: $ARCHITECTURE"
    
    # Install system-specific optimized packages
    log_info "Installing ChromaDB with compatible dependencies..."
    
    # Step 1: Install core dependencies that ChromaDB needs
    log_info "Installing core dependencies..."
    pip install --no-cache-dir \
        numpy>=1.21.0 \
        pandas>=1.3.0 \
        requests>=2.28.0 \
        pyyaml>=6.0 \
        overrides>=7.4.0 \
        importlib-metadata>=6.0.0 \
        typing-extensions>=4.5.0
    
    # Step 2: Install PyTorch with CPU-only for better compatibility
    log_info "Installing PyTorch (CPU version for compatibility)..."
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    
    # Step 3: Install sentence-transformers first (it's a ChromaDB dependency)
    log_info "Installing sentence-transformers..."
    pip install --no-cache-dir sentence-transformers==$SENTENCE_TRANSFORMERS_VERSION
    
    # Step 4: Install ChromaDB with specific version
    log_info "Installing ChromaDB..."
    pip install --no-cache-dir chromadb==$CHROMADB_VERSION
    
    # Step 5: Verify installation
    log_info "Verifying ChromaDB installation..."
    if python -c "
import chromadb
import sentence_transformers
print(f'✅ ChromaDB {chromadb.__version__} installed successfully')
print(f'✅ SentenceTransformers {sentence_transformers.__version__} installed successfully')

# Test basic functionality
try:
    client = chromadb.Client()
    test_collection_name = f'test_collection_{int(__import__(\"time\").time())}'
    collection = client.create_collection(test_collection_name)
    collection.add(documents=['test document'], ids=['test_id'])
    results = collection.query(query_texts=['test'], n_results=1)
    
    # Cleanup
    try:
        client.delete_collection(test_collection_name)
    except:
        pass
        
    print('✅ ChromaDB functionality test passed')
    exit(0)
except Exception as e:
    print(f'❌ ChromaDB test failed: {e}')
    exit(1)
" 2>/dev/null; then
        log_success "ChromaDB installation completed and verified!"
        return 0
    else
        log_error "ChromaDB installation failed verification"
        log_warn "ChromaDB will be disabled - system will work without vector storage"
        return 1
    fi
}

# Install dependencies with optimized ChromaDB handling
install_dependencies() {
    log_step "Installing Python dependencies..."
    
    if [ ! -f "requirements.txt" ]; then
        log_error "requirements.txt not found!"
        exit 1
    fi
    
    # Install base requirements first (excluding ChromaDB and sentence-transformers)
    log_info "Installing core dependencies from requirements.txt..."
    
    # Create temporary requirements file without ChromaDB
    grep -v -E "(chromadb|sentence-transformers)" requirements.txt > /tmp/requirements_base.txt
    pip install --no-cache-dir -r /tmp/requirements_base.txt
    rm -f /tmp/requirements_base.txt
    
    # Install Redis client
    log_info "Installing Redis client..."
    pip install --no-cache-dir redis
    
    # Install ChromaDB with our optimized method
    if install_chromadb; then
        log_success "ChromaDB installed successfully"
    else
        log_warn "ChromaDB installation failed - continuing without it"
        log_info "The system will work with basic functionality"
    fi
    
    log_success "Dependencies installation completed"
    
    # Optional: Install development dependencies
    if [ -f "requirements-dev.txt" ]; then
        read -p "Install development dependencies? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Installing development dependencies..."
            pip install --no-cache-dir -r requirements-dev.txt
        fi
    fi
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
    
    # Check dependencies
    log_info "Checking dependencies status..."
    
    # Check ChromaDB
    if python -c "
try:
    import chromadb
    import sentence_transformers
    
    # Test functionality
    client = chromadb.Client()
    print(f'✅ ChromaDB {chromadb.__version__}: Fully functional')
except ImportError as e:
    print(f'⚠️  ChromaDB: Not available - {e}')
except Exception as e:
    print(f'⚠️  ChromaDB: Available but not functional - {e}')
" 2>/dev/null; then
        true  # ChromaDB status already printed
    else
        log_warn "ChromaDB check failed"
    fi
    
    # Check Redis client
    python -c "
try:
    import redis
    print('✅ Redis client: Available')
except ImportError:
    print('⚠️  Redis client: Not available')
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
    
    log_success "Health check completed"
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
    log_info "  ChromaDB target version: $CHROMADB_VERSION"
    log_info "  SentenceTransformers target version: $SENTENCE_TRANSFORMERS_VERSION"
    
    # Check if help was requested
    if [[ "$1" == "--help" || "$1" == "-h" ]]; then
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h             Show this help message"
        echo "  --check-only           Run health check only"
        echo "  --install-only         Install dependencies only"
        echo "  --reinstall-chromadb   Force reinstall ChromaDB"
        echo "  --skip-chromadb        Skip ChromaDB installation"
        echo "  --debug                Enable debug output"
        echo ""
        echo "Environment variables:"
        echo "  HOST          Server host (default: $DEFAULT_HOST)"
        echo "  PORT          Server port (default: $DEFAULT_PORT)"
        echo "  ENV           Environment mode (default: $DEFAULT_ENV)"
        echo ""
        exit 0
    fi
    
    # Handle ChromaDB reinstallation
    if [[ "$1" == "--reinstall-chromadb" || "$2" == "--reinstall-chromadb" ]]; then
        log_step "Force reinstalling ChromaDB..."
        
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
        
        # Force reinstall ChromaDB
        log_info "Uninstalling existing ChromaDB..."
        pip uninstall -y chromadb sentence-transformers 2>/dev/null || true
        
        if install_chromadb; then
            log_success "ChromaDB reinstallation completed!"
        else
            log_error "ChromaDB reinstallation failed"
            exit 1
        fi
        exit 0
    fi
    
    # Check for skip ChromaDB flag
    SKIP_CHROMADB=false
    if [[ "$1" == "--skip-chromadb" || "$2" == "--skip-chromadb" ]]; then
        SKIP_CHROMADB=true
        log_info "Skipping ChromaDB installation as requested"
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
        if [ "$SKIP_CHROMADB" = true ]; then
            # Install dependencies without ChromaDB
            log_info "Installing dependencies without ChromaDB..."
            grep -v -E "(chromadb|sentence-transformers)" requirements.txt > /tmp/requirements_no_chromadb.txt
            pip install --no-cache-dir -r /tmp/requirements_no_chromadb.txt
            pip install --no-cache-dir redis
            rm -f /tmp/requirements_no_chromadb.txt
        else
            install_dependencies
        fi
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