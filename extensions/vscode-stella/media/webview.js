/**
 * Stella Viewer - Three.js based 3D world explorer
 * WASD + mouse look controls with collision detection
 */

(function() {
    'use strict';

    // ============================================================
    // Configuration
    // ============================================================
    const CONFIG = {
        moveSpeed: 5.0,
        runMultiplier: 2.0,
        jumpVelocity: 8.0,
        gravity: 20.0,
        mouseSensitivity: 0.002,
        playerHeight: 1.7,
        playerRadius: 0.3,
        nearClip: 0.1,
        farClip: 1000,
        fov: 75,
    };

    // ============================================================
    // State
    // ============================================================
    let scene, camera, renderer;
    let stellaData = null;
    let collisionGrid = null;
    let isLocked = false;
    
    // Player state
    const player = {
        position: new THREE.Vector3(0, CONFIG.playerHeight, 0),
        velocity: new THREE.Vector3(0, 0, 0),
        rotation: new THREE.Euler(0, 0, 0, 'YXZ'),
        onGround: false,
    };
    
    // Input state
    const keys = {
        forward: false,
        backward: false,
        left: false,
        right: false,
        jump: false,
        run: false,
    };
    
    // FPS tracking
    let frameCount = 0;
    let lastFpsUpdate = performance.now();
    let currentFps = 0;

    // DOM elements
    const canvas = document.getElementById('viewport');
    const overlay = document.getElementById('overlay');
    const worldNameEl = document.getElementById('world-name');
    const positionEl = document.getElementById('position');
    const levelNameEl = document.getElementById('level-name');
    const fpsEl = document.getElementById('fps');
    const clickToStart = document.getElementById('click-to-start');
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error-message');
    const errorTextEl = document.getElementById('error-text');
    const crosshair = document.getElementById('crosshair');

    // ============================================================
    // RLEVOX Parser
    // ============================================================
    class VoxelCollider {
        constructor(voxelData) {
            this.sizeX = voxelData.sizeX;
            this.sizeY = voxelData.sizeY;
            this.sizeZ = voxelData.sizeZ;
            this.voxelSize = voxelData.voxelSize;
            this.originX = voxelData.originX;
            this.originY = voxelData.originY;
            this.originZ = voxelData.originZ;
            this.grid = voxelData.grid; // Uint8Array
        }

        // Convert world position to voxel indices
        worldToVoxel(x, y, z) {
            const vx = Math.floor((x - this.originX) / this.voxelSize);
            const vy = Math.floor((y - this.originY) / this.voxelSize);
            const vz = Math.floor((z - this.originZ) / this.voxelSize);
            return { vx, vy, vz };
        }

        // Check if voxel is solid
        isSolid(vx, vy, vz) {
            if (vx < 0 || vx >= this.sizeX ||
                vy < 0 || vy >= this.sizeY ||
                vz < 0 || vz >= this.sizeZ) {
                return false; // Out of bounds = not solid
            }
            const idx = vx + vy * this.sizeX + vz * this.sizeX * this.sizeY;
            return this.grid[idx] !== 0;
        }

        // Check if world position is inside solid voxel
        isPositionSolid(x, y, z) {
            const { vx, vy, vz } = this.worldToVoxel(x, y, z);
            return this.isSolid(vx, vy, vz);
        }

        // Check collision for a capsule/cylinder shape
        checkCapsuleCollision(x, y, z, radius, height) {
            // Check multiple points around the player
            const steps = 8;
            for (let i = 0; i < steps; i++) {
                const angle = (i / steps) * Math.PI * 2;
                const checkX = x + Math.cos(angle) * radius;
                const checkZ = z + Math.sin(angle) * radius;
                
                // Check at feet, middle, and head
                for (let h = 0; h < height; h += this.voxelSize) {
                    if (this.isPositionSolid(checkX, y + h, checkZ)) {
                        return true;
                    }
                }
                // Check top
                if (this.isPositionSolid(checkX, y + height, checkZ)) {
                    return true;
                }
            }
            // Check center column
            for (let h = 0; h < height; h += this.voxelSize) {
                if (this.isPositionSolid(x, y + h, z)) {
                    return true;
                }
            }
            return false;
        }

        // Get ground height at position
        getGroundHeight(x, z) {
            const { vx, vz } = this.worldToVoxel(x, 0, z);
            if (vx < 0 || vx >= this.sizeX || vz < 0 || vz >= this.sizeZ) {
                return 0;
            }
            
            // Find highest solid voxel
            for (let vy = this.sizeY - 1; vy >= 0; vy--) {
                if (this.isSolid(vx, vy, vz)) {
                    return this.originY + (vy + 1) * this.voxelSize;
                }
            }
            return this.originY;
        }
    }

    function parseRLEVOX(buffer) {
        const view = new DataView(buffer);
        let offset = 0;

        // Read magic "STVX"
        const magic = String.fromCharCode(
            view.getUint8(0), view.getUint8(1),
            view.getUint8(2), view.getUint8(3)
        );
        if (magic !== 'STVX') {
            throw new Error(`Invalid RLEVOX magic: ${magic}`);
        }
        offset = 4;

        // Read header
        const version = view.getUint32(offset, true); offset += 4;
        const sizeX = view.getUint32(offset, true); offset += 4;
        const sizeY = view.getUint32(offset, true); offset += 4;
        const sizeZ = view.getUint32(offset, true); offset += 4;
        const voxelSize = view.getFloat32(offset, true); offset += 4;
        const originX = view.getFloat32(offset, true); offset += 4;
        const originY = view.getFloat32(offset, true); offset += 4;
        const originZ = view.getFloat32(offset, true); offset += 4;
        const payloadSize = view.getUint32(offset, true); offset += 4;
        
        // Skip reserved bytes (to byte 64)
        offset = 64;

        // Allocate grid
        const totalVoxels = sizeX * sizeY * sizeZ;
        const grid = new Uint8Array(totalVoxels);

        // RLE decode
        let gridIdx = 0;
        const payloadEnd = offset + payloadSize;
        
        while (offset < payloadEnd && gridIdx < totalVoxels) {
            const value = view.getUint8(offset++);
            let count = view.getUint8(offset++);
            if (count === 0) count = 256; // 0 means 256
            
            for (let i = 0; i < count && gridIdx < totalVoxels; i++) {
                grid[gridIdx++] = value;
            }
        }

        console.log(`Loaded RLEVOX: ${sizeX}x${sizeY}x${sizeZ}, voxel=${voxelSize}m`);

        return new VoxelCollider({
            sizeX, sizeY, sizeZ,
            voxelSize,
            originX, originY, originZ,
            grid
        });
    }

    // ============================================================
    // Stella File Loader
    // ============================================================
    async function loadStellaFile(arrayBuffer) {
        const zip = await JSZip.loadAsync(arrayBuffer);
        
        // Read manifest
        const manifestFile = zip.file('manifest.json');
        if (!manifestFile) {
            throw new Error('No manifest.json found in .stella file');
        }
        const manifestJson = await manifestFile.async('string');
        const manifest = JSON.parse(manifestJson);
        
        console.log('Loaded manifest:', manifest);
        
        // Get first level
        const levels = manifest.levels || [];
        if (levels.length === 0) {
            throw new Error('No levels found in manifest');
        }
        
        const levelInfo = levels[0];
        const levelPath = `levels/${levelInfo.id}`;
        
        // Load level.json
        const levelJsonFile = zip.file(`${levelPath}/level.json`);
        let levelJson = null;
        if (levelJsonFile) {
            const levelJsonStr = await levelJsonFile.async('string');
            levelJson = JSON.parse(levelJsonStr);
            console.log('Level JSON:', levelJson);
        }
        
        // Load render.glb
        let renderGlb = null;
        const renderFile = zip.file(`${levelPath}/render.glb`);
        if (renderFile) {
            renderGlb = await renderFile.async('arraybuffer');
            console.log('Loaded render.glb:', renderGlb.byteLength, 'bytes');
        }
        
        // Load collision.rlevox
        let collisionData = null;
        const collisionFile = zip.file(`${levelPath}/collision.rlevox`);
        if (collisionFile) {
            const collisionBuffer = await collisionFile.async('arraybuffer');
            collisionData = parseRLEVOX(collisionBuffer);
            console.log('Loaded collision data');
        }
        
        return {
            manifest,
            levelInfo,
            levelJson,
            renderGlb,
            collisionData,
        };
    }

    // ============================================================
    // Three.js Setup
    // ============================================================
    function initThreeJS() {
        // Scene
        scene = new THREE.Scene();
        scene.background = new THREE.Color(0x87ceeb); // Sky blue
        
        // Camera
        camera = new THREE.PerspectiveCamera(
            CONFIG.fov,
            window.innerWidth / window.innerHeight,
            CONFIG.nearClip,
            CONFIG.farClip
        );
        
        // Renderer
        renderer = new THREE.WebGLRenderer({
            canvas: canvas,
            antialias: true,
        });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        // Lights
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(50, 100, 50);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        directionalLight.shadow.camera.near = 0.5;
        directionalLight.shadow.camera.far = 500;
        directionalLight.shadow.camera.left = -100;
        directionalLight.shadow.camera.right = 100;
        directionalLight.shadow.camera.top = 100;
        directionalLight.shadow.camera.bottom = -100;
        scene.add(directionalLight);
        
        // Ground plane (fallback if no collision)
        const groundGeometry = new THREE.PlaneGeometry(100, 100);
        const groundMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x808080,
            roughness: 0.8,
        });
        const ground = new THREE.Mesh(groundGeometry, groundMaterial);
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        ground.name = 'fallback-ground';
        scene.add(ground);
        
        // Fog for atmosphere
        scene.fog = new THREE.Fog(0x87ceeb, 50, 200);
        
        // Handle resize
        window.addEventListener('resize', onWindowResize);
    }

    function onWindowResize() {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }

    // ============================================================
    // Load GLB Model
    // ============================================================
    function loadGLBModel(arrayBuffer) {
        return new Promise((resolve, reject) => {
            const loader = new THREE.GLTFLoader();
            loader.parse(arrayBuffer, '', (gltf) => {
                const model = gltf.scene;
                model.traverse((child) => {
                    if (child.isMesh) {
                        child.castShadow = true;
                        child.receiveShadow = true;
                    }
                });
                scene.add(model);
                console.log('GLB model loaded');
                resolve(model);
            }, reject);
        });
    }

    // ============================================================
    // Input Handling
    // ============================================================
    function setupInputHandlers() {
        // Pointer lock
        clickToStart.addEventListener('click', () => {
            canvas.requestPointerLock();
        });
        
        canvas.addEventListener('click', () => {
            if (!isLocked) {
                canvas.requestPointerLock();
            }
        });
        
        document.addEventListener('pointerlockchange', () => {
            isLocked = document.pointerLockElement === canvas;
            clickToStart.classList.toggle('hidden', isLocked);
            crosshair.classList.toggle('visible', isLocked);
        });
        
        // Mouse movement
        document.addEventListener('mousemove', (e) => {
            if (!isLocked) return;
            
            player.rotation.y -= e.movementX * CONFIG.mouseSensitivity;
            player.rotation.x -= e.movementY * CONFIG.mouseSensitivity;
            
            // Clamp vertical rotation
            player.rotation.x = Math.max(-Math.PI / 2 + 0.01, 
                                         Math.min(Math.PI / 2 - 0.01, player.rotation.x));
        });
        
        // Keyboard
        document.addEventListener('keydown', (e) => {
            if (!isLocked) return;
            
            switch (e.code) {
                case 'KeyW': keys.forward = true; break;
                case 'KeyS': keys.backward = true; break;
                case 'KeyA': keys.left = true; break;
                case 'KeyD': keys.right = true; break;
                case 'Space': keys.jump = true; e.preventDefault(); break;
                case 'ShiftLeft':
                case 'ShiftRight': keys.run = true; break;
            }
        });
        
        document.addEventListener('keyup', (e) => {
            switch (e.code) {
                case 'KeyW': keys.forward = false; break;
                case 'KeyS': keys.backward = false; break;
                case 'KeyA': keys.left = false; break;
                case 'KeyD': keys.right = false; break;
                case 'Space': keys.jump = false; break;
                case 'ShiftLeft':
                case 'ShiftRight': keys.run = false; break;
            }
        });
    }

    // ============================================================
    // Physics & Movement
    // ============================================================
    function updatePlayer(deltaTime) {
        // Movement direction
        const moveDir = new THREE.Vector3();
        
        if (keys.forward) moveDir.z -= 1;
        if (keys.backward) moveDir.z += 1;
        if (keys.left) moveDir.x -= 1;
        if (keys.right) moveDir.x += 1;
        
        if (moveDir.length() > 0) {
            moveDir.normalize();
            
            // Apply rotation
            const yawQuat = new THREE.Quaternion();
            yawQuat.setFromAxisAngle(new THREE.Vector3(0, 1, 0), player.rotation.y);
            moveDir.applyQuaternion(yawQuat);
            
            // Apply speed
            const speed = CONFIG.moveSpeed * (keys.run ? CONFIG.runMultiplier : 1);
            moveDir.multiplyScalar(speed);
        }
        
        // Horizontal movement with collision
        const newPosX = player.position.x + moveDir.x * deltaTime;
        const newPosZ = player.position.z + moveDir.z * deltaTime;
        
        // Check X movement
        if (!collisionGrid || !collisionGrid.checkCapsuleCollision(
            newPosX, player.position.y - CONFIG.playerHeight + 0.1, 
            player.position.z, CONFIG.playerRadius, CONFIG.playerHeight - 0.2)) {
            player.position.x = newPosX;
        }
        
        // Check Z movement
        if (!collisionGrid || !collisionGrid.checkCapsuleCollision(
            player.position.x, player.position.y - CONFIG.playerHeight + 0.1,
            newPosZ, CONFIG.playerRadius, CONFIG.playerHeight - 0.2)) {
            player.position.z = newPosZ;
        }
        
        // Gravity
        if (!player.onGround) {
            player.velocity.y -= CONFIG.gravity * deltaTime;
        }
        
        // Jump
        if (keys.jump && player.onGround) {
            player.velocity.y = CONFIG.jumpVelocity;
            player.onGround = false;
        }
        
        // Vertical movement
        const newPosY = player.position.y + player.velocity.y * deltaTime;
        
        // Ground collision
        let groundHeight = 0;
        if (collisionGrid) {
            groundHeight = collisionGrid.getGroundHeight(player.position.x, player.position.z);
        }
        const feetHeight = groundHeight + CONFIG.playerHeight;
        
        if (newPosY <= feetHeight) {
            player.position.y = feetHeight;
            player.velocity.y = 0;
            player.onGround = true;
        } else {
            player.position.y = newPosY;
            player.onGround = false;
        }
        
        // Ceiling collision
        if (collisionGrid && collisionGrid.isPositionSolid(
            player.position.x, player.position.y, player.position.z)) {
            player.velocity.y = Math.min(0, player.velocity.y);
        }
        
        // Update camera
        camera.position.copy(player.position);
        camera.rotation.copy(player.rotation);
    }

    // ============================================================
    // UI Updates
    // ============================================================
    function updateUI() {
        // Position
        positionEl.textContent = `${player.position.x.toFixed(2)}, ${player.position.y.toFixed(2)}, ${player.position.z.toFixed(2)}`;
        
        // FPS
        frameCount++;
        const now = performance.now();
        if (now - lastFpsUpdate >= 1000) {
            currentFps = Math.round(frameCount * 1000 / (now - lastFpsUpdate));
            frameCount = 0;
            lastFpsUpdate = now;
            fpsEl.textContent = currentFps;
        }
    }

    // ============================================================
    // Animation Loop
    // ============================================================
    let lastTime = performance.now();
    
    function animate() {
        requestAnimationFrame(animate);
        
        const now = performance.now();
        const deltaTime = Math.min((now - lastTime) / 1000, 0.1); // Cap delta
        lastTime = now;
        
        if (isLocked) {
            updatePlayer(deltaTime);
        }
        
        updateUI();
        renderer.render(scene, camera);
    }

    // ============================================================
    // VS Code Message Handling
    // ============================================================
    function setupVSCodeMessaging() {
        // Check if running in VS Code webview
        if (typeof acquireVsCodeApi !== 'undefined') {
            const vscode = acquireVsCodeApi();
            
            window.addEventListener('message', async (event) => {
                const message = event.data;
                
                switch (message.type) {
                    case 'load':
                        try {
                            showLoading(true);
                            const arrayBuffer = Uint8Array.from(atob(message.data), c => c.charCodeAt(0)).buffer;
                            await loadWorld(arrayBuffer);
                            showLoading(false);
                        } catch (error) {
                            showError(error.message);
                        }
                        break;
                }
            });
            
            // Request file data
            vscode.postMessage({ type: 'ready' });
        }
    }

    // ============================================================
    // Main Functions
    // ============================================================
    async function loadWorld(arrayBuffer) {
        stellaData = await loadStellaFile(arrayBuffer);
        
        // Update UI
        worldNameEl.textContent = stellaData.manifest.name || 'Untitled World';
        levelNameEl.textContent = stellaData.levelInfo.name || stellaData.levelInfo.id;
        
        // Load collision
        if (stellaData.collisionData) {
            collisionGrid = stellaData.collisionData;
        }
        
        // Load render model
        if (stellaData.renderGlb) {
            await loadGLBModel(stellaData.renderGlb);
            
            // Remove fallback ground
            const fallbackGround = scene.getObjectByName('fallback-ground');
            if (fallbackGround) {
                scene.remove(fallbackGround);
            }
        }
        
        // Set spawn position
        let spawnPos = { x: 0, y: CONFIG.playerHeight, z: 0 };
        if (stellaData.levelJson && stellaData.levelJson.spawn) {
            spawnPos = stellaData.levelJson.spawn;
        }
        player.position.set(spawnPos.x, spawnPos.y + CONFIG.playerHeight, spawnPos.z);
        
        console.log('World loaded, spawn:', spawnPos);
    }

    function showLoading(show) {
        loadingEl.classList.toggle('hidden', !show);
        if (show) {
            clickToStart.classList.add('hidden');
        }
    }

    function showError(message) {
        loadingEl.classList.add('hidden');
        errorTextEl.textContent = message;
        errorEl.classList.remove('hidden');
    }

    // ============================================================
    // Initialization
    // ============================================================
    async function init() {
        try {
            initThreeJS();
            setupInputHandlers();
            setupVSCodeMessaging();
            
            showLoading(false);
            animate();
            
            console.log('Stella Viewer initialized');
        } catch (error) {
            console.error('Init error:', error);
            showError(error.message);
        }
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
