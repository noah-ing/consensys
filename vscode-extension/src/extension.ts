import * as vscode from 'vscode';
import axios from 'axios';

// Output channel for displaying review results
let outputChannel: vscode.OutputChannel;

// API endpoint (configurable)
const DEFAULT_API_ENDPOINT = 'http://localhost:8000';

interface ReviewIssue {
    description: string;
    severity: string;
    line?: number;
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

export function activate(context: vscode.ExtensionContext) {
    console.log('Consensus Code Review extension is now active');

    // Create output channel
    outputChannel = vscode.window.createOutputChannel('Consensus Review');

    // Register commands
    const reviewFileCommand = vscode.commands.registerCommand(
        'consensus.reviewFile',
        reviewCurrentFile
    );

    const reviewSelectionCommand = vscode.commands.registerCommand(
        'consensus.reviewSelection',
        reviewSelection
    );

    context.subscriptions.push(reviewFileCommand, reviewSelectionCommand, outputChannel);
}

export function deactivate() {
    if (outputChannel) {
        outputChannel.dispose();
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
    isSelection: boolean = false
): Promise<void> {
    const apiEndpoint = getApiEndpoint();

    // Show progress
    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'Consensus Review',
            cancellable: false
        },
        async (progress) => {
            progress.report({ message: 'Connecting to Consensus API...' });

            try {
                // Check health
                await axios.get(`${apiEndpoint}/api/health`);

                progress.report({ message: 'Reviewing code with AI agents...' });

                // Submit review
                const response = await axios.post<ReviewResponse>(
                    `${apiEndpoint}/api/review`,
                    {
                        code,
                        language,
                        quick_mode: true
                    },
                    {
                        timeout: 60000 // 60 second timeout
                    }
                );

                const result = response.data;

                // Display results
                displayResults(result, fileName, isSelection);

                // Show notification
                const decision = result.consensus.decision;
                const issueCount = result.reviews.reduce((sum, r) => sum + r.issues.length, 0);

                if (decision === 'APPROVE') {
                    vscode.window.showInformationMessage(
                        `Consensus: APPROVED - ${issueCount} minor issues found`
                    );
                } else if (decision === 'REJECT') {
                    vscode.window.showWarningMessage(
                        `Consensus: REJECTED - ${issueCount} issues found. Check output for details.`
                    );
                } else {
                    vscode.window.showInformationMessage(
                        `Consensus: ${decision} - Review complete`
                    );
                }
            } catch (error) {
                handleError(error);
            }
        }
    );
}

function displayResults(result: ReviewResponse, fileName: string, isSelection: boolean): void {
    outputChannel.clear();
    outputChannel.show(true);

    const source = isSelection ? 'Selected Code' : fileName;
    outputChannel.appendLine('═'.repeat(60));
    outputChannel.appendLine(`CONSENSUS CODE REVIEW`);
    outputChannel.appendLine(`Source: ${source}`);
    outputChannel.appendLine(`Session: ${result.session_id}`);
    outputChannel.appendLine('═'.repeat(60));
    outputChannel.appendLine('');

    // Display each agent's review
    for (const review of result.reviews) {
        outputChannel.appendLine(`─── ${review.agent_name} ───`);
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
                outputChannel.appendLine(`  • ${suggestion}`);
            }
            outputChannel.appendLine('');
        }
    }

    // Display consensus
    outputChannel.appendLine('═'.repeat(60));
    outputChannel.appendLine('CONSENSUS');
    outputChannel.appendLine('═'.repeat(60));

    const consensus = result.consensus;
    const decisionEmoji = consensus.decision === 'APPROVE' ? '✓' :
                          consensus.decision === 'REJECT' ? '✗' : '○';
    outputChannel.appendLine(`Decision: ${decisionEmoji} ${consensus.decision}`);
    outputChannel.appendLine('');

    outputChannel.appendLine('Votes:');
    for (const [vote, count] of Object.entries(consensus.vote_counts)) {
        outputChannel.appendLine(`  ${vote}: ${count}`);
    }
    outputChannel.appendLine('');

    if (consensus.key_issues.length > 0) {
        outputChannel.appendLine('Key Issues:');
        for (const issue of consensus.key_issues) {
            outputChannel.appendLine(`  • ${issue}`);
        }
        outputChannel.appendLine('');
    }

    if (consensus.accepted_suggestions.length > 0) {
        outputChannel.appendLine('Accepted Suggestions:');
        for (const suggestion of consensus.accepted_suggestions) {
            outputChannel.appendLine(`  • ${suggestion}`);
        }
    }

    outputChannel.appendLine('');
    outputChannel.appendLine('═'.repeat(60));
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
