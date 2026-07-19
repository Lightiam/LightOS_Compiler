# LightOS Compiler - EasyEDA Pro Extension Installer

A professional, cross-platform installation and development framework for building EasyEDA Pro extensions.

## 🚀 Quick Start

Choose your platform and run the installer:

**Linux/macOS:**
```bash
chmod +x install.sh
./install.sh
```

**Windows:**
```batch
install.bat
```

**Cross-platform (Python):**
```bash
python3 install.py
```

Or use Make:
```bash
make install
```

## 📋 Features

✅ **Cross-Platform Support** - Works on Windows, macOS, and Linux
✅ **Automatic Prerequisite Checking** - Validates Node.js, npm, and Git installation
✅ **Zero-Configuration Setup** - Creates full project structure automatically
✅ **TypeScript Support** - Pre-configured TypeScript and Webpack
✅ **Template Files** - Sample extension code to get started quickly
✅ **Development Tools** - Build, watch, and development mode support
✅ **Comprehensive Documentation** - Detailed guides and API reference

## 📦 What's Included

### Installers
- `install.sh` - Bash installer for Linux/macOS
- `install.bat` - Batch installer for Windows
- `install.py` - Python installer (cross-platform)
- `Makefile` - GNU Make convenience commands

### Documentation
- `README.md` - This file
- `INSTALLATION_GUIDE.md` - Detailed installation and configuration guide
- `DEVELOPMENT.md` - Development workflows and best practices

### Configuration Templates
- `extension.json` - Extension metadata template
- `tsconfig.json` - TypeScript configuration
- `webpack.config.js` - Build configuration
- `.gitignore` - Git ignore patterns

### Sample Code
- `src/index.ts` - Starter extension with activation/deactivation

## 🔧 Requirements

- **Node.js** 20.5.0 or later
- **npm** 9.0.0 or later (included with Node.js)
- **Git** 2.37.0 or later
- **Optional:** Visual Studio Code (recommended)

## 📖 Installation Guides

### Using Bash (Linux/macOS)

```bash
# Make the script executable
chmod +x install.sh

# Run the installer
./install.sh
```

The script will:
1. Check for Node.js, npm, and Git
2. Create project directories
3. Initialize npm project
4. Install dependencies
5. Create configuration files
6. Generate sample code

### Using Batch (Windows)

```batch
# Option 1: Command line
install.bat

# Option 2: Double-click install.bat in File Explorer
```

The installer will:
1. Verify Node.js and npm installation
2. Set up project structure
3. Install all dependencies
4. Create configuration files

### Using Python (Cross-Platform)

```bash
# Make the script executable (Linux/macOS)
chmod +x install.py

# Run the installer
python3 install.py
```

### Using Make

```bash
# Show available commands
make help

# Run auto-detect installer
make install

# Run platform-specific installer
make install-linux      # Linux/macOS
make install-python     # Cross-platform Python
```

## 🏗️ Project Structure

After installation, your project will have:

```
project-root/
├── src/
│   └── index.ts              # Your extension source code
├── dist/
│   ├── index.js              # Compiled extension
│   ├── index.js.map          # Source map for debugging
│   └── index.d.ts            # TypeScript declarations
├── node_modules/             # Dependencies
├── extension.json            # Extension configuration
├── tsconfig.json             # TypeScript configuration
├── webpack.config.js         # Build configuration
├── package.json              # npm project manifest
├── .gitignore                # Git ignore rules
└── README.md                 # Project README
```

## 🛠️ Development Commands

### Build the Extension

```bash
npm run build
```

Compiles TypeScript and bundles using Webpack.

### Watch Mode (Development)

```bash
npm run dev
```

Automatically rebuilds when you modify source files.

### Install Dependencies

```bash
npm install
```

Installs all required packages.

## 🔌 Extension Configuration

Edit `extension.json` to configure your extension:

```json
{
  "name": "my-extension",
  "displayName": "My Awesome Extension",
  "description": "What my extension does",
  "version": "1.0.0",
  "uuid": "",
  "entry": "./dist/index",
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
    ]
  }
}
```

## 💻 Creating Your First Extension

### 1. Edit `extension.json`

Update the extension metadata with your details.

### 2. Implement `src/index.ts`

```typescript
import { registerAction, onMenuClick } from "@easyeda/pro-api-sdk";

export function activate() {
  console.log("Extension activated!");

  registerAction("my-extension.greet", {
    label: "Say Hello",
    run: async () => {
      alert("Hello from my extension!");
    }
  });
}

export function deactivate() {
  console.log("Extension deactivated");
}
```

### 3. Build

```bash
npm run build
```

### 4. Load in EasyEDA Pro

1. Open EasyEDA Pro
2. Go to **Advanced → Extension Manager**
3. Click **Load Local Extension**
4. Select your project directory

### 5. Test

Use your extension from the menus in EasyEDA Pro.

## 📚 API Reference

### activate()

Called when the extension is loaded. Initialize your extension here.

### deactivate()

Called when the extension is unloaded. Clean up resources here.

### registerAction(id, options)

Register an action that can be triggered:

```typescript
registerAction("extension.doSomething", {
  label: "Do Something",
  icon?: "path/to/icon.png",
  run: async () => {
    // Implementation
  }
});
```

### onMenuClick(menuId, callback)

Listen for menu events:

```typescript
onMenuClick("my-extension.menu", () => {
  console.log("Menu clicked!");
});
```

For complete API documentation, see:
https://prodocs.easyeda.com/en/api/guide/how-to-start.html

## 🐛 Troubleshooting

### "Node.js is not installed"

Install Node.js 20.5.0+ from https://nodejs.org/

### "npm command not found"

npm comes with Node.js. Reinstall Node.js.

### Build fails with errors

Ensure all dependencies are installed:

```bash
npm install
npm install --save-dev typescript webpack webpack-cli ts-loader
```

### Extension doesn't load

- Check `extension.json` syntax (use a JSON validator)
- Ensure `dist/index.js` exists
- Check browser console in EasyEDA Pro for errors
- Restart EasyEDA Pro after rebuilds

### Port already in use

If using development server, specify a different port in webpack config.

## 📝 Commit Workflow

1. Initialize git repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: EasyEDA extension setup"
   ```

2. Create feature branch:
   ```bash
   git checkout -b feature/my-feature
   ```

3. Commit your changes:
   ```bash
   git add src/
   git commit -m "Add feature: description"
   ```

4. Push and create PR:
   ```bash
   git push origin feature/my-feature
   ```

## 🤝 Contributing

To contribute improvements to this installer:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This installer framework is provided as-is for EasyEDA Pro extension development.

## 🔗 Resources

- **EasyEDA Official:** https://easyeda.com
- **EasyEDA Pro Documentation:** https://prodocs.easyeda.com
- **Extension API Guide:** https://prodocs.easyeda.com/en/api/guide/how-to-start.html
- **TypeScript Docs:** https://www.typescriptlang.org/
- **Webpack Docs:** https://webpack.js.org/
- **Node.js:** https://nodejs.org/

## 📧 Support

For issues with the installer or documentation, please open an issue on GitHub:
https://github.com/Lightiam/LightOS_Compiler/issues

For EasyEDA API support, visit the official documentation:
https://prodocs.easyeda.com/en/api/

---

**Happy coding! 🎉**
