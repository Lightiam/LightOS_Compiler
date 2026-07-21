# EasyEDA Extension Development Guide

Advanced development workflows, best practices, and troubleshooting for EasyEDA Pro extensions.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Project Structure](#project-structure)
3. [Building Extensions](#building-extensions)
4. [Testing](#testing)
5. [Debugging](#debugging)
6. [Best Practices](#best-practices)
7. [Advanced Configuration](#advanced-configuration)
8. [Performance Optimization](#performance-optimization)
9. [Distribution](#distribution)
10. [Troubleshooting](#troubleshooting)

## Development Setup

### Initial Setup

After running the installer, verify everything works:

```bash
# Navigate to project directory
cd your-project

# Install dependencies
npm install

# Build the extension
npm run build

# Check the dist/ directory
ls -la dist/
```

### IDE Configuration

#### Visual Studio Code (Recommended)

Install extensions for TypeScript support:

1. **TypeScript Vue Plugin (Volar)**
2. **Prettier - Code formatter**
3. **ESLint**

Create `.vscode/settings.json`:

```json
{
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.formatOnSave": true,
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "typescript.tsdk": "node_modules/typescript/lib"
}
```

#### WebStorm/IntelliJ IDEA

1. Open project settings
2. Go to Languages & Frameworks → TypeScript
3. Set TypeScript version to "Local"
4. Point to `node_modules/typescript`

## Project Structure

### Directory Organization

```
extension-project/
├── src/
│   ├── index.ts              # Main entry point (required)
│   ├── types/                # TypeScript type definitions
│   │   └── api.d.ts
│   ├── utils/                # Utility functions
│   │   ├── helpers.ts
│   │   └── config.ts
│   ├── actions/              # Action handlers
│   │   ├── schematic.ts
│   │   └── pcb.ts
│   └── styles/               # Styles (if supported)
│       └── main.css
├── dist/                     # Compiled output (auto-generated)
├── tests/                    # Test files
│   └── index.test.ts
├── docs/                     # Documentation
│   └── API.md
├── .github/                  # GitHub workflows
│   └── workflows/
│       └── build.yml
├── extension.json            # Extension configuration
├── tsconfig.json             # TypeScript config
├── webpack.config.js         # Build config
├── package.json              # npm manifest
├── .gitignore                # Git ignore
└── README.md                 # Project README
```

### Creating Modules

```typescript
// src/utils/config.ts
export const CONFIG = {
  version: "1.0.0",
  debug: process.env.DEBUG === "true"
};

// src/actions/schematic.ts
import { registerAction } from "@easyeda/pro-api-sdk";

export function registerSchematicActions() {
  registerAction("extension.schematic.analyze", {
    label: "Analyze Schematic",
    run: async () => {
      console.log("Analyzing...");
    }
  });
}

// src/index.ts
import { registerSchematicActions } from "./actions/schematic";

export function activate() {
  registerSchematicActions();
}
```

## Building Extensions

### Build Modes

#### Production Build

```bash
npm run build
```

Generates optimized, minified output suitable for distribution.

#### Development Build (Watch Mode)

```bash
npm run dev
```

Rebuilds on file changes. Useful during development.

### Custom Build Scripts

Add to `package.json`:

```json
{
  "scripts": {
    "build": "webpack",
    "build:prod": "webpack --mode production",
    "build:dev": "webpack --mode development",
    "watch": "webpack --watch",
    "lint": "eslint src/",
    "type-check": "tsc --noEmit",
    "prepack": "npm run build"
  }
}
```

### Webpack Configuration

Customize `webpack.config.js` for specific needs:

```javascript
const path = require('path');
const webpack = require('webpack');

module.exports = {
  mode: process.env.NODE_ENV || 'production',
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
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      }
    ]
  },
  resolve: {
    extensions: ['.ts', '.js'],
    alias: {
      '@': path.resolve(__dirname, 'src/')
    }
  },
  devtool: process.env.NODE_ENV === 'production' 
    ? false 
    : 'source-map',
  plugins: [
    new webpack.DefinePlugin({
      'process.env.DEBUG': JSON.stringify(process.env.DEBUG || 'false')
    })
  ]
};
```

## Testing

### Unit Testing with Jest

Install Jest:

```bash
npm install --save-dev jest ts-jest @types/jest
```

Create `jest.config.js`:

```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/tests'],
  testMatch: ['**/*.test.ts'],
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts'
  ]
};
```

Write tests:

```typescript
// tests/index.test.ts
describe('Extension', () => {
  it('should activate without errors', () => {
    expect(() => {
      require('../src/index').activate();
    }).not.toThrow();
  });
});
```

Run tests:

```bash
npm test
npm test -- --coverage
```

## Debugging

### Browser DevTools

In EasyEDA Pro:

1. Open Developer Tools (F12 or Right-click → Inspect)
2. Go to Console tab
3. Look for your extension's logs
4. Use `debugger;` statements in code

### Console Logging

```typescript
// Use console methods for debugging
console.log('Normal message');
console.error('Error message');
console.warn('Warning message');
console.debug('Debug message');
console.table(data);

// Conditional logging
if (process.env.DEBUG === 'true') {
  console.debug('Detailed debug info');
}
```

### Source Maps

Ensure source maps are generated:

In `webpack.config.js`:

```javascript
module.exports = {
  devtool: process.env.NODE_ENV === 'production' 
    ? 'source-map'  // Still include for production debugging
    : 'eval-source-map'  // Faster rebuilds in dev
};
```

### Environment Variables for Debugging

```bash
# Enable debug mode
DEBUG=true npm run dev

# Set custom debug level
DEBUG=extension:* npm run dev
```

## Best Practices

### Code Organization

1. **Modular Structure** - Separate concerns into different files
2. **Type Safety** - Use TypeScript strict mode
3. **Error Handling** - Wrap async operations in try-catch

```typescript
export async function safeRun(fn: () => Promise<void>) {
  try {
    await fn();
  } catch (error) {
    console.error('Operation failed:', error);
    // User notification here
  }
}
```

### Memory Management

```typescript
// Clean up resources in deactivate()
let listeners: Array<() => void> = [];

export function activate() {
  const unsubscribe = onEvent(() => {
    // Handle event
  });
  listeners.push(unsubscribe);
}

export function deactivate() {
  // Clean up all listeners
  listeners.forEach(unsubscribe => unsubscribe());
  listeners = [];
}
```

### Performance

1. **Lazy Load** - Load heavy modules only when needed
2. **Debounce** - Avoid excessive updates

```typescript
function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn(...args), delay);
  };
}
```

### Error Handling

```typescript
export function activate() {
  try {
    registerAction("extension.action", {
      label: "My Action",
      run: async () => {
        try {
          // Your code
        } catch (error) {
          console.error('Action failed:', error);
          throw error;  // Re-throw for EasyEDA to handle
        }
      }
    });
  } catch (error) {
    console.error('Extension setup failed:', error);
  }
}
```

## Advanced Configuration

### Environment-Specific Builds

Create `webpack.prod.js` for production-specific config:

```javascript
const common = require('./webpack.config.js');
const merge = require('webpack-merge');

module.exports = merge(common, {
  mode: 'production',
  devtool: 'source-map',
  optimization: {
    minimize: true,
    usedExports: true
  }
});
```

### Multiple Entry Points

```javascript
module.exports = {
  entry: {
    main: './src/index.ts',
    plugin: './src/plugin.ts'
  },
  output: {
    filename: '[name].js'
  }
};
```

### External Dependencies

```typescript
// For external libraries, use vendor prefixes in extension.json
"dependencies": {
  "lodash": "^4.17.21"
}
```

## Performance Optimization

### Code Splitting

```javascript
module.exports = {
  optimization: {
    splitChunks: {
      chunks: 'all'
    }
  }
};
```

### Tree Shaking

Enable with:

```json
{
  "sideEffects": false
}
```

### Bundle Analysis

Install webpack-bundle-analyzer:

```bash
npm install --save-dev webpack-bundle-analyzer
```

## Distribution

### Creating Release Packages

1. Bump version in `extension.json` and `package.json`
2. Build: `npm run build`
3. Test thoroughly
4. Commit and tag: `git tag v1.0.0`
5. Package for distribution

### Distribution Methods

1. **GitHub Releases** - Upload `.eext` file to releases
2. **EasyEDA Store** - Submit for official listing
3. **Direct Distribution** - Share GitHub link

## Troubleshooting

### Build Issues

#### TypeScript Compilation Errors

```bash
# Check TypeScript config
npx tsc --noEmit

# Update TypeScript
npm install --save-dev typescript@latest
```

#### Webpack Build Fails

```bash
# Clear webpack cache
rm -rf node_modules/.cache

# Rebuild
npm run build
```

### Runtime Issues

#### Extension Won't Load

1. Check `extension.json` syntax (use jsonlint)
2. Verify `dist/index.js` exists
3. Check console errors in EasyEDA Pro
4. Restart EasyEDA Pro

#### Extension Crashes

1. Check browser console for errors
2. Look at `dist/index.js.map` source map
3. Add logging to isolate issue
4. Use debugger statement

#### Memory Leaks

1. Ensure listeners are unsubscribed
2. Clear timers and intervals
3. Check for circular references
4. Use Chrome DevTools memory profiler

### Performance Issues

```bash
# Analyze bundle size
npm install -g webpack-bundle-analyzer
webpack-bundle-analyzer dist/index.js
```

### Version Conflicts

```bash
# Check npm for conflicts
npm audit

# Fix vulnerabilities
npm audit fix

# Update dependencies safely
npm update
```

## Additional Resources

- [EasyEDA Pro API Docs](https://prodocs.easyeda.com/en/api/guide/how-to-start.html)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Webpack Documentation](https://webpack.js.org/concepts/)
- [npm Documentation](https://docs.npmjs.com/)

---

**Happy developing! 🚀**
