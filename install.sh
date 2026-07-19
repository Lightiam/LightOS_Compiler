#!/bin/bash

# EasyEDA Pro Extension Developer Installer
# Installs and configures the development environment for EasyEDA Pro extensions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="easyeda-extension"
COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
COLOR_NC='\033[0m' # No Color

log_info() {
    echo -e "${COLOR_GREEN}[INFO]${COLOR_NC} $1"
}

log_error() {
    echo -e "${COLOR_RED}[ERROR]${COLOR_NC} $1"
}

log_warning() {
    echo -e "${COLOR_YELLOW}[WARNING]${COLOR_NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        return 1
    fi
    return 0
}

check_version() {
    local cmd=$1
    local min_version=$2
    local version=$($cmd --version 2>&1 | head -n1)
    echo "$version"
}

echo "============================================"
echo "EasyEDA Pro Extension Installer"
echo "============================================"
echo ""

# Check Node.js
log_info "Checking Node.js installation..."
if ! check_command "node"; then
    log_error "Node.js is not installed"
    echo "Please install Node.js 20.5.0 or later from https://nodejs.org/"
    exit 1
fi

node_version=$(node -v | sed 's/v//')
log_info "Node.js version: $node_version"

# Check Git
log_info "Checking Git installation..."
if ! check_command "git"; then
    log_error "Git is not installed"
    echo "Please install Git from https://git-scm.com/"
    exit 1
fi

git_version=$(git --version | awk '{print $3}')
log_info "Git version: $git_version"

# Check npm
log_info "Checking npm installation..."
if ! check_command "npm"; then
    log_error "npm is not installed"
    exit 1
fi

npm_version=$(npm -v)
log_info "npm version: $npm_version"

echo ""
log_info "All prerequisites are installed!"
echo ""

# Create project structure if not exists
if [ ! -f "package.json" ]; then
    log_info "Creating project structure..."

    # Create directories
    mkdir -p src dist

    log_info "Setting up npm project..."
    npm init -y

    log_info "Installing dependencies..."
    npm install --save-dev typescript webpack webpack-cli ts-loader @easyeda/pro-api-sdk

    log_info "Creating TypeScript configuration..."
    cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "lib": ["ES2020"],
    "declaration": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "moduleResolution": "node"
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
EOF

    log_info "Creating webpack configuration..."
    cat > webpack.config.js << 'EOF'
const path = require('path');

module.exports = {
  mode: 'production',
  entry: './src/index.ts',
  output: {
    filename: 'index.js',
    path: path.resolve(__dirname, 'dist'),
    libraryTarget: 'umd',
    globalObject: 'this'
  },
  module: {
    rules: [
      {
        test: /\.ts$/,
        use: 'ts-loader',
        exclude: /node_modules/
      }
    ]
  },
  resolve: {
    extensions: ['.ts', '.js']
  },
  devtool: 'source-map'
};
EOF

    log_info "Updating package.json scripts..."
    npm set-script build "webpack"
    npm set-script dev "webpack --watch"
    npm set-script test "echo \"Error: no test specified\" && exit 1"

else
    log_warning "Project already exists. Skipping structure setup."
fi

echo ""
log_info "Creating extension.json template..."
if [ ! -f "extension.json" ]; then
    cat > extension.json << 'EOF'
{
  "name": "my-extension",
  "displayName": "My EasyEDA Extension",
  "description": "A custom extension for EasyEDA Pro",
  "version": "1.0.0",
  "uuid": "",
  "entry": "./dist/index",
  "main": "./dist/index.js",
  "author": "Your Name",
  "license": "MIT",
  "engines": {
    "easyeda": ">=2024.01"
  },
  "menus": {
    "schematic": [
      {
        "id": "my-extension.menu",
        "label": "My Extension",
        "group": "Custom"
      }
    ],
    "pcb": [
      {
        "id": "my-extension.menu",
        "label": "My Extension",
        "group": "Custom"
      }
    ]
  }
}
EOF
fi

echo ""
log_info "Creating sample extension source..."
if [ ! -f "src/index.ts" ]; then
    cat > src/index.ts << 'EOF'
import { registerAction, onMenuClick } from "@easyeda/pro-api-sdk";

// Initialize your extension
export function activate() {
  console.log("Extension activated");

  // Register menu actions
  registerAction("my-extension.action", {
    label: "Run My Extension",
    run: async () => {
      console.log("Extension action executed");
    }
  });

  // Listen for menu clicks
  onMenuClick("my-extension.menu", () => {
    console.log("Menu clicked");
  });
}

export function deactivate() {
  console.log("Extension deactivated");
}
EOF
fi

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
log_info "Next steps:"
echo "  1. Edit extension.json with your extension details"
echo "  2. Implement your extension logic in src/index.ts"
echo "  3. Run 'npm run build' to compile your extension"
echo "  4. Use Extension Manager in EasyEDA Pro to load the extension"
echo ""
log_info "Useful commands:"
echo "  - npm run build    : Build the extension"
echo "  - npm run dev      : Build in watch mode"
echo ""
log_info "For more information, visit:"
echo "  https://prodocs.easyeda.com/en/api/guide/how-to-start.html"
echo ""
