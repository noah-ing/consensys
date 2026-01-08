import * as vscode from 'vscode';
import axios from 'axios';

// Global state
let outputChannel: vscode.OutputChannel;
let diagnosticCollection: vscode.DiagnosticCollection;
let statusBarItem: vscode.StatusBarItem;
let currentReviewData: Map<string, ReviewResponse> = new Map();

// API endpoint default
const DEFAULT_API_ENDPOINT = 'http://localhost:8000';

// Interfaces for API response
interface ReviewIssue {
    description: string;
    severity: string;
    line?: number;
    suggestion?: string;
}

interface AgentReview {
    agent_name: string;
    issues: ReviewIssue[];
    suggestions: string[];
    severity: string;
    confidence: number;
}

interface ConsensusResult {
    decision: string;
    vote_counts: { [key: string]: number };
    key_issues: string[];
    accepted_suggestions: string[];
}

interface ReviewResponse {
    session_id: string;
    reviews: AgentReview[];
    consensus: ConsensusResult;
}

// Code action provider for "Fix with Consensus" suggestions
class ConsensusCodeActionProvider implements vscode.CodeActionProvider {
    public static readonly providedCodeActionKinds = [
        vscode.CodeActionKind.QuickFix
    ];

    provideCodeActions(
        document: vscode.TextDocument,
        range: vscode.Range | vscode.Selection,
        context: vscode.CodeActionContext,
        token: vscode.CancellationToken
    ): vscode.CodeAction[] {
        const actions: vscode.CodeAction[] = [];

        // Get diagnostics for this range
        for (const diagnostic of context.diagnostics) {
            if (diagnostic.source === 'Consensus') {
                // Check if we have a fix suggestion stored (encoded as "suggestion:...")
                const code = diagnostic.code;
                if (typeof code === 'string' && code.startsWith('suggestion:')) {
                    const suggestion = code.substring('suggestion:'.length);
                    const truncated = suggestion.length > 50 ? suggestion.slice(0, 50) + '...' : suggestion;
                    const fix = new vscode.CodeAction(
                        `Fix: ${truncated}`,
                        vscode.CodeActionKind.QuickFix
                    );
                    fix.diagnostics = [diagnostic];
                    fix.isPreferred = true;

                    // Show the suggestion to the user
                    fix.command = {
                        command: 'consensus.showFixSuggestion',
                        title: 'Show Fix Suggestion',
                        arguments: [suggestion]
                    };

                    actions.push(fix);
                }

                // Always add "Review with Consensus" action
                const reviewAction = new vscode.CodeAction(
                    'Review with Consensus',
                    vscode.CodeActionKind.QuickFix
                );
                reviewAction.diagnostics = [diagnostic];
                reviewAction.command = {
                    command: 'consensus.reviewFile',
                    title: 'Review File'
                };
                actions.push(reviewAction);
            }
        }

        return actions;
    }
}

