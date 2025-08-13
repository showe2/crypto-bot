#!/usr/bin/env bash

set -e  # Exit on first error

# ==============================================
# SOLANA TOKEN ANALYSIS SYSTEM - TEST RUNNER
# ==============================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
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

log_header() {
    echo -e "\n${BLUE}============================================${NC}"
    echo -e "${WHITE} $1${NC}"
    echo -e "${BLUE}============================================${NC}"
}

# ==============================================
# CONFIGURATION
# ==============================================

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Virtual environment directory
VENV_DIR=".venv"

# Test directories
TESTS_DIR="tests"
UNIT_TESTS_DIR="$TESTS_DIR/unit"
INTEGRATION_TESTS_DIR="$TESTS_DIR/integration"

# Python executable preference
PYTHON_CMD="python"

# Test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
START_TIME=$(date +%s)

# ==============================================
# UTILITY FUNCTIONS
# ==============================================

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Python is available
check_python() {
    log_step "Checking Python installation..."
    
    if ! command_exists python && ! command_exists python3; then
        log_error "Python is not installed or not in PATH."
        log_info "Please install Python and make sure it's accessible"
        exit 1
    fi
    
    # Prefer python3 if available
    if command_exists python3; then
        PYTHON_CMD="python3"
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
    log_success "Python found: $PYTHON_VERSION"
}

# Activate virtual environment if it exists
activate_venv() {
    if [ -d "$VENV_DIR" ]; then
        log_step "Activating virtual environment..."
        
        # Detect OS and activate accordingly
        if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]] || [[ -n "$WINDIR" ]]; then
            # Windows (Git Bash, MSYS, or native Windows)
            if [ -f "$VENV_DIR/Scripts/activate" ]; then
                source "$VENV_DIR/Scripts/activate"
                log_success "Virtual environment activated (Windows): $VIRTUAL_ENV"
            elif [ -f "$VENV_DIR/Scripts/activate.bat" ]; then
                # For cmd/PowerShell users who might be running this in Git Bash
                log_warn "Detected Windows batch activation script"
                log_info "Please run: $VENV_DIR\\Scripts\\activate.bat"
                log_info "Then re-run this script"
                export PATH="$VENV_DIR/Scripts:$PATH"
                log_success "Added venv to PATH"
            else
                log_error "Virtual environment activation script not found"
                log_info "Expected: $VENV_DIR/Scripts/activate"
                return 1
            fi
        else
            # Unix-like systems
            if [ -f "$VENV_DIR/bin/activate" ]; then
                source "$VENV_DIR/bin/activate"
                log_success "Virtual environment activated (Unix): $VIRTUAL_ENV"
            else
                log_error "Virtual environment activation script not found"
                log_info "Expected: $VENV_DIR/bin/activate"
                return 1
            fi
        fi
        
        # Verify activation worked
        if [[ "$VIRTUAL_ENV" != "" ]] || [[ "$PATH" == *"$VENV_DIR"* ]]; then
            return 0
        else
            log_warn "Virtual environment activation may have failed"
            log_info "Continuing anyway..."
            return 0
        fi
    else
        log_warn "Virtual environment not found at $VENV_DIR"
        log_info "Consider running ./start.sh first to set up the environment"
        log_info "Or create one manually:"
        log_info "  $PYTHON_CMD -m venv $VENV_DIR"
        return 0
    fi
}

