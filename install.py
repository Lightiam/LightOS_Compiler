#!/usr/bin/env python3
"""
EasyEDA Pro Extension Developer Installer
Cross-platform installation and setup for EasyEDA Pro extension development
"""

import os
import sys
import subprocess
import json
import platform
import shutil
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def log_info(msg: str):
    print(f"{Colors.GREEN}[INFO]{Colors.RESET} {msg}")

def log_error(msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")

def log_warning(msg: str):
    print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} {msg}")

def log_blue(msg: str):
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")

def check_command(cmd: str) -> bool:
    """Check if a command is available."""
    return shutil.which(cmd) is not None

def run_command(cmd: list, description: str = "") -> bool:
    """Run a shell command."""
    try:
        if description:
            log_info(description)
        subprocess.run(cmd, check=True, cwd=os.getcwd())
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to run: {' '.join(cmd)}")
        return False

def get_command_version(cmd: str, flag: str = "--version") -> str:
    """Get the version of a command."""
    try:
        result = subprocess.run(
            [cmd, flag],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip().split('\n')[0]
    except Exception:
        return "unknown"

def create_directory(path: str):
    """Create a directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)

def create_file(path: str, content: str):
    """Create a file with content."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    log_info(f"Created {path}")

def check_prerequisites() -> bool:
    """Check if all prerequisites are installed."""
    log_blue("=" * 50)
    log_blue("EasyEDA Pro Extension Installer")
    log_blue("=" * 50)
    print()

    log_info("Checking prerequisites...")

    # Check Node.js
    if not check_command('node'):
        log_error("Node.js is not installed")
        print("Please install Node.js 20.5.0 or later from https://nodejs.org/")
        return False

    node_version = get_command_version('node', '-v')
    log_info(f"Node.js version: {node_version}")

    # Check npm
    if not check_command('npm'):
        log_error("npm is not installed")
        return False

    npm_version = get_command_version('npm', '-v')
    log_info(f"npm version: {npm_version}")

    # Check Git
    if not check_command('git'):
        log_error("Git is not installed")
        print("Please install Git from https://git-scm.com/")
        return False

    git_version = get_command_version('git', '--version')
    log_info(f"Git: {git_version}")

    print()
    log_info("All prerequisites are installed!")
    print()

    return True

def setup_project():
    """Set up the project structure."""
    # Check if package.json exists
    if Path("package.json").exists():
        log_warning("Project already exists. Skipping structure setup.")
        return

    log_info("Creating project structure...")

    # Create directories
    create_directory("src")
    create_directory("dist")

    # Initialize npm project
    log_info("Initializing npm project...")
    run_command(["npm", "init", "-y"])

    # Install dependencies
    log_info("Installing dependencies...")
    run_command([
        "npm", "install", "--save-dev",
        "typescript", "webpack", "webpack-cli", "ts-loader"
    ])

    # Create tsconfig.json
    tsconfig = {
        "compilerOptions": {
            "target": "ES2020",
            "module": "ESNext",
            "lib": ["ES2020"],
            "declaration": True,
            "outDir": "./dist",
            "rootDir": "./src",
            "strict": True,
            "esModuleInterop": True,
            "skipLibCheck": True,
            "forceConsistentCasingInFileNames": True,
            "resolveJsonModule": True,
            "moduleResolution": "node"
        },
        "include": ["src/**/*"],
        "exclude": ["node_modules", "dist"]
    }

    create_file("tsconfig.json", json.dumps(tsconfig, indent=2))

    # Create webpack.config.js
    webpack_config = """const path = require('path');

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
        test: /\\.ts$/,
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
"""

    create_file("webpack.config.js", webpack_config)

    # Update package.json scripts
    log_info("Updating package.json scripts...")
    with open("package.json", "r") as f:
        package = json.load(f)

    package["scripts"]["build"] = "webpack"
    package["scripts"]["dev"] = "webpack --watch"

    with open("package.json", "w") as f:
        json.dump(package, f, indent=2)

def create_extension_files():
    """Create extension template files."""

    # Create extension.json
    extension_config = {
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

    if not Path("extension.json").exists():
        create_file("extension.json", json.dumps(extension_config, indent=2))

    # Create sample TypeScript extension
    if not Path("src/index.ts").exists():
        index_ts = '''import { registerAction, onMenuClick } from "@easyeda/pro-api-sdk";

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
'''
        create_file("src/index.ts", index_ts)

    # Create .gitignore if it doesn't exist
    if not Path(".gitignore").exists():
        gitignore = """node_modules/
dist/
*.js
*.js.map
*.d.ts
.DS_Store
*.log
npm-debug.log*
.env
.env.local
.vscode/settings.json
.idea/
*.swp
*.swo
"""
        create_file(".gitignore", gitignore)

def main():
    """Main installation function."""
    try:
        if not check_prerequisites():
            sys.exit(1)

        setup_project()
        create_extension_files()

        print()
        log_blue("=" * 50)
        log_info("Setup Complete!")
        log_blue("=" * 50)
        print()

        log_info("Next steps:")
        print("  1. Edit extension.json with your extension details")
        print("  2. Implement your extension logic in src/index.ts")
        print("  3. Run 'npm run build' to compile your extension")
        print("  4. Use Extension Manager in EasyEDA Pro to load the extension")
        print()

        log_info("Useful commands:")
        print("  - npm run build    : Build the extension")
        print("  - npm run dev      : Build in watch mode")
        print()

        log_info("For more information, visit:")
        print("  https://prodocs.easyeda.com/en/api/guide/how-to-start.html")
        print()

    except KeyboardInterrupt:
        print()
        log_warning("Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        log_error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