export function activate(context: vscode.ExtensionContext) {
    console.log('Consensus Code Review extension is now active');

    // Create output channel
    outputChannel = vscode.window.createOutputChannel('Consensus Review');

    // Create diagnostic collection
    diagnosticCollection = vscode.languages.createDiagnosticCollection('consensus');

    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'consensus.reviewFile';
    statusBarItem.text = '$(shield) Consensus';
    statusBarItem.tooltip = 'Click to review current file with Consensus';
    statusBarItem.show();

    // Register commands
    const reviewFileCommand = vscode.commands.registerCommand(
        'consensus.reviewFile',
        reviewCurrentFile
    );

    const reviewSelectionCommand = vscode.commands.registerCommand(
        'consensus.reviewSelection',
        reviewSelection
    );

    const clearDiagnosticsCommand = vscode.commands.registerCommand(
        'consensus.clearDiagnostics',
        () => {
            diagnosticCollection.clear();
            updateStatusBar('idle');
        }
    );

    const showFixSuggestionCommand = vscode.commands.registerCommand(
        'consensus.showFixSuggestion',
        (suggestion: string) => {
            vscode.window.showInformationMessage(
                `Consensus Suggestion: ${suggestion}`,
                'Copy to Clipboard'
            ).then(selection => {
                if (selection === 'Copy to Clipboard') {
                    vscode.env.clipboard.writeText(suggestion);
                    vscode.window.showInformationMessage('Suggestion copied to clipboard');
                }
            });
        }
    );

    // Register code action provider for all languages
    const codeActionProvider = vscode.languages.registerCodeActionsProvider(
        { scheme: 'file' },
        new ConsensusCodeActionProvider(),
        {
            providedCodeActionKinds: ConsensusCodeActionProvider.providedCodeActionKinds
        }
    );

    // Auto-review on save (if enabled)
    const onSaveListener = vscode.workspace.onDidSaveTextDocument(async (document) => {
        const config = vscode.workspace.getConfiguration('consensus');
        if (config.get<boolean>('autoReviewOnSave')) {
            // Only review code files
            const supportedLanguages = ['python', 'javascript', 'typescript', 'go', 'rust', 'java', 'cpp', 'c'];
            if (supportedLanguages.includes(document.languageId)) {
                await performReview(document.getText(), document.fileName, document.languageId, false, true);
            }
        }
    });

    // Update status bar on active editor change
    const onEditorChangeListener = vscode.window.onDidChangeActiveTextEditor((editor) => {
        if (editor) {
            const diagnostics = diagnosticCollection.get(editor.document.uri);
            if (diagnostics && diagnostics.length > 0) {
                const errorCount = diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Error).length;
                const warningCount = diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Warning).length;
                updateStatusBar('reviewed', errorCount, warningCount);
            } else {
                updateStatusBar('idle');
            }
        }
    });

    context.subscriptions.push(
        reviewFileCommand,
        reviewSelectionCommand,
        clearDiagnosticsCommand,
        showFixSuggestionCommand,
        codeActionProvider,
        onSaveListener,
        onEditorChangeListener,
        outputChannel,
        diagnosticCollection,
        statusBarItem
    );
}

export function deactivate() {
    if (outputChannel) {
        outputChannel.dispose();
    }
    if (diagnosticCollection) {
        diagnosticCollection.dispose();
    }
    if (statusBarItem) {
        statusBarItem.dispose();
    }
}

function updateStatusBar(state: 'idle' | 'reviewing' | 'reviewed' | 'error', errors: number = 0, warnings: number = 0): void {
    switch (state) {
        case 'idle':
            statusBarItem.text = '$(shield) Consensus';
            statusBarItem.tooltip = 'Click to review current file with Consensus';
            statusBarItem.backgroundColor = undefined;
            break;
        case 'reviewing':
            statusBarItem.text = '$(sync~spin) Reviewing...';
            statusBarItem.tooltip = 'Consensus review in progress...';
            statusBarItem.backgroundColor = undefined;
            break;
        case 'reviewed':
            if (errors > 0) {
                statusBarItem.text = `$(error) ${errors} $(warning) ${warnings}`;
                statusBarItem.tooltip = `Consensus: ${errors} errors, ${warnings} warnings`;
                statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
            } else if (warnings > 0) {
                statusBarItem.text = `$(warning) ${warnings}`;
                statusBarItem.tooltip = `Consensus: ${warnings} warnings`;
                statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
            } else {
                statusBarItem.text = '$(check) Consensus';
                statusBarItem.tooltip = 'Consensus: No issues found';
                statusBarItem.backgroundColor = undefined;
            }
            break;
        case 'error':
            statusBarItem.text = '$(error) Consensus';
            statusBarItem.tooltip = 'Consensus: Connection error';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
            break;
    }
}

async function reviewCurrentFile(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showErrorMessage('No active editor found');
        return;
    }

    const document = editor.document;
    const code = document.getText();
    const fileName = document.fileName;
    const language = document.languageId;

    await performReview(code, fileName, language);
}

async function reviewSelection(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showErrorMessage('No active editor found');
        return;
    }

    const selection = editor.selection;
    if (selection.isEmpty) {
        vscode.window.showErrorMessage('No code selected');
        return;
    }

    const code = editor.document.getText(selection);
    const fileName = editor.document.fileName;
    const language = editor.document.languageId;

    await performReview(code, fileName, language, true);
}

