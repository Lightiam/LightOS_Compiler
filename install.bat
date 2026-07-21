@echo off
REM EasyEDA Pro Extension Developer Installer for Windows
REM Installs and configures the development environment for EasyEDA Pro extensions

setlocal enabledelayedexpansion

echo.
echo ============================================
echo EasyEDA Pro Extension Installer (Windows)
echo ============================================
echo.

REM Check Node.js
echo [INFO] Checking Node.js installation...
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is not installed
    echo Please install Node.js 20.5.0 or later from https://nodejs.org/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo [INFO] Node.js version: %NODE_VERSION%

REM Check Git
echo [INFO] Checking Git installation...
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Git is not installed
    echo Please install Git from https://git-scm.com/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('git --version') do set GIT_VERSION=%%i
echo [INFO] %GIT_VERSION%

REM Check npm
echo [INFO] Checking npm installation...
where npm >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] npm is not installed
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('npm -v') do set NPM_VERSION=%%i
echo [INFO] npm version: %NPM_VERSION%

echo.
echo [INFO] All prerequisites are installed!
echo.

REM Create project structure
if not exist "package.json" (
    echo [INFO] Creating project structure...

    if not exist "src" mkdir src
    if not exist "dist" mkdir dist

    echo [INFO] Initializing npm project...
    call npm init -y

    echo [INFO] Installing dependencies...
    call npm install --save-dev typescript webpack webpack-cli ts-loader @easyeda/pro-api-sdk

    echo [INFO] Creating TypeScript configuration...
    (
        echo {
        echo   "compilerOptions": {
        echo     "target": "ES2020",
        echo     "module": "ESNext",
        echo     "lib": ["ES2020"],
        echo     "declaration": true,
        echo     "outDir": "./dist",
        echo     "rootDir": "./src",
        echo     "strict": true,
        echo     "esModuleInterop": true,
        echo     "skipLibCheck": true,
        echo     "forceConsistentCasingInFileNames": true,
        echo     "resolveJsonModule": true,
        echo     "moduleResolution": "node"
        echo   },
        echo   "include": ["src/**/*"],
        echo   "exclude": ["node_modules", "dist"]
        echo }
    ) > tsconfig.json

    echo [INFO] Creating webpack configuration...
    (
        echo const path = require('path');
        echo.
        echo module.exports = {
        echo   mode: 'production',
        echo   entry: './src/index.ts',
        echo   output: {
        echo     filename: 'index.js',
        echo     path: path.resolve(__dirname, 'dist'),
        echo     libraryTarget: 'umd',
        echo     globalObject: 'this'
        echo   },
        echo   module: {
        echo     rules: [
        echo       {
        echo         test: /\.ts$/,
        echo         use: 'ts-loader',
        echo         exclude: /node_modules/
        echo       }
        echo     ]
        echo   },
        echo   resolve: {
        echo     extensions: ['.ts', '.js']
        echo   },
        echo   devtool: 'source-map'
        echo };
    ) > webpack.config.js

    echo [INFO] Updating package.json scripts...
    call npm set-script build "webpack"
    call npm set-script dev "webpack --watch"

) else (
    echo [WARNING] Project already exists. Skipping structure setup.
)

echo.
echo [INFO] Creating extension.json template...
if not exist "extension.json" (
    (
        echo {
        echo   "name": "my-extension",
        echo   "displayName": "My EasyEDA Extension",
        echo   "description": "A custom extension for EasyEDA Pro",
        echo   "version": "1.0.0",
        echo   "uuid": "",
        echo   "entry": "./dist/index",
        echo   "main": "./dist/index.js",
        echo   "author": "Your Name",
        echo   "license": "MIT",
        echo   "engines": {
        echo     "easyeda": "^2024.01"
        echo   },
        echo   "menus": {
        echo     "schematic": [
        echo       {
        echo         "id": "my-extension.menu",
        echo         "label": "My Extension",
        echo         "group": "Custom"
        echo       }
        echo     ],
        echo     "pcb": [
        echo       {
        echo         "id": "my-extension.menu",
        echo         "label": "My Extension",
        echo         "group": "Custom"
        echo       }
        echo     ]
        echo   }
        echo }
    ) > extension.json
)

echo.
echo [INFO] Creating sample extension source...
if not exist "src\index.ts" (
    (
        echo import { registerAction, onMenuClick } from "@easyeda/pro-api-sdk";
        echo.
        echo export function activate^(^) {
        echo   console.log("Extension activated");
        echo.
        echo   registerAction("my-extension.action", {
        echo     label: "Run My Extension",
        echo     run: async ^(^) =^> {
        echo       console.log("Extension action executed");
        echo     }
        echo   });
        echo.
        echo   onMenuClick("my-extension.menu", ^(^) =^> {
        echo     console.log("Menu clicked");
        echo   });
        echo }
        echo.
        echo export function deactivate^(^) {
        echo   console.log("Extension deactivated");
        echo }
    ) > src\index.ts
)

echo.
echo ============================================
echo Setup Complete!
echo ============================================
echo.
echo [INFO] Next steps:
echo   1. Edit extension.json with your extension details
echo   2. Implement your extension logic in src\index.ts
echo   3. Run 'npm run build' to compile your extension
echo   4. Use Extension Manager in EasyEDA Pro to load the extension
echo.
echo [INFO] Useful commands:
echo   - npm run build    : Build the extension
echo   - npm run dev      : Build in watch mode
echo.
echo [INFO] For more information, visit:
echo   https://prodocs.easyeda.com/en/api/guide/how-to-start.html
echo.
pause
