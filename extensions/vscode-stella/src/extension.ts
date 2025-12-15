import * as vscode from 'vscode';
import * as path from 'path';
import * as cp from 'child_process';
import { StellaEditorProvider } from './editor/StellaCustomEditor';

export function activate(context: vscode.ExtensionContext) {
    console.log('Stella extension activated');

    // Register custom editor for .stella files
    context.subscriptions.push(StellaEditorProvider.register(context));

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('stella.extractPackage', extractPackage)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('stella.showInfo', showInfo)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('stella.buildFromFloorplan', buildFromFloorplan)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('stella.buildFromVideo', buildFromVideo)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('stella.verifyChecksums', verifyChecksums)
    );
}

export function deactivate() {}

// Get Python path from settings
function getPythonPath(): string {
    const config = vscode.workspace.getConfiguration('stella');
    return config.get('pythonPath', 'python');
}

// Run stella CLI command
async function runStellaCli(args: string[]): Promise<string> {
    const pythonPath = getPythonPath();
    
    return new Promise((resolve, reject) => {
        const process = cp.spawn(pythonPath, ['-m', 'stella.cli', ...args]);
        
        let stdout = '';
        let stderr = '';
        
        process.stdout.on('data', (data) => {
            stdout += data.toString();
        });
        
        process.stderr.on('data', (data) => {
            stderr += data.toString();
        });
        
        process.on('close', (code) => {
            if (code === 0) {
                resolve(stdout);
            } else {
                reject(new Error(stderr || `Process exited with code ${code}`));
            }
        });
    });
}

// Extract .stella package
async function extractPackage(uri?: vscode.Uri) {
    const stellaUri = uri || await selectStellaFile();
    if (!stellaUri) {
        return;
    }

    const outputFolder = await vscode.window.showOpenDialog({
        canSelectFiles: false,
        canSelectFolders: true,
        canSelectMany: false,
        title: 'Select output folder for extraction'
    });

    if (!outputFolder || outputFolder.length === 0) {
        return;
    }

    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Extracting .stella package...',
                cancellable: false
            },
            async () => {
                const output = await runStellaCli([
                    'extract',
                    stellaUri.fsPath,
                    '--output', outputFolder[0].fsPath
                ]);
                vscode.window.showInformationMessage(`Extracted to: ${outputFolder[0].fsPath}`);
            }
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to extract: ${error}`);
    }
}

// Show .stella file info
async function showInfo(uri?: vscode.Uri) {
    const stellaUri = uri || await selectStellaFile();
    if (!stellaUri) {
        return;
    }

    try {
        const output = await runStellaCli(['info', stellaUri.fsPath]);
        
        // Show in output channel
        const channel = vscode.window.createOutputChannel('Stella Info');
        channel.clear();
        channel.appendLine(output);
        channel.show();
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to get info: ${error}`);
    }
}

// Build .stella from floorplan
async function buildFromFloorplan(uri?: vscode.Uri) {
    const imageUri = uri || await vscode.window.showOpenDialog({
        canSelectFiles: true,
        canSelectFolders: false,
        filters: { 'Images': ['png', 'jpg', 'jpeg'] },
        title: 'Select floorplan image'
    }).then(uris => uris?.[0]);

    if (!imageUri) {
        return;
    }

    const outputUri = await vscode.window.showSaveDialog({
        filters: { 'Stella World': ['stella'] },
        title: 'Save .stella file'
    });

    if (!outputUri) {
        return;
    }

    const config = vscode.workspace.getConfiguration('stella');
    const wallHeight = config.get('defaultWallHeight', 2.7);
    const voxelSize = config.get('defaultVoxelSize', 0.1);

    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Building .stella from floorplan...',
                cancellable: false
            },
            async () => {
                await runStellaCli([
                    'build-floorplan',
                    '--input', imageUri.fsPath,
                    '--output', outputUri.fsPath,
                    '--wall-height', wallHeight.toString(),
                    '--voxel', voxelSize.toString()
                ]);
                
                vscode.window.showInformationMessage(`Created: ${outputUri.fsPath}`);
                
                // Open the created file in the custom editor (not as text document)
                await vscode.commands.executeCommand('vscode.openWith', outputUri, 'stella.worldViewer');
            }
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to build: ${error}`);
    }
}

// Build .stella from video
async function buildFromVideo(uri?: vscode.Uri) {
    const videoUri = uri || await vscode.window.showOpenDialog({
        canSelectFiles: true,
        canSelectFolders: false,
        filters: { 'Videos': ['mp4', 'mov', 'avi'] },
        title: 'Select video file'
    }).then(uris => uris?.[0]);

    if (!videoUri) {
        return;
    }

    const outputUri = await vscode.window.showSaveDialog({
        filters: { 'Stella World': ['stella'] },
        title: 'Save .stella file'
    });

    if (!outputUri) {
        return;
    }

    const config = vscode.workspace.getConfiguration('stella');
    const voxelSize = config.get('defaultVoxelSize', 0.1);

    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Building .stella from video (this may take a while)...',
                cancellable: false
            },
            async () => {
                await runStellaCli([
                    'build-video',
                    '--input', videoUri.fsPath,
                    '--output', outputUri.fsPath,
                    '--voxel', voxelSize.toString()
                ]);
                
                vscode.window.showInformationMessage(`Created: ${outputUri.fsPath}`);
                
                // Open the created file in the custom editor
                await vscode.commands.executeCommand('vscode.openWith', outputUri, 'stella.worldViewer');
            }
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to build: ${error}`);
    }
}

// Verify checksums
async function verifyChecksums(uri?: vscode.Uri) {
    const stellaUri = uri || await selectStellaFile();
    if (!stellaUri) {
        return;
    }

    try {
        const output = await runStellaCli(['verify', stellaUri.fsPath]);
        vscode.window.showInformationMessage(`Checksums valid for ${path.basename(stellaUri.fsPath)}`);
    } catch (error) {
        vscode.window.showErrorMessage(`Checksum verification failed: ${error}`);
    }
}

// Helper to select a .stella file
async function selectStellaFile(): Promise<vscode.Uri | undefined> {
    const uris = await vscode.window.showOpenDialog({
        canSelectFiles: true,
        canSelectFolders: false,
        filters: { 'Stella World': ['stella'] },
        title: 'Select .stella file'
    });
    return uris?.[0];
}
