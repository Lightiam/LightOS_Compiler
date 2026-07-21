# EasyEDA Pro Extension Development Installer

A comprehensive installation system for setting up an EasyEDA Pro Extension development environment.

## Overview

This installer automates the setup of a complete development environment for creating EasyEDA Pro extensions. It handles all prerequisites checking, dependency installation, and project scaffolding.

## Prerequisites

Before running the installer, ensure you have:

- **Node.js** 20.5.0 or later ([Download](https://nodejs.org/))
- **npm** (comes with Node.js)
- **Git** ([Download](https://git-scm.com/))
- **Text Editor or IDE** (Visual Studio Code recommended)

## Installation Methods

### Method 1: Bash Script (macOS/Linux)

```bash
chmod +x install.sh
./install.sh
```

### Method 2: Batch Script (Windows)

```batch
install.bat
```

Or simply double-click `install.bat` in File Explorer.

### Method 3: Python Script (Cross-Platform)

```bash
python3 install.py
```

or

```bash
python install.py
```

## What Gets Installed

The installer automatically sets up:

1. **Project Structure**
   - `src/` - TypeScript source files
   - `dist/` - Compiled output directory
   - `node_modules/` - Dependencies

2. **Dependencies**
   - TypeScript compiler
   - Webpack bundler
   - ts-loader for TypeScript support
   - EasyEDA Pro API SDK type definitions

3. **Configuration Files**
   - `tsconfig.json` - TypeScript configuration
   - `webpack.config.js` - Build configuration
   - `extension.json` - Extension metadata
   - `.gitignore` - Git ignore rules

4. **Sample Files**
   - `src/index.ts` - Starter extension code

## Quick Start

### 1. Run the Installer

Choose your platform and run the appropriate installer script.

### 2. Configure Your Extension

Edit `extension.json`:

```json
{
  "name": "my-awesome-extension",
  "displayName": "My Awesome Extension",
  "description": "What my extension does",
  "version": "1.0.0",
  "uuid": "",
  "author": "Your Name",
  "license": "MIT"
}
```

### 3. Develop Your Extension

Edit `src/index.ts` to add your functionality:

```typescript
import { registerAction, onMenuClick } from "@easyeda/pro-api-sdk";

export function activate() {
  console.log("My extension is active!");

  registerAction("my-extension.action", {
    label: "Do Something",
    run: async () => {
      // Your code here
    }
  });
}

export function deactivate() {
  console.log("My extension is deactivated");
}
```

### 4. Build Your Extension

```bash
npm run build
```

This generates `dist/index.js` which is your compiled extension.

### 5. Load into EasyEDA Pro

1. Open EasyEDA Pro
2. Go to **Advanced → Extension Manager**
3. Click **Load Local Extension**
4. Select your project folder or the compiled `.eext` file

## Development Workflow

### Watch Mode (Auto-rebuild on changes)

```bash
npm run build     # One-time build
npm run dev       # Watch mode - rebuilds on file changes
```

### Project Structure

```
your-project/
├── src/
│   └── index.ts           # Your extension code
├── dist/
│   └── index.js           # Compiled output
├── extension.json         # Extension metadata
├── tsconfig.json          # TypeScript configuration
├── webpack.config.js      # Build configuration
├── package.json           # npm project file
└── node_modules/          # Dependencies
```

## Extension Configuration (extension.json)

Key fields in `extension.json`:

| Field | Description | Required |
|-------|-------------|----------|
| `name` | Unique identifier (no spaces) | Yes |
| `displayName` | User-friendly name | Yes |
| `description` | What the extension does | Yes |
| `version` | Semantic version (e.g., 1.0.0) | Yes |
| `uuid` | Unique ID from EasyEDA Store | No |
| `entry` | Path to compiled entry point | Yes |
| `author` | Your name or organization | No |
| `license` | License type (MIT, Apache, etc.) | No |
| `engines.easyeda` | Required EasyEDA version | No |
| `menus` | Menu definitions for UI | Optional |

## API Reference

### Core Functions

#### registerAction(id, options)

Register an action that can be triggered from menus or commands.

```typescript
registerAction("extension.doSomething", {
  label: "Do Something",
  icon?: "path/to/icon.png",
  run: async () => {
    // Action implementation
  }
});
```

#### onMenuClick(menuId, callback)

Listen for menu click events.

```typescript
onMenuClick("my-extension.menu", () => {
  console.log("Menu was clicked");
});
```

#### registerCommand(commandId, handler)

Register a command.

```typescript
registerCommand("extension.myCommand", async (args) => {
  // Handle command
});
```

For full API documentation, visit:
https://prodocs.easyeda.com/en/api/guide/how-to-start.html

## Troubleshooting

### "Node.js is not installed"

Install Node.js from https://nodejs.org/ (version 20.5.0 or later required).

### "npm command not found"

npm comes bundled with Node.js. Reinstall Node.js if needed.

### Build fails with TypeScript errors

Ensure TypeScript dependencies are installed:

```bash
npm install --save-dev typescript ts-loader
```

### Extension doesn't load in EasyEDA Pro

1. Check that `extension.json` has valid JSON syntax
2. Ensure `entry` path points to `./dist/index`
3. Verify the `dist/index.js` file exists
4. Check browser console in EasyEDA Pro for error messages

### Changes not reflected when rebuilding

Make sure to restart EasyEDA Pro after rebuilding the extension.

## Environment Variables

Optional environment variables for the installer:

- `NODE_ENV=development` - Set development mode for builds
- `DEBUG=true` - Enable verbose logging

## License

The installer and templates are provided as-is for EasyEDA extension development.

## Support

For issues with the installer, visit:
https://github.com/Lightiam/LightOS_Compiler/issues

For EasyEDA API documentation:
https://prodocs.easyeda.com/en/api/guide/how-to-start.html

## Additional Resources

- [EasyEDA Official Site](https://easyeda.com)
- [EasyEDA Pro Documentation](https://prodocs.easyeda.com)
- [Extension API Guide](https://prodocs.easyeda.com/en/api/guide/how-to-start.html)
- [TypeScript Documentation](https://www.typescriptlang.org/)
- [Webpack Documentation](https://webpack.js.org/)
