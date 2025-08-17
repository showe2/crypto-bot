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

# Test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
START_TIME=$(date +%s)

# ==============================================
# UTILITY FUNCTIONS
# ==============================================

# Activate virtual environment if it exists
activate_venv() {
    if [ -d "$VENV_DIR" ]; then
        log_step "Activating virtual environment..."
        
        # Detect OS and activate accordingly
        if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]] || [[ -n "$WINDIR" ]]; then
            # Windows
            if [ -f "$VENV_DIR/Scripts/activate" ]; then
                source "$VENV_DIR/Scripts/activate"
                log_success "Virtual environment activated (Windows)"
            else
                log_warn "Virtual environment activation script not found"
                export PATH="$VENV_DIR/Scripts:$PATH"
                log_success "Added venv to PATH"
            fi
        else
            # Unix-like systems
            if [ -f "$VENV_DIR/bin/activate" ]; then
                source "$VENV_DIR/bin/activate"
                log_success "Virtual environment activated (Unix)"
            else
                log_warn "Virtual environment activation script not found"
                return 1
            fi
        fi
        
        return 0
    else
        log_warn "Virtual environment not found at $VENV_DIR"
        log_info "Run ./start.sh first to set up the environment"
        return 1
    fi
}

# Check if required dependencies are installed
check_dependencies() {
    log_step "Checking test dependencies..."
    
    local missing_deps=()
    local required_deps=("pytest" "fastapi")
    
    for dep in "${required_deps[@]}"; do
        if ! python -c "import $dep" >/dev/null 2>&1; then
            missing_deps+=("$dep")
        fi
    done
    
    if [ ${#missing_deps[@]} -eq 0 ]; then
        log_success "All required dependencies are installed"
        return 0
    else
        log_warn "Missing dependencies: ${missing_deps[*]}"
        log_info "Installing missing dependencies..."
        
        if [ -f "requirements-test.txt" ]; then
            python -m pip install -r requirements-test.txt
        else
            python -m pip install pytest pytest-asyncio "fastapi[test]"
        fi
        
        log_success "Dependencies installed"
        return 0
    fi
}

# Check if service testing dependencies are available
check_service_dependencies() {
    log_step "Checking service testing dependencies..."
    
    local missing_deps=()
    local service_deps=("aiohttp" "asyncio")
    
    for dep in "${service_deps[@]}"; do
        if ! python -c "import $dep" >/dev/null 2>&1; then
            missing_deps+=("$dep")
        fi
    done
    
    if [ ${#missing_deps[@]} -eq 0 ]; then
        log_success "Service testing dependencies available"
        return 0
    else
        log_warn "Missing service dependencies: ${missing_deps[*]}"
        log_info "Installing missing dependencies..."
        
        if [ -f "requirements-test.txt" ]; then
            python -m pip install -r requirements-test.txt
        else
            python -m pip install aiohttp aiofiles
        fi
        
        log_success "Service dependencies installed"
        return 0
    fi
}

# Check project structure
check_project_structure() {
    log_step "Checking project structure..."
    
    local required_files=(
        "app/main.py"
        "app/core/config.py"
        "app/models/token.py"
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
    mkdir -p "$TESTS_DIR/services"
    
    # Create __init__.py files
    touch "$TESTS_DIR/__init__.py"
    touch "$UNIT_TESTS_DIR/__init__.py"
    touch "$INTEGRATION_TESTS_DIR/__init__.py"
    touch "$TESTS_DIR/services/__init__.py"
    
    log_success "Test structure ready"
}

# Test module imports
test_imports() {
    log_step "Testing module imports..."
    
    local modules=(
        "app.main"
        "app.core.config"
        "app.models.token"
    )
    
    local failed_imports=()
    
    for module in "${modules[@]}"; do
        if python -c "import $module" 2>/dev/null; then
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
    if python -c "
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
    if python -c "
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
    
    return 0
}

# Test FastAPI endpoints
test_fastapi_endpoints() {
    log_step "Testing FastAPI endpoints..."
    
    if python -c "
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
    local cmd="python -m pytest"
    
    # Add path
    if [ -n "$test_path" ]; then
        cmd="$cmd \"$test_path\""
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
            echo "$output" | grep -A 3 "FAILED\|ERROR" | head -10
        fi
    fi
    
    return $exit_code
}

# Create sample tests if none exist
create_sample_tests() {
    log_step "Creating sample tests..."
    
    # Sample unit test
    if [ ! -f "$UNIT_TESTS_DIR/test_sample.py" ]; then
        cat > "$UNIT_TESTS_DIR/test_sample.py" << 'EOF'
import pytest
from app.core.config import get_settings
from app.models.token import TokenMetadata

@pytest.mark.unit
class TestSample:
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
    if [ ! -f "$INTEGRATION_TESTS_DIR/test_sample.py" ]; then
        cat > "$INTEGRATION_TESTS_DIR/test_sample.py" << 'EOF'
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
    elif [ $TOTAL_TESTS -eq 0 ]; then
        log_warn "NO TESTS FOUND"
        log_info "Use '$0 --create-samples' to create sample tests"
    else
        log_warn "SOME TESTS FAILED ($PASSED_TESTS/$TOTAL_TESTS passed)"
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
    
    activate_venv || return 1
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
    activate_venv || return 1
    check_dependencies || return 1
    check_project_structure || return 1
    check_test_structure
    
    # Basic tests
    test_imports || return 1
    test_basic_functionality || return 1
    test_fastapi_endpoints || return 1
    
    # Pytest suites
    log_header "Running Test Suites"
    
    # Check if we have any tests
    if [ ! -d "$TESTS_DIR" ] || [ -z "$(find "$TESTS_DIR" -name "test_*.py" 2>/dev/null)" ]; then
        log_warn "No tests found. Creating sample tests..."
        create_sample_tests
    fi
    
    # Run tests
    run_pytest_suite "$TESTS_DIR" "All Tests" ""
    
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
    echo "  --services          Run service/API tests (mocked)"
    echo "  --services-safe     Run safe service testing tool (mock mode)"
    echo "  --services-free     Run free API tests only"
    echo "  --services-paid     Run paid API tests (⚠️  COSTS MONEY)"
    echo "  --services-health   Run service health monitoring tests"
    echo "  --create-samples    Create sample tests"
    echo "  --with-coverage     Run tests with coverage report"
    echo ""
    echo "Service Testing Modes:"
    echo "  --services          Pytest-based service tests (safe, mocked)"
    echo "  --services-safe     Safe service tester in mock mode (FREE)"
    echo "  --services-free     Safe service tester with free APIs (FREE)"
    echo "  --services-paid     Safe service tester with paid APIs (💰 COSTS MONEY)"
    echo "  --services-health   Service health monitoring tests (FREE)"
    echo ""
    echo "Examples:"
    echo "  $0                  # Run full test suite"
    echo "  $0 --quick          # Quick tests only"
    echo "  $0 --unit-only      # Unit tests only"
    echo "  $0 --services       # Service tests (mocked, safe)"
    echo "  $0 --services-safe  # Safe service testing (mock mode)"
    echo "  $0 --services-free  # Test free APIs only"
    echo ""
    echo "⚠️  WARNING: --services-paid may consume API credits!"
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
            activate_venv || exit 1
            check_dependencies || exit 1
            check_test_structure
            run_pytest_suite "$UNIT_TESTS_DIR" "Unit Tests" "-m unit"
            generate_report
            exit $([ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; echo $?)
            ;;
        --integration-only)
            log_header "Integration Tests Only"
            activate_venv || exit 1
            check_dependencies || exit 1
            check_test_structure
            run_pytest_suite "$INTEGRATION_TESTS_DIR" "Integration Tests" "-m integration"
            generate_report
            exit $([ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; echo $?)
            ;;
        --services)
            log_header "Service Tests Only"
            activate_venv || exit 1
            check_dependencies || exit 1
            check_service_dependencies || exit 1
            check_test_structure
            
            # Check if services directory exists
            SERVICES_DIR="$TESTS_DIR/services"
            if [ ! -d "$SERVICES_DIR" ]; then
                log_warn "Services test directory not found: $SERVICES_DIR"
                log_info "Creating services test directory..."
                mkdir -p "$SERVICES_DIR"
                touch "$SERVICES_DIR/__init__.py"
            fi
            
            run_pytest_suite "$SERVICES_DIR" "Service Tests" "-m services"
            generate_report
            exit $([ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; echo $?)
            ;;
        --services-safe)
            log_header "Safe Service Testing Tool"
            activate_venv || exit 1
            check_dependencies || exit 1
            check_service_dependencies || exit 1
            
            # Check if safe service tester exists
            SAFE_TESTER="$TESTS_DIR/services/test_services.py"
            if [ ! -f "$SAFE_TESTER" ]; then
                log_error "Safe service tester not found: $SAFE_TESTER"
                log_info "Please ensure tests/services/test_services.py exists"
                exit 1
            fi
            
            # Create results directory
            mkdir -p "$TESTS_DIR/services/results"
            
            log_info "Running safe service tester in mock mode (safest)..."
            log_info "This will test system components even if the server isn't running"
            python -m tests.services.test_services --mode mock
            
            # Show results location
            if [ -f "$TESTS_DIR/services/results/latest_mock.json" ]; then
                log_success "Latest results available at: $TESTS_DIR/services/results/latest_mock.json"
            fi
            
            exit $?
            ;;
        --services-free)
            log_header "Free API Service Testing"
            activate_venv || exit 1
            check_dependencies || exit 1
            check_service_dependencies || exit 1
            
            SAFE_TESTER="$TESTS_DIR/services/test_services.py"
            if [ ! -f "$SAFE_TESTER" ]; then
                log_error "Safe service tester not found: $SAFE_TESTER"
                exit 1
            fi
            
            # Create results directory
            mkdir -p "$TESTS_DIR/services/results"
            
            log_info "Running safe service tester with free APIs only..."
            python -m tests.services.test_services --mode free
            
            # Show results location
            if [ -f "$TESTS_DIR/services/results/latest_free.json" ]; then
                log_success "Latest results available at: $TESTS_DIR/services/results/latest_free.json"
            fi
            
            exit $?
            ;;
        --services-paid)
            log_header "⚠️  PAID API SERVICE TESTING ⚠️"
            log_warn "This mode will test paid APIs and may consume credits!"
            log_warn "Make sure you have:"
            log_warn "  • Set ENABLE_API_MOCKS=true in .env (recommended)"
            log_warn "  • Sufficient API credits"
            log_warn "  • Monitoring enabled on API dashboards"
            
            activate_venv || exit 1
            check_dependencies || exit 1
            check_service_dependencies || exit 1
            
            SAFE_TESTER="$TESTS_DIR/services/test_services.py"
            if [ ! -f "$SAFE_TESTER" ]; then
                log_error "Safe service tester not found: $SAFE_TESTER"
                exit 1
            fi
            
            # Create results directory
            mkdir -p "$TESTS_DIR/services/results"
            
            # Ask for confirmation
            echo ""
            echo -e "${YELLOW}Continue with paid API testing? This may cost money! (yes/no):${NC}"
            read -r confirmation
            if [[ "$confirmation" != "yes" && "$confirmation" != "y" ]]; then
                log_info "Paid API testing cancelled"
                exit 0
            fi
            
            log_info "Running safe service tester with limited paid API calls..."
            python -m tests.services.test_services --mode limited
            
            # Show results location
            if [ -f "$TESTS_DIR/services/results/latest_limited.json" ]; then
                log_success "Latest results available at: $TESTS_DIR/services/results/latest_limited.json"
            fi
            
            exit $?
            ;;
        --services-health)
            log_header "Service Health Testing"
            activate_venv || exit 1
            check_dependencies || exit 1
            check_service_dependencies || exit 1
            check_test_structure
            
            # Run health-specific tests
            run_pytest_suite "$TESTS_DIR/services" "Service Health Tests" "-m health"
            generate_report
            exit $([ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; echo $?)
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
            activate_venv || exit 1
            check_dependencies || exit 1
            check_test_structure
            
            # Install coverage if needed
            if ! python -c "import coverage" >/dev/null 2>&1; then
                log_info "Installing coverage..."
                python -m pip install coverage pytest-cov
            fi
            
            run_pytest_suite "$TESTS_DIR" "All Tests with Coverage" "--cov=app --cov-report=html --cov-report=term"
            log_info "Coverage report generated in htmlcov/ directory"
            generate_report
            exit $([ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; echo $?)
            ;;
        "")
            # Default: run full test suite
            echo -e "${BLUE}"
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