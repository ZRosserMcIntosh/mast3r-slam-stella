import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import JSZip from 'jszip';

/**
 * Custom editor provider for .stella files.
 * Opens .stella files in a 3D viewer with WASD controls.
 */
export class StellaEditorProvider implements vscode.CustomReadonlyEditorProvider {
    public static readonly viewType = 'stella.worldViewer';
    
    constructor(private readonly context: vscode.ExtensionContext) {}

    public static register(context: vscode.ExtensionContext): vscode.Disposable {
        const provider = new StellaEditorProvider(context);
        return vscode.window.registerCustomEditorProvider(
            StellaEditorProvider.viewType,
            provider,
            {
                webviewOptions: {
                    retainContextWhenHidden: true,
                },
                supportsMultipleEditorsPerDocument: false,
            }
        );
    }

    async openCustomDocument(
        uri: vscode.Uri,
        openContext: vscode.CustomDocumentOpenContext,
        token: vscode.CancellationToken
    ): Promise<vscode.CustomDocument> {
        return { uri, dispose: () => {} };
    }

    async resolveCustomEditor(
        document: vscode.CustomDocument,
        webviewPanel: vscode.WebviewPanel,
        token: vscode.CancellationToken
    ): Promise<void> {
        webviewPanel.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                vscode.Uri.joinPath(this.context.extensionUri, 'media'),
            ],
        };

        // Load and parse the .stella file
        const stellaData = await this.loadStellaFile(document.uri);
        
        // Generate webview HTML
        webviewPanel.webview.html = this.getHtmlForWebview(
            webviewPanel.webview,
            stellaData
        );

        // Handle messages from webview
        webviewPanel.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.type) {
                    case 'ready':
                        // Send data to webview
                        webviewPanel.webview.postMessage({
                            type: 'loadWorld',
                            data: stellaData
                        });
                        break;
                    case 'error':
                        vscode.window.showErrorMessage(`Stella Viewer: ${message.text}`);
                        break;
                }
            },
            undefined,
            []
        );
    }

    private async loadStellaFile(uri: vscode.Uri): Promise<StellaData> {
        const fileBuffer = await vscode.workspace.fs.readFile(uri);
        const zip = await JSZip.loadAsync(fileBuffer);
        
        // Read manifest
        const manifestFile = zip.file('manifest.json');
        if (!manifestFile) {
            throw new Error('Invalid .stella file: missing manifest.json');
        }
        const manifestJson = await manifestFile.async('string');
        const manifest = JSON.parse(manifestJson);
        
        // Read first level
        const levelPath = manifest.levels[0]?.path || 'levels/0/level.json';
        const levelFile = zip.file(levelPath);
        if (!levelFile) {
            throw new Error(`Invalid .stella file: missing ${levelPath}`);
        }
        const levelJson = await levelFile.async('string');
        const level = JSON.parse(levelJson);
        
        // Read render GLB
        const renderPath = path.dirname(levelPath) + '/' + (level.render?.uri || 'render.glb');
        const renderFile = zip.file(renderPath);
        let glbBase64: string | null = null;
        if (renderFile) {
            const glbBuffer = await renderFile.async('base64');
            glbBase64 = glbBuffer;
        }
        
        // Read collision data
        const collisionPath = path.dirname(levelPath) + '/' + (level.collision?.uri || 'collision.rlevox');
        const collisionFile = zip.file(collisionPath);
        let collisionBase64: string | null = null;
        if (collisionFile) {
            const collisionBuffer = await collisionFile.async('base64');
            collisionBase64 = collisionBuffer;
        }
        
        return {
            manifest,
            level,
            glbBase64,
            collisionBase64,
        };
    }

    private getHtmlForWebview(webview: vscode.Webview, data: StellaData): string {
        const nonce = getNonce();
        
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource} data: blob:; script-src 'nonce-${nonce}' https://unpkg.com; style-src 'unsafe-inline'; connect-src https://unpkg.com;">
    <title>Stella World Viewer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            overflow: hidden; 
            background: #1e1e1e;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        #canvas { width: 100vw; height: 100vh; display: block; }
        #info {
            position: absolute;
            top: 10px;
            left: 10px;
            color: white;
            background: rgba(0,0,0,0.7);
            padding: 10px 15px;
            border-radius: 5px;
            font-size: 12px;
            pointer-events: none;
            z-index: 100;
        }
        #info h3 { margin-bottom: 5px; font-size: 14px; }
        #controls {
            position: absolute;
            bottom: 10px;
            left: 10px;
            color: white;
            background: rgba(0,0,0,0.7);
            padding: 10px 15px;
            border-radius: 5px;
            font-size: 11px;
            pointer-events: none;
        }
        #loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: white;
            font-size: 18px;
        }
        #crosshair {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 20px;
            height: 20px;
            pointer-events: none;
        }
        #crosshair::before, #crosshair::after {
            content: '';
            position: absolute;
            background: rgba(255,255,255,0.5);
        }
        #crosshair::before {
            width: 2px;
            height: 100%;
            left: 50%;
            transform: translateX(-50%);
        }
        #crosshair::after {
            width: 100%;
            height: 2px;
            top: 50%;
            transform: translateY(-50%);
        }
    </style>
