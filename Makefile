.PHONY: install install-linux install-macos install-windows install-python help clean build watch docs

help:
	@echo "EasyEDA Pro Extension Installer - Available Commands"
	@echo "=================================================="
	@echo ""
	@echo "Installation:"
	@echo "  make install          - Run installer (auto-detects OS)"
	@echo "  make install-linux    - Run bash installer for Linux/macOS"
	@echo "  make install-macos    - Run bash installer for macOS"
	@echo "  make install-windows  - Run batch installer for Windows"
	@echo "  make install-python   - Run Python installer (cross-platform)"
	@echo ""
	@echo "Development:"
	@echo "  make build            - Build the extension"
	@echo "  make watch            - Build in watch mode"
	@echo "  make clean            - Clean build artifacts"
	@echo "  make docs             - Generate documentation"
	@echo ""
	@echo "Maintenance:"
	@echo "  make help             - Show this help message"
	@echo ""

# Auto-detect OS and run appropriate installer
install:
ifeq ($(OS),Windows_NT)
	@echo Running Windows installer...
	@call install.bat
else
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
	@echo Running Linux installer...
	@bash install.sh
endif
ifeq ($(UNAME_S),Darwin)
	@echo Running macOS installer...
	@bash install.sh
endif
endif

install-linux:
	@bash install.sh

install-macos:
	@bash install.sh

install-windows:
	@call install.bat

install-python:
	@python3 install.py

build:
	npm run build

watch:
	npm run dev

clean:
	rm -rf dist/ node_modules/ package-lock.json

docs:
	@echo "Documentation available at:"
	@echo "  - INSTALLATION_GUIDE.md"
	@echo "  - README.md"
	@echo "  - https://prodocs.easyeda.com/en/api/guide/how-to-start.html"

.DEFAULT_GOAL := help