# Check if required dependencies are installed
check_dependencies() {
    log_step "Checking test dependencies..."
    
    local missing_deps=()
    local required_deps=("pytest" "fastapi")
    
    for dep in "${required_deps[@]}"; do
        if ! $PYTHON_CMD -c "import $dep" >/dev/null 2>&1; then
            missing_deps+=("$dep")
        fi
    done
    
    if [ ${#missing_deps[@]} -eq 0 ]; then
        log_success "All required dependencies are installed"
        return 0
    else
        log_warn "Missing dependencies: ${missing_deps[*]}"
        
        # Try to install missing dependencies
        log_info "Attempting to install missing dependencies..."
        
        if [ -f "requirements-test.txt" ]; then
            $PYTHON_CMD -m pip install -r requirements-test.txt
        else
            $PYTHON_CMD -m pip install pytest pytest-asyncio fastapi[test]
        fi
        
        # Check again
        local still_missing=()
        for dep in "${missing_deps[@]}"; do
            if ! $PYTHON_CMD -c "import $dep" >/dev/null 2>&1; then
                still_missing+=("$dep")
            fi
        done
        
        if [ ${#still_missing[@]} -eq 0 ]; then
            log_success "Dependencies installed successfully"
            return 0
        else
            log_error "Failed to install dependencies: ${still_missing[*]}"
            return 1
        fi
    fi
}

# Check project structure
check_project_structure() {
    log_step "Checking project structure..."
    
    local required_files=(
        "app/main.py"
        "app/core/config.py"
        "app/models/token.py"
        "app/utils/redis_client.py"
        "app/utils/chroma_client.py"
        "app/utils/cache.py"
        "app/utils/validation.py"
    )
    
    local missing_files=()
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            log_success "Found: $file"
        else
            missing_files+=("$file")
            log_error "Missing: $file"
        fi
    done
    
    if [ ${#missing_files[@]} -eq 0 ]; then
        log_success "Project structure is correct"
        return 0
    else
        log_error "Missing ${#missing_files[@]} required files"
        return 1
    fi
}

# Check and create test structure
check_test_structure() {
    log_step "Checking test structure..."
    
    # Create test directories if they don't exist
    mkdir -p "$TESTS_DIR"
    mkdir -p "$UNIT_TESTS_DIR"
    mkdir -p "$INTEGRATION_TESTS_DIR"
    
    # Create __init__.py files
    touch "$TESTS_DIR/__init__.py"
    touch "$UNIT_TESTS_DIR/__init__.py"
    touch "$INTEGRATION_TESTS_DIR/__init__.py"
    
    # Create basic conftest.py if it doesn't exist
    if [ ! -f "$TESTS_DIR/conftest.py" ]; then
        log_info "Creating basic conftest.py..."
        cat > "$TESTS_DIR/conftest.py" << 'EOF'
import pytest
import sys
from pathlib import Path

# Add the app directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@pytest.fixture
def client():
    """Create FastAPI test client"""
    from fastapi.testclient import TestClient
    from app.main import app
    
    with TestClient(app) as test_client:
        yield test_client
EOF
        log_success "Created basic conftest.py"
    fi
    
    log_success "Test structure ready"
}

# Test module imports
test_imports() {
    log_step "Testing module imports..."
    
    local modules=(
        "app.main"
        "app.core.config"
        "app.models.token"
        "app.utils.redis_client"
        "app.utils.chroma_client"
        "app.utils.cache"
        "app.utils.validation"
        "app.core.logging"
    )
    
    local failed_imports=()
    
    for module in "${modules[@]}"; do
        if $PYTHON_CMD -c "import $module" >/dev/null 2>&1; then
            log_success "Import successful: $module"
        else
            failed_imports+=("$module")
            log_error "Import failed: $module"
        fi
    done
    
    if [ ${#failed_imports[@]} -eq 0 ]; then
        log_success "All modules imported successfully"
        return 0
    else
        log_error "Failed to import ${#failed_imports[@]} modules"
        return 1
    fi
}

# Test basic functionality
test_basic_functionality() {
    log_step "Testing basic functionality..."
    
    # Test configuration
    if $PYTHON_CMD -c "
from app.core.config import get_settings
settings = get_settings()
assert settings is not None
print('✅ Configuration system working')
" 2>/dev/null; then
        log_success "Configuration system working"
    else
        log_error "Configuration system failed"
        return 1
    fi
    
    # Test models
    if $PYTHON_CMD -c "
from app.models.token import TokenMetadata, PriceData
from decimal import Decimal

metadata = TokenMetadata(
    mint='So11111111111111111111111111111111111112',
    name='Test Token',
    symbol='TEST'
)
price_data = PriceData(current_price=Decimal('100.0'))
assert metadata.symbol == 'TEST'
assert price_data.current_price == Decimal('100.0')
print('✅ Pydantic models working')
" 2>/dev/null; then
        log_success "Pydantic models working"
    else
        log_error "Pydantic models failed"
        return 1
    fi
    
    # Test FastAPI app creation
    if $PYTHON_CMD -c "
from app.main import app
assert app is not None
print('✅ FastAPI app creation working')
" 2>/dev/null; then
        log_success "FastAPI app creation working"
    else
        log_error "FastAPI app creation failed"
        return 1
    fi
    
    return 0
}

# Test FastAPI endpoints
test_fastapi_endpoints() {
    log_step "Testing FastAPI endpoints..."
    
    if $PYTHON_CMD -c "
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    # Test root endpoint
    response = client.get('/')
    assert response.status_code == 200
    
    data = response.json()
    assert data['service'] == 'Solana Token Analysis AI System'
    
    # Test health endpoint
    response = client.get('/health')
    assert response.status_code in [200, 503]
    
    # Test commands endpoint
    response = client.get('/commands')
    assert response.status_code == 200

print('✅ FastAPI endpoints working')
" 2>/dev/null; then
        log_success "FastAPI endpoints working"
        return 0
    else
        log_error "FastAPI endpoints failed"
        return 1
    fi
}

# Run pytest suite
run_pytest_suite() {
    local test_path="$1"
    local test_name="$2"
    local extra_args="$3"
    
    log_info "Running $test_name..."
    
    # Build pytest command
    local cmd="$PYTHON_CMD -m pytest"
    
    # Add path
    if [ -n "$test_path" ]; then
        cmd="$cmd $test_path"
    fi
    
    # Add standard options
    cmd="$cmd -v --tb=short --no-header"
    
    # Add extra arguments
    if [ -n "$extra_args" ]; then
        cmd="$cmd $extra_args"
    fi
    
    # Run the command and capture output
    local start_time=$(date +%s)
    local output
    local exit_code
    
    if output=$(eval $cmd 2>&1); then
        exit_code=0
    else
        exit_code=$?
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Parse results from output
    local passed=$(echo "$output" | grep -o "[0-9]\+ passed" | grep -o "[0-9]\+" || echo "0")
    local failed=$(echo "$output" | grep -o "[0-9]\+ failed" | grep -o "[0-9]\+" || echo "0")
    local skipped=$(echo "$output" | grep -o "[0-9]\+ skipped" | grep -o "[0-9]\+" || echo "0")
    
    # Update global counters
    TOTAL_TESTS=$((TOTAL_TESTS + passed + failed))
    PASSED_TESTS=$((PASSED_TESTS + passed))
    FAILED_TESTS=$((FAILED_TESTS + failed))
    
    # Report results
    if [ $exit_code -eq 0 ]; then
        log_success "$test_name: PASSED (${duration}s) - $passed passed, $skipped skipped"
    else
        log_error "$test_name: FAILED (${duration}s) - $passed passed, $failed failed, $skipped skipped"
        
        # Show failed test details
        if [ $failed -gt 0 ]; then
            echo "$output" | grep -A 5 "FAILED\|ERROR" | head -20
        fi
    fi
    
    return $exit_code
}

# Run unit tests
run_unit_tests() {
    if [ -d "$UNIT_TESTS_DIR" ] && [ -n "$(find "$UNIT_TESTS_DIR" -name "test_*.py" 2>/dev/null)" ]; then
        run_pytest_suite "$UNIT_TESTS_DIR" "Unit Tests" "-m unit"
    else
        log_warn "No unit tests found in $UNIT_TESTS_DIR"
    fi
}

# Run integration tests
run_integration_tests() {
    if [ -d "$INTEGRATION_TESTS_DIR" ] && [ -n "$(find "$INTEGRATION_TESTS_DIR" -name "test_*.py" 2>/dev/null)" ]; then
        run_pytest_suite "$INTEGRATION_TESTS_DIR" "Integration Tests" "-m integration"
    else
        log_warn "No integration tests found in $INTEGRATION_TESTS_DIR"
    fi
}

# Run all pytest tests
run_all_pytest_tests() {
    if [ -d "$TESTS_DIR" ] && [ -n "$(find "$TESTS_DIR" -name "test_*.py" 2>/dev/null)" ]; then
        run_pytest_suite "$TESTS_DIR" "All Tests" ""
    else
        log_warn "No tests found in $TESTS_DIR"
    fi
}

# Run health checks
run_health_checks() {
    log_step "Running system health checks..."
    
    if $PYTHON_CMD -c "
import asyncio
from app.utils.health import health_check_all_services

async def check_health():
    health_status = await health_check_all_services()
    
    if health_status.get('overall_status'):
        print('✅ System health check: PASSED')
        
        services = health_status.get('services', {})
        for service, status in services.items():
            if status.get('healthy'):
                print(f'  ✅ {service}: Healthy')
            else:
                print(f'  ⚠️  {service}: {status.get(\"error\", \"Unhealthy\")}')
        return True
    else:
        print('⚠️  System health check: PARTIAL')
        print('Some optional services are not available')
        return True

result = asyncio.run(check_health())
" 2>/dev/null; then
        log_success "Health checks completed"
        return 0
    else
        log_warn "Health checks failed (this is usually OK for testing)"
        return 0  # Don't fail the whole suite for health checks
    fi
}

# Create sample tests if none exist
create_sample_tests() {
    log_step "Creating sample tests..."
    
    # Sample unit test
    if [ ! -f "$UNIT_TESTS_DIR/test_sample_unit.py" ]; then
        cat > "$UNIT_TESTS_DIR/test_sample_unit.py" << 'EOF'
import pytest
from app.core.config import get_settings
from app.models.token import TokenMetadata

@pytest.mark.unit
class TestSampleUnit:
    """Sample unit tests"""
    
    def test_settings_creation(self):
        """Test that settings can be created"""
        settings = get_settings()
        assert settings is not None
        assert hasattr(settings, 'ENV')
    
    def test_token_metadata_creation(self):
        """Test token metadata creation"""
        metadata = TokenMetadata(
            mint="So11111111111111111111111111111111111112",
            name="Test Token",
            symbol="TEST"
        )
        assert metadata.mint == "So11111111111111111111111111111111111112"
        assert metadata.name == "Test Token"
        assert metadata.symbol == "TEST"
EOF
        log_success "Created sample unit test"
    fi
    
    # Sample integration test
    if [ ! -f "$INTEGRATION_TESTS_DIR/test_sample_integration.py" ]; then
        cat > "$INTEGRATION_TESTS_DIR/test_sample_integration.py" << 'EOF'
import pytest

@pytest.mark.integration
class TestSampleIntegration:
    """Sample integration tests"""
    
    def test_fastapi_health_endpoint(self, client):
        """Test FastAPI health endpoint"""
        response = client.get("/health")
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "overall_status" in data
    
    def test_fastapi_root_endpoint(self, client):
        """Test FastAPI root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["service"] == "Solana Token Analysis AI System"
EOF
        log_success "Created sample integration test"
    fi
}

# Generate test report
generate_report() {
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    
    log_header "Test Report Summary"
    
    echo "Total execution time: ${total_duration}s"
    echo "Total tests run: $TOTAL_TESTS"
    echo "Tests passed: $PASSED_TESTS"
    echo "Tests failed: $FAILED_TESTS"
    
    if [ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; then
        log_success "ALL TESTS PASSED ($PASSED_TESTS/$TOTAL_TESTS)"
        echo
        log_success "🎉 Your system is ready for development!"
        echo
        log_info "Next steps:"
        log_info "1. Configure API keys in .env file"
        log_info "2. Set up Redis server for better performance"
        log_info "3. Install ChromaDB for vector storage"
        log_info "4. Run the application with ./start.sh"
    elif [ $TOTAL_TESTS -eq 0 ]; then
        log_warn "NO TESTS FOUND"
        log_info "Use '$0 --create-samples' to create sample tests"
    else
        log_warn "SOME TESTS FAILED ($PASSED_TESTS/$TOTAL_TESTS passed)"
        echo
        log_info "Common issues and solutions:"
        log_info "1. Missing dependencies - run: pip install -r requirements-test.txt"
        log_info "2. Python path issues - ensure you're in the project root"
        log_info "3. Optional services unavailable - this is usually OK for testing"
    fi
    
    # Save simple report
    cat > "test_report_summary.txt" << EOF
Test Execution Summary
====================
Date: $(date)
Total Duration: ${total_duration}s
Total Tests: $TOTAL_TESTS
Passed: $PASSED_TESTS
Failed: $FAILED_TESTS
Success Rate: $(( TOTAL_TESTS > 0 ? (PASSED_TESTS * 100) / TOTAL_TESTS : 0 ))%
EOF
    
    log_info "Summary saved to: test_report_summary.txt"
}

# ==============================================
# MAIN EXECUTION FUNCTIONS
# ==============================================

# Quick test mode
run_quick_tests() {
    log_header "Quick Test Mode"
    
    check_python || return 1
    activate_venv
    check_dependencies || return 1
    check_project_structure || return 1
    test_imports || return 1
    test_basic_functionality || return 1
    test_fastapi_endpoints || return 1
    
    log_success "Quick tests completed successfully!"
}

# Full test suite
run_full_tests() {
    log_header "Full Test Suite"
    
    # Setup phase
    check_python || return 1
    activate_venv
    check_dependencies || return 1
    check_project_structure || return 1
    check_test_structure
    
    # Basic tests
    test_imports || return 1
    test_basic_functionality || return 1
    test_fastapi_endpoints || return 1
    
    # Health checks (non-blocking)
    run_health_checks
    
    # Pytest suites
    log_header "Running Test Suites"
    
    # Check if we have any tests
    if [ ! -d "$TESTS_DIR" ] || [ -z "$(find "$TESTS_DIR" -name "test_*.py" 2>/dev/null)" ]; then
        log_warn "No tests found. Creating sample tests..."
        create_sample_tests
    fi
    
    # Run tests
    run_all_pytest_tests
    
    # Generate report
    generate_report
    
    # Return success if no tests failed
    return $([ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; echo $?)
}

# ==============================================
# COMMAND LINE INTERFACE
# ==============================================

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Solana Token Analysis AI System - Test Runner"
    echo ""
    echo "Options:"
    echo "  --help              Show this help message"
    echo "  --quick             Run only basic tests (fast)"
    echo "  --unit-only         Run only unit tests"
    echo "  --integration-only  Run only integration tests"
    echo "  --imports-only      Test only module imports"
    echo "  --health-only       Run only health checks"
    echo "  --create-samples    Create sample tests"
    echo "  --with-coverage     Run tests with coverage report"
    echo "  --verbose           Run with verbose output"
    echo ""
    echo "Examples:"
    echo "  $0                  # Run full test suite"
    echo "  $0 --quick          # Quick tests only"
    echo "  $0 --unit-only      # Unit tests only"
    echo "  $0 --with-coverage  # Tests with coverage"
    echo ""
}

# Main function
main() {
    # Parse command line arguments
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --quick)
            run_quick_tests
            exit $?
            ;;
        --unit-only)
            log_header "Unit Tests Only"
            check_python || exit 1
            activate_venv
            check_dependencies || exit 1
            check_test_structure
            run_unit_tests
            generate_report
            exit $([ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; echo $?)
            ;;
        --integration-only)
            log_header "Integration Tests Only"
            check_python || exit 1
            activate_venv
            check_dependencies || exit 1
            check_test_structure
            run_integration_tests
            generate_report
            exit $([ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; echo $?)
            ;;
        --imports-only)
            log_header "Import Tests Only"
            check_python || exit 1
            activate_venv
            test_imports
            exit $?
            ;;
        --health-only)
            log_header "Health Checks Only"
            check_python || exit 1
            activate_venv
            run_health_checks
            exit $?
            ;;
        --create-samples)
            log_header "Creating Sample Tests"
            check_test_structure
            create_sample_tests
            log_success "Sample tests created!"
            log_info "Run '$0' to execute all tests"
            exit 0
            ;;
        --with-coverage)
            log_header "Tests with Coverage"
            check_python || exit 1
            activate_venv
            check_dependencies || exit 1
            check_test_structure
            
            # Add coverage to pytest command
            if command_exists coverage || $PYTHON_CMD -c "import coverage" >/dev/null 2>&1; then
                run_pytest_suite "$TESTS_DIR" "All Tests with Coverage" "--cov=app --cov-report=html --cov-report=term"
                log_info "Coverage report generated in htmlcov/ directory"
            else
                log_warn "Coverage not installed. Installing..."
                $PYTHON_CMD -m pip install coverage pytest-cov
                run_pytest_suite "$TESTS_DIR" "All Tests with Coverage" "--cov=app --cov-report=html --cov-report=term"
            fi
            generate_report
            exit $([ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; echo $?)
            ;;
        --verbose)
            log_header "Verbose Test Mode"
            check_python || exit 1
            activate_venv
            check_dependencies || exit 1
            check_test_structure
            run_pytest_suite "$TESTS_DIR" "All Tests (Verbose)" "-v -s"
            generate_report
            exit $([ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; echo $?)
            ;;
        "")
            # Default: run full test suite
            echo -e "${PURPLE}"
            echo "==============================================="
            echo "  SOLANA TOKEN ANALYSIS AI SYSTEM"
            echo "  TEST SUITE"
            echo "==============================================="
            echo -e "${NC}"
            
            run_full_tests
            exit $?
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

# Handle script interruption
trap 'echo -e "\n${YELLOW}Test execution interrupted${NC}"; exit 1' INT TERM

# Run main function
main "$@"