async function performReview(
    code: string,
    fileName: string,
    language: string,
    isSelection: boolean = false,
    isSilent: boolean = false
): Promise<void> {
    const apiEndpoint = getApiEndpoint();

    updateStatusBar('reviewing');

    // Show progress (unless silent mode for auto-review)
    const progressOptions = {
        location: isSilent ? vscode.ProgressLocation.Window : vscode.ProgressLocation.Notification,
        title: 'Consensus Review',
        cancellable: false
    };

    await vscode.window.withProgress(progressOptions, async (progress) => {
        progress.report({ message: 'Connecting to Consensus API...' });

        try {
            // Check health
            await axios.get(`${apiEndpoint}/api/health`, { timeout: 5000 });

            progress.report({ message: 'Reviewing code with AI agents...' });

            // Submit review
            const response = await axios.post<ReviewResponse>(
                `${apiEndpoint}/api/review`,
                {
                    code,
                    language,
                    quick: true  // API expects 'quick', not 'quick_mode'
                },
                {
                    timeout: 60000 // 60 second timeout
                }
            );

            const result = response.data;

            // Store review data for code actions
            currentReviewData.set(fileName, result);

            // Display results in output
            displayResults(result, fileName, isSelection);

            // Update diagnostics
            const editor = vscode.window.activeTextEditor;
            if (editor && editor.document.fileName === fileName) {
                updateDiagnostics(editor.document, result);
            }

            // Update status bar
            const diagnostics = diagnosticCollection.get(vscode.Uri.file(fileName));
            if (diagnostics) {
                const errorCount = diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Error).length;
                const warningCount = diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Warning).length;
                updateStatusBar('reviewed', errorCount, warningCount);
            }

            // Show notification (unless silent)
            if (!isSilent) {
                const decision = result.consensus.decision;
                const issueCount = result.reviews.reduce((sum, r) => sum + r.issues.length, 0);

                if (decision === 'APPROVE') {
                    vscode.window.showInformationMessage(
                        `Consensus: APPROVED - ${issueCount} minor issues found`
                    );
                } else if (decision === 'REJECT') {
                    vscode.window.showWarningMessage(
                        `Consensus: REJECTED - ${issueCount} issues found. Check Problems panel.`
                    );
                } else {
                    vscode.window.showInformationMessage(
                        `Consensus: ${decision} - Review complete`
                    );
                }
            }
        } catch (error) {
            updateStatusBar('error');
            if (!isSilent) {
                handleError(error);
            }
        }
    });
}

function updateDiagnostics(document: vscode.TextDocument, result: ReviewResponse): void {
    const diagnostics: vscode.Diagnostic[] = [];

    // Map severity to VS Code diagnostic severity
    const severityMap: { [key: string]: vscode.DiagnosticSeverity } = {
        'CRITICAL': vscode.DiagnosticSeverity.Error,
        'HIGH': vscode.DiagnosticSeverity.Error,
        'MEDIUM': vscode.DiagnosticSeverity.Warning,
        'LOW': vscode.DiagnosticSeverity.Information
    };

    for (const review of result.reviews) {
        for (const issue of review.issues) {
            // Determine line number (default to 1 if not specified)
            const lineNumber = Math.max(0, (issue.line || 1) - 1);
            const lineCount = document.lineCount;

            // Clamp line number to valid range
            const validLine = Math.min(lineNumber, lineCount - 1);
            const line = document.lineAt(validLine);

            const range = new vscode.Range(
                validLine,
                line.firstNonWhitespaceCharacterIndex,
                validLine,
                line.text.length
            );

            const severity = severityMap[issue.severity] || vscode.DiagnosticSeverity.Warning;
            const diagnostic = new vscode.Diagnostic(
                range,
                `[${review.agent_name}] ${issue.description}`,
                severity
            );

            diagnostic.source = 'Consensus';

            // Store suggestion in diagnostic code (for code actions to access)
            // We encode the suggestion as part of the code value string
            if (issue.suggestion || (review.suggestions && review.suggestions.length > 0)) {
                const suggestionText = issue.suggestion || review.suggestions[0];
                diagnostic.code = `suggestion:${suggestionText}`;
            }

            diagnostics.push(diagnostic);
        }
    }

    // Add key issues from consensus as informational diagnostics at line 1
    if (result.consensus.key_issues.length > 0) {
        for (const keyIssue of result.consensus.key_issues) {
            const diagnostic = new vscode.Diagnostic(
                new vscode.Range(0, 0, 0, 0),
                `[Consensus] ${keyIssue}`,
                vscode.DiagnosticSeverity.Information
            );
            diagnostic.source = 'Consensus';
            diagnostics.push(diagnostic);
        }
    }

    diagnosticCollection.set(document.uri, diagnostics);
}

