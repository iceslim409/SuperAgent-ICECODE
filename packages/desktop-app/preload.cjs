'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('icecodeDesktop', {
  getServerUrl: () => ipcRenderer.invoke('get-server-url'),
  getVersion: () => ipcRenderer.invoke('get-version'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  showMessage: (opts) => ipcRenderer.invoke('show-message', opts),
  platform: process.platform,
});
