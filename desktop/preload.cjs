const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("netwatchDesktop", {
  status: () => ipcRenderer.invoke("netwatch:status"),
  restart: () => ipcRenderer.invoke("netwatch:restart"),
  openDashboard: () => ipcRenderer.invoke("netwatch:open-dashboard"),
  onStartup: (callback) => ipcRenderer.on("desktop-state", (_event, state) => callback(state)),
});