</head>
<body>
    <div id="loading">Loading world...</div>
    <div id="info" style="display:none;">
        <h3 id="world-title">Stella World</h3>
        <div id="position">Position: (0, 0, 0)</div>
    </div>
    <div id="controls" style="display:none;">
        <b>Controls:</b> WASD = Move | Mouse = Look | Space = Up | Shift = Down | Click to capture mouse
    </div>
    <div id="crosshair" style="display:none;"></div>
    <canvas id="canvas"></canvas>

    <!-- Three.js from CDN -->
    <script nonce="${nonce}" src="https://unpkg.com/three@0.160.0/build/three.min.js"></script>
    <script nonce="${nonce}" src="https://unpkg.com/three@0.160.0/examples/js/loaders/GLTFLoader.js"></script>
    <script nonce="${nonce}" src="https://unpkg.com/three@0.160.0/examples/js/controls/PointerLockControls.js"></script>
    
    <script nonce="${nonce}">
        // Stella World Viewer
        const vscode = acquireVsCodeApi();
        
        let scene, camera, renderer, controls;
        let collisionGrid = null;
        let gridInfo = null;
        
        // Player state
        const player = {
            height: 1.7,
            radius: 0.3,
            speed: 5.0,
            velocity: new THREE.Vector3(),
        };
        
        const keys = {};
        let isLocked = false;
        
        // Initialize
        function init() {
            // Scene
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x87ceeb);
            scene.fog = new THREE.Fog(0x87ceeb, 50, 200);
            
            // Camera
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(0, player.height, 0);
            
            // Renderer
            renderer = new THREE.WebGLRenderer({ 
                canvas: document.getElementById('canvas'),
                antialias: true 
            });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setPixelRatio(window.devicePixelRatio);
            
            // Lights
            const ambient = new THREE.AmbientLight(0xffffff, 0.6);
            scene.add(ambient);
            
            const directional = new THREE.DirectionalLight(0xffffff, 0.8);
            directional.position.set(50, 100, 50);
            scene.add(directional);
            
            // Pointer lock controls
            controls = new THREE.PointerLockControls(camera, document.body);
            
            controls.addEventListener('lock', () => {
                isLocked = true;
                document.getElementById('crosshair').style.display = 'block';
            });
            
            controls.addEventListener('unlock', () => {
                isLocked = false;
                document.getElementById('crosshair').style.display = 'none';
            });
            
            // Click to lock
            document.addEventListener('click', () => {
                if (!isLocked) {
                    controls.lock();
                }
            });
            
            // Keyboard
            document.addEventListener('keydown', (e) => { keys[e.code] = true; });
            document.addEventListener('keyup', (e) => { keys[e.code] = false; });
            
            // Resize
            window.addEventListener('resize', () => {
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            });
            
            // Add ground plane as fallback
            const groundGeo = new THREE.PlaneGeometry(100, 100);
            const groundMat = new THREE.MeshLambertMaterial({ color: 0x808080 });
            const ground = new THREE.Mesh(groundGeo, groundMat);
            ground.rotation.x = -Math.PI / 2;
            ground.position.y = 0;
            scene.add(ground);
            
            // Tell extension we're ready
            vscode.postMessage({ type: 'ready' });
            
            animate();
        }
        
        // Load world data
        function loadWorld(data) {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('info').style.display = 'block';
            document.getElementById('controls').style.display = 'block';
            
            // Set title
            const title = data.manifest.world?.title || 'Stella World';
            document.getElementById('world-title').textContent = title;
            
            // Set spawn position
            if (data.level.spawn) {
                const pos = data.level.spawn.position || [0, player.height, 0];
                camera.position.set(pos[0], pos[1], pos[2]);
                
                if (data.level.spawn.yaw_degrees) {
                    camera.rotation.y = (data.level.spawn.yaw_degrees * Math.PI) / 180;
                }
            }
            
            // Load GLB model
            if (data.glbBase64) {
                const loader = new THREE.GLTFLoader();
                const glbData = atob(data.glbBase64);
                const glbArray = new Uint8Array(glbData.length);
                for (let i = 0; i < glbData.length; i++) {
                    glbArray[i] = glbData.charCodeAt(i);
                }
                
                loader.parse(glbArray.buffer, '', (gltf) => {
                    scene.add(gltf.scene);
                    console.log('GLB loaded');
                }, (error) => {
                    console.error('Failed to load GLB:', error);
                });
            }
            
            // Load collision data
            if (data.collisionBase64) {
                loadCollisionData(data.collisionBase64);
            }
            
            // Player collision settings
            if (data.level.collision?.player) {
                player.height = data.level.collision.player.height_m || 1.7;
                player.radius = data.level.collision.player.radius_m || 0.3;
            }
        }
        
        // Parse RLEVOX collision data
        function loadCollisionData(base64Data) {
            const binary = atob(base64Data);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            const view = new DataView(bytes.buffer);
            
            // Check magic
            const magic = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]);
            if (magic !== 'STVX') {
                console.error('Invalid RLEVOX magic:', magic);
                return;
            }
            
            // Read header
            const version = view.getUint16(4, true);
            const headerSize = view.getUint16(6, true);
            const dimX = view.getUint32(8, true);
            const dimY = view.getUint32(12, true);
            const dimZ = view.getUint32(16, true);
            const voxelSize = view.getFloat32(20, true);
            const originX = view.getFloat32(24, true);
            const originY = view.getFloat32(28, true);
            const originZ = view.getFloat32(32, true);
            
            console.log('Collision grid:', dimX, dimY, dimZ, 'voxel:', voxelSize);
            
            gridInfo = { dimX, dimY, dimZ, voxelSize, originX, originY, originZ };
            
            // Decode RLE
            collisionGrid = new Uint8Array(dimX * dimY * dimZ);
            let offset = headerSize;
            
            for (let z = 0; z < dimZ; z++) {
                for (let y = 0; y < dimY; y++) {
                    let x = 0;
                    while (x < dimX && offset < bytes.length) {
                        const runLength = view.getUint16(offset, true);
                        const value = bytes[offset + 2];
                        offset += 4;
                        
                        for (let i = 0; i < runLength && x < dimX; i++, x++) {
                            collisionGrid[x + y * dimX + z * dimX * dimY] = value;
                        }
                    }
                }
            }
            
            console.log('Collision loaded');
        }
        
        // Check collision
        function checkCollision(pos) {
            if (!collisionGrid || !gridInfo) return false;
            
            const { dimX, dimY, dimZ, voxelSize, originX, originY, originZ } = gridInfo;
            
            // Check multiple points around the player
            const checkPoints = [
                [pos.x, pos.y, pos.z],
                [pos.x - player.radius, pos.y, pos.z],
                [pos.x + player.radius, pos.y, pos.z],
                [pos.x, pos.y, pos.z - player.radius],
                [pos.x, pos.y, pos.z + player.radius],
                [pos.x, pos.y + player.height * 0.5, pos.z],
            ];
            
            for (const [wx, wy, wz] of checkPoints) {
                const gx = Math.floor((wx - originX) / voxelSize);
                const gy = Math.floor((wy - originY) / voxelSize);
                const gz = Math.floor((wz - originZ) / voxelSize);
                
                if (gx >= 0 && gx < dimX && gy >= 0 && gy < dimY && gz >= 0 && gz < dimZ) {
                    if (collisionGrid[gx + gy * dimX + gz * dimX * dimY]) {
                        return true;
                    }
                }
            }
            return false;
        }
        
        // Animation loop
        let prevTime = performance.now();
        
        function animate() {
            requestAnimationFrame(animate);
            
            const time = performance.now();
            const delta = (time - prevTime) / 1000;
            prevTime = time;
            
            if (isLocked) {
                // Calculate movement direction
                const direction = new THREE.Vector3();
                
                if (keys['KeyW']) direction.z -= 1;
                if (keys['KeyS']) direction.z += 1;
                if (keys['KeyA']) direction.x -= 1;
                if (keys['KeyD']) direction.x += 1;
                if (keys['Space']) direction.y += 1;
                if (keys['ShiftLeft']) direction.y -= 1;
                
                direction.normalize();
                
                // Apply camera rotation to movement
                const moveDir = new THREE.Vector3();
                moveDir.x = direction.x;
                moveDir.z = direction.z;
                moveDir.applyQuaternion(camera.quaternion);
                moveDir.y = direction.y;
                
                // New position
                const newPos = camera.position.clone();
                newPos.add(moveDir.multiplyScalar(player.speed * delta));
                
                // Check collision
                if (!checkCollision(newPos)) {
                    camera.position.copy(newPos);
                }
                
                // Update position display
                const p = camera.position;
                document.getElementById('position').textContent = 
                    'Position: (' + p.x.toFixed(1) + ', ' + p.y.toFixed(1) + ', ' + p.z.toFixed(1) + ')';
            }
            
            renderer.render(scene, camera);
        }
        
        // Handle messages from extension
        window.addEventListener('message', (event) => {
            const message = event.data;
            switch (message.type) {
                case 'loadWorld':
                    loadWorld(message.data);
                    break;
            }
        });
        
        // Start
        init();
    </script>
</body>
</html>`;
    }
}

interface StellaData {
    manifest: any;
    level: any;
    glbBase64: string | null;
    collisionBase64: string | null;
}

function getNonce(): string {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
