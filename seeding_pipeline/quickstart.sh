#!/bin/bash
# VTT Pipeline Quick Start Script
# 
# One-command deployment for the VTT Knowledge Pipeline.
# Gets you from fresh clone to working pipeline in <5 minutes.

set -e  # Exit on error

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Functions
print_header() {
    echo -e "\n${GREEN}==== $1 ====${NC}"
}

print_error() {
    echo -e "${RED}Error: $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}Warning: $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        OS="windows"
        print_warning "Windows detected. Consider using quickstart.py instead."
    else
        OS="unknown"
    fi
}

# Check Python version
check_python() {
    print_header "Checking Python Version"
    
    # Try python3 first, then python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python not found. Please install Python 3.11 or higher."
        exit 1
    fi
    
    # Check version
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
        print_error "Python 3.11+ required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    print_success "Python $PYTHON_VERSION detected"
}

# Create virtual environment
setup_venv() {
    print_header "Setting Up Virtual Environment"
    
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists"
    else
        $PYTHON_CMD -m venv venv || {
            print_error "Failed to create virtual environment"
            exit 1
        }
        print_success "Virtual environment created"
    fi
    
    # Activate based on OS
    if [ "$OS" == "windows" ]; then
        source venv/Scripts/activate 2>/dev/null || {
            print_warning "Could not activate venv on Windows. Run manually:"
            echo "venv\\Scripts\\activate"
        }
    else
        source venv/bin/activate || {
            print_error "Failed to activate virtual environment"
            exit 1
        }
    fi
    
    print_success "Virtual environment activated"
}

# Install dependencies
install_deps() {
    print_header "Installing Dependencies"
    
    # Upgrade pip first
    pip install --upgrade pip || {
        print_warning "Could not upgrade pip"
    }
    
    # Check available memory
    if command -v free &> /dev/null; then
        AVAILABLE_MB=$(free -m | awk 'NR==2{print $7}')
        if [ "$AVAILABLE_MB" -lt 2048 ]; then
            print_warning "Low memory detected: ${AVAILABLE_MB}MB available"
            REQUIREMENTS="requirements-core.txt"
        else
            REQUIREMENTS="requirements-core.txt"
        fi
    else
        REQUIREMENTS="requirements-core.txt"
    fi
    
    # Install requirements
    if [ -f "$REQUIREMENTS" ]; then
        print_success "Installing from $REQUIREMENTS..."
        pip install -r "$REQUIREMENTS" || {
            print_error "Failed to install dependencies"
            print_warning "Try installing manually: pip install -r $REQUIREMENTS"
            exit 1
        }
        print_success "Dependencies installed"
    else
        print_error "$REQUIREMENTS not found"
        exit 1
    fi
}

# Setup configuration
setup_config() {
    print_header "Setting Up Configuration"
    
    if [ -f ".env" ]; then
        print_warning ".env file already exists"
        read -p "Overwrite? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_success "Keeping existing .env file"
            return
        fi
    fi
    
    if [ -f ".env.template" ]; then
        cp .env.template .env
        print_success "Created .env from template"
        
        echo
        print_warning "ACTION REQUIRED: Edit .env file with your credentials"
        echo "Required settings:"
        echo "  - NEO4J_PASSWORD: Your Neo4j database password"
        echo "  - GOOGLE_API_KEY: Your Google API key from https://makersuite.google.com/app/apikey"
        echo
        
        # Offer to open editor
        if [ "$OS" == "macos" ]; then
            read -p "Open .env in default editor? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                open .env
            fi
        elif [ "$OS" == "linux" ]; then
            if command -v nano &> /dev/null; then
                read -p "Open .env in nano? (y/N): " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    nano .env
                fi
            fi
        fi
    else
        print_error ".env.template not found"
        exit 1
    fi
}

# Create directories
setup_directories() {
    print_header "Creating Required Directories"
    
    DIRS=("checkpoints" "output" "logs")
    for dir in "${DIRS[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            print_success "Created $dir/"
        else
            print_success "$dir/ already exists"
        fi
    done
}

# Run validation
validate_deployment() {
    print_header "Validating Deployment"
    
    if [ -f "scripts/validate_deployment.py" ]; then
        $PYTHON_CMD scripts/validate_deployment.py || {
            print_warning "Some validation checks failed. This is normal for first setup."
        }
    else
        print_warning "Validation script not found"
    fi
}

# Main execution
main() {
    echo "==================================="
    echo "VTT Pipeline Quick Start"
    echo "==================================="
    
    START_TIME=$(date +%s)
    
    # Run setup steps
    detect_os
    check_python
    setup_venv
    install_deps
    setup_config
    setup_directories
    validate_deployment
    
    # Calculate duration
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    # Final instructions
    echo
    print_header "Setup Complete!"
    echo "Time taken: ${DURATION} seconds"
    echo
    echo "Next steps:"
    echo "1. Edit .env file with your credentials (if not done already)"
    echo "2. Start Neo4j database (if using)"
    echo "3. Activate virtual environment:"
    if [ "$OS" == "windows" ]; then
        echo "   venv\\Scripts\\activate"
    else
        echo "   source venv/bin/activate"
    fi
    echo "4. Test the installation:"
    echo "   $PYTHON_CMD -m src.cli.cli --help"
    echo "5. Process your first VTT file:"
    echo "   $PYTHON_CMD src/cli/minimal_cli.py sample.vtt"
    echo
    
    if [ $DURATION -gt 300 ]; then
        print_warning "Setup took longer than 5 minutes. Consider using requirements-core.txt for faster installation."
    else
        print_success "Setup completed in under 5 minutes!"
    fi
}

# Error handler
trap 'print_error "Setup failed. Check the error messages above."' ERR

# Run main function
main