function displayResults(result: ReviewResponse, fileName: string, isSelection: boolean): void {
    outputChannel.clear();
    outputChannel.show(true);

    const source = isSelection ? 'Selected Code' : fileName;
    outputChannel.appendLine('='.repeat(60));
    outputChannel.appendLine('CONSENSUS CODE REVIEW');
    outputChannel.appendLine(`Source: ${source}`);
    outputChannel.appendLine(`Session: ${result.session_id}`);
    outputChannel.appendLine('='.repeat(60));
    outputChannel.appendLine('');

    // Display each agent's review
    for (const review of result.reviews) {
        outputChannel.appendLine(`--- ${review.agent_name} ---`);
        outputChannel.appendLine(`Severity: ${review.severity} | Confidence: ${review.confidence}%`);
        outputChannel.appendLine('');

        if (review.issues.length > 0) {
            outputChannel.appendLine('Issues:');
            for (const issue of review.issues) {
                const lineInfo = issue.line ? ` (line ${issue.line})` : '';
                outputChannel.appendLine(`  [${issue.severity}]${lineInfo} ${issue.description}`);
            }
            outputChannel.appendLine('');
        }

        if (review.suggestions.length > 0) {
            outputChannel.appendLine('Suggestions:');
            for (const suggestion of review.suggestions) {
                outputChannel.appendLine(`  * ${suggestion}`);
            }
            outputChannel.appendLine('');
        }
    }

    // Display consensus
    outputChannel.appendLine('='.repeat(60));
    outputChannel.appendLine('CONSENSUS');
    outputChannel.appendLine('='.repeat(60));

    const consensus = result.consensus;
    const decisionSymbol = consensus.decision === 'APPROVE' ? '[PASS]' :
                          consensus.decision === 'REJECT' ? '[FAIL]' : '[ABSTAIN]';
    outputChannel.appendLine(`Decision: ${decisionSymbol} ${consensus.decision}`);
    outputChannel.appendLine('');

    outputChannel.appendLine('Votes:');
    for (const [vote, count] of Object.entries(consensus.vote_counts)) {
        outputChannel.appendLine(`  ${vote}: ${count}`);
    }
    outputChannel.appendLine('');

    if (consensus.key_issues.length > 0) {
        outputChannel.appendLine('Key Issues:');
        for (const issue of consensus.key_issues) {
            outputChannel.appendLine(`  * ${issue}`);
        }
        outputChannel.appendLine('');
    }

    if (consensus.accepted_suggestions.length > 0) {
        outputChannel.appendLine('Accepted Suggestions:');
        for (const suggestion of consensus.accepted_suggestions) {
            outputChannel.appendLine(`  * ${suggestion}`);
        }
    }

    outputChannel.appendLine('');
    outputChannel.appendLine('='.repeat(60));
}

function getApiEndpoint(): string {
    const config = vscode.workspace.getConfiguration('consensus');
    return config.get<string>('apiEndpoint') || DEFAULT_API_ENDPOINT;
}

function handleError(error: unknown): void {
    if (axios.isAxiosError(error)) {
        if (error.code === 'ECONNREFUSED') {
            vscode.window.showErrorMessage(
                'Cannot connect to Consensus API. Make sure the server is running: consensus web'
            );
        } else if (error.response) {
            vscode.window.showErrorMessage(
                `Consensus API error: ${error.response.status} - ${error.response.statusText}`
            );
        } else {
            vscode.window.showErrorMessage(`Network error: ${error.message}`);
        }
    } else if (error instanceof Error) {
        vscode.window.showErrorMessage(`Error: ${error.message}`);
    } else {
        vscode.window.showErrorMessage('An unknown error occurred');
    }
}
