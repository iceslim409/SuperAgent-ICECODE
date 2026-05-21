'use strict';
if (process.env.ELECTRON_RUN_AS_NODE) {
  console.error('Error: Do not run this script with ELECTRON_RUN_AS_NODE=1.\nUse: npm start');
  process.exit(1);
}
const { app, BrowserWindow, Menu, Tray, nativeImage, shell, ipcMain, dialog } = require('electron');
const path = require('node:path');
const http = require('node:http');
const fs = require('node:fs');

const SERVER_URL = 'http://localhost:13210';
const WEB_UI_PATH = path.join(__dirname, '..', 'web-ui', 'index.html');
const IS_DEV = process.argv.includes('--dev');

let mainWindow = null;
let tray = null;
let serverReady = false;

// ── Check if ICECODE server is up ──────────────────────────────────────────
function checkServer(retries, onReady) {
  if (retries === undefined) retries = 30;
  const req = http.get(`${SERVER_URL}/health`, (res) => {
    if (res.statusCode === 200) {
      serverReady = true;
      onReady(true);
    } else {
      retry();
    }
  });
  req.on('error', retry);
  req.setTimeout(1500, () => { req.destroy(); retry(); });

  let attempts = 0;
  function retry() {
    attempts++;
    if (attempts >= retries) {
      onReady(false);
      return;
    }
    setTimeout(() => checkServer(retries - attempts, onReady), 1000);
  }
}

// ── Create main window ─────────────────────────────────────────────────────
function createWindow(useServer) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 800,
    minHeight: 600,
    backgroundColor: '#0d1117',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    title: 'ICECODE Super-Agent Network',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
    icon: path.join(__dirname, 'icon.png'),
    show: false,
  });

  const loadUrl = useServer ? SERVER_URL : `file://${WEB_UI_PATH}`;
  mainWindow.loadURL(loadUrl);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (IS_DEV) mainWindow.webContents.openDevTools({ mode: 'detach' });
  });

  mainWindow.webContents.on('did-fail-load', () => {
    if (useServer) {
      mainWindow.loadURL(`file://${WEB_UI_PATH}`);
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url);
    return { action: 'deny' };
  });

  return mainWindow;
}

// ── Tray ───────────────────────────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, 'icon.png');
  let icon;
  if (fs.existsSync(iconPath)) {
    icon = nativeImage.createFromPath(iconPath);
  } else {
    icon = nativeImage.createEmpty();
  }
  if (icon.isEmpty()) {
    icon = nativeImage.createFromDataURL(
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAbwAAAG8B8aLcQwAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAB2SURBVDiNY2CgBuD/DxgYGBiI0c/AwMDACMNgBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYAAD4EBgUAAAAASUVORK5CYII='
    );
  }

  tray = new Tray(icon);
  const menu = Menu.buildFromTemplate([
    { label: 'ICECODE Super-Agent Network', enabled: false },
    { type: 'separator' },
    { label: 'Show Window', click: () => { if (mainWindow) mainWindow.show(); else createWindow(serverReady); } },
    { label: 'Open in Browser', click: () => shell.openExternal(SERVER_URL) },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]);
  tray.setToolTip('ICECODE Super-Agent Network');
  tray.setContextMenu(menu);
  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
    }
  });
}

// ── App menu ───────────────────────────────────────────────────────────────
function buildMenu() {
  const template = [
    {
      label: 'ICECODE',
      submenu: [
        { label: 'About ICECODE', role: 'about' },
        { type: 'separator' },
        { label: 'Reload', accelerator: 'CmdOrCtrl+R', click: () => mainWindow && mainWindow.reload() },
        { label: 'Open DevTools', accelerator: 'F12', click: () => mainWindow && mainWindow.webContents.openDevTools() },
        { type: 'separator' },
        { label: 'Quit', accelerator: 'CmdOrCtrl+Q', role: 'quit' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { label: 'Back', accelerator: 'Alt+Left', click: () => mainWindow && mainWindow.webContents.goBack() },
        { label: 'Forward', accelerator: 'Alt+Right', click: () => mainWindow && mainWindow.webContents.goForward() },
        { type: 'separator' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { role: 'resetZoom' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' }, { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ── Bootstrap ──────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  ipcMain.handle('get-server-url', () => SERVER_URL);
  ipcMain.handle('get-version', () => app.getVersion());
  ipcMain.handle('open-external', (_, url) => shell.openExternal(url));
  ipcMain.handle('show-message', (_, opts) => dialog.showMessageBox(mainWindow, opts));

  buildMenu();
  createTray();

  const splash = new BrowserWindow({
    width: 420,
    height: 260,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    backgroundColor: '#0d1117',
    webPreferences: { nodeIntegration: false },
  });

  splash.loadURL(`data:text/html,
    <html><head><style>
      body{background:#0d1117;color:#e6edf3;font-family:system-ui;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;margin:0}
      h2{color:#58a6ff;font-size:22px;margin-bottom:8px}
      p{color:#8b949e;font-size:13px}
      .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#58a6ff;animation:pulse 1s infinite alternate}
      @keyframes pulse{from{opacity:.3}to{opacity:1}}
    </style></head>
    <body>
      <h2>ICECODE</h2>
      <p>Super-Agent Network</p>
      <br>
      <span class="dot"></span>&nbsp;
      <span class="dot" style="animation-delay:.2s"></span>&nbsp;
      <span class="dot" style="animation-delay:.4s"></span>
      <br><br>
      <p style="font-size:11px">Connecting to agent server...</p>
    </body></html>
  `);

  checkServer(20, (ready) => {
    serverReady = ready;
    splash.close();
    createWindow(ready);
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow(serverReady);
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
