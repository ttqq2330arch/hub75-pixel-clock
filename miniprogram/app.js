const ble = require('./utils/ble.js')
const facesApi = require('./utils/faces.js')

App({
  globalData: {
    ble: ble,
    device: null,          // { deviceId, name }
    faces: [],             // 本地表盘清单（来自 faces-index.json）
  },
  onLaunch() {
    this.globalData.faces = facesApi.list()
    // 打开蓝牙适配器（BLE 一切操作的前置；失败静默——真机没开蓝牙时
    // 由具体页面在调用时报错，这里不阻塞启动）
    ble.init().catch(() => {})
  },
})
