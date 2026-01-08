# Consensus Code Review - VS Code Extension

Multi-agent AI code review with debate-style consensus building, right in your editor.

## Features

- **Review Current File**: Get a comprehensive code review from multiple AI agents
- **Review Selection**: Review just the selected code snippet
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

### Review Selection

1. Select code in the editor
2. Use one of these methods:
   - Press `Ctrl+Shift+Alt+R` (or `Cmd+Shift+Alt+R` on Mac)
   - Right-click and select "Consensus: Review Selection"

### View Results

Results appear in the Output panel under "Consensus Review". The output includes:

- Individual agent reviews with severity and confidence
- Issues found with severity levels (LOW, MEDIUM, HIGH, CRITICAL)
- Suggestions from each agent
- Final consensus decision (APPROVE/REJECT/ABSTAIN)
- Key issues agreed upon by multiple agents
- Accepted suggestions

## Configuration

Configure the extension in VS Code settings:

```json
{
  "consensus.apiEndpoint": "http://localhost:8000"
}
```

### Available Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `consensus.apiEndpoint` | URL of the Consensus web API | `http://localhost:8000` |

## Keyboard Shortcuts

| Command | Windows/Linux | Mac |
|---------|---------------|-----|
| Review Current File | `Ctrl+Shift+R` | `Cmd+Shift+R` |
| Review Selection | `Ctrl+Shift+Alt+R` | `Cmd+Shift+Alt+R` |

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

## Contributing

Contributions are welcome! Please see the main [Consensus repository](https://github.com/consensus/consensus) for contribution guidelines.

## License

MIT License - see the main repository for details.
