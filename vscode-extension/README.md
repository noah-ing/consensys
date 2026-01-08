# Consensus Code Review - VS Code Extension

Multi-agent AI code review with debate-style consensus building, right in your editor.

## Features

- **Review Current File**: Get a comprehensive code review from multiple AI agents
- **Review Selection**: Review just the selected code snippet
- **Diagnostic Integration**: Issues show as warnings/errors in the Problems panel and editor
- **Code Actions**: Quick fixes with "Fix with Consensus" suggestions
- **Status Bar**: Real-time review status indicator
- **Auto-Review**: Optionally review files on save
- **Output Panel**: Detailed review results with issues, suggestions, and consensus
- **Context Menu**: Right-click access to review commands

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/consensus/consensus.git
   cd consensus/vscode-extension
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Compile the extension:
   ```bash
   npm run compile
   ```

4. Package the extension:
   ```bash
   npm run package
   ```

5. Install the VSIX file:
   - Open VS Code
   - Go to Extensions (Ctrl+Shift+X)
   - Click the "..." menu
   - Select "Install from VSIX..."
   - Choose the generated `.vsix` file

### From Marketplace (Coming Soon)

Search for "Consensus Code Review" in the VS Code Extensions marketplace.

## Prerequisites

The extension requires the Consensus web server to be running:

```bash
# Install consensus (if not already installed)
pip install -e /path/to/consensus

# Start the web server
consensus web
```

The server runs on `http://localhost:8000` by default.

## Usage

### Review Current File

1. Open a file in VS Code
2. Use one of these methods:
   - Press `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac)
   - Open Command Palette (`Ctrl+Shift+P`) and search for "Consensus: Review Current File"
   - Right-click in the editor and select "Consensus: Review Current File"
   - Click the Consensus icon in the status bar

### Review Selection

1. Select code in the editor
2. Use one of these methods:
   - Press `Ctrl+Shift+Alt+R` (or `Cmd+Shift+Alt+R` on Mac)
   - Right-click and select "Consensus: Review Selection"

### View Results

Results appear in multiple places:

1. **Problems Panel**: Issues show as warnings/errors you can click to navigate
2. **Editor**: Squiggly underlines highlight problematic code
3. **Output Panel**: Full review details under "Consensus Review"
4. **Status Bar**: Quick summary with error/warning counts

### Code Actions (Quick Fixes)

When you hover over an issue, click the lightbulb icon to see:
- **Fix suggestions**: Copy AI-generated fix suggestions
- **Review with Consensus**: Re-review the file

### Auto-Review on Save

Enable automatic reviews when you save files:

1. Open Settings (`Ctrl+,`)
2. Search for "consensus"
3. Check "Auto Review On Save"

## Configuration

Configure the extension in VS Code settings:

```json
{
  "consensus.apiEndpoint": "http://localhost:8000",
  "consensus.autoReviewOnSave": false
}
```

### Available Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `consensus.apiEndpoint` | URL of the Consensus web API | `http://localhost:8000` |
| `consensus.autoReviewOnSave` | Automatically review files when saved | `false` |

## Keyboard Shortcuts

| Command | Windows/Linux | Mac |
|---------|---------------|-----|
| Review Current File | `Ctrl+Shift+R` | `Cmd+Shift+R` |
| Review Selection | `Ctrl+Shift+Alt+R` | `Cmd+Shift+Alt+R` |

## Status Bar Icons

The status bar shows the current review state:

| Icon | Meaning |
|------|---------|
| Shield | Ready to review (click to start) |
| Spinning | Review in progress |
| Check | Review passed, no issues |
| Warning | Review complete, warnings found |
| Error | Review complete, errors found |

## Troubleshooting

### "Cannot connect to Consensus API"

Make sure the Consensus web server is running:

```bash
consensus web
```

### Extension Not Activating

1. Check the VS Code Developer Tools console for errors
2. Make sure the extension is enabled in the Extensions view
3. Try reloading VS Code (`Ctrl+Shift+P` > "Developer: Reload Window")

### Slow Reviews

- Use "Quick Mode" (enabled by default) for faster reviews
- Check your internet connection to the Anthropic API

### Clear Diagnostics

To clear all Consensus diagnostics:
- Open Command Palette (`Ctrl+Shift+P`)
- Search for "Consensus: Clear Review Diagnostics"

## Development

### Building

```bash
npm install
npm run compile
```

### Watching for Changes

```bash
npm run watch
```

### Linting

```bash
npm run lint
```

### Packaging

```bash
npm run package
```

This creates a `.vsix` file that can be installed in VS Code.

## Contributing

Contributions are welcome! Please see the main [Consensus repository](https://github.com/consensus/consensus) for contribution guidelines.

## License

MIT License - see the main repository for details.
