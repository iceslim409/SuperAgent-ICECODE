import * as em from 'electron/main';
const me = em['module.exports'];
console.log('module.exports type:', typeof me);
console.log('module.exports keys:', me ? Object.keys(me).slice(0,15).join(', ') : 'null');
console.log('module.exports.app:', me && typeof me.app);
console.log('module.exports.BrowserWindow:', me && typeof me.BrowserWindow);
process.exit(0);
