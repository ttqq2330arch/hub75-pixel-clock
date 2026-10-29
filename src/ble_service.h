// ============================================================
//  ble_service.h — BLE 服务（小程序/App 侧接口原型）
//  服务:  4f8c0000-1f0a-4c1e-9b2d-000000000001
//  特征:
//    TIME (write)      uint32 LE 秒 → 设置时间
//    FACE (write)      uint8 → 切换表盘索引
//    TIME_READ(read)   uint32 LE 秒 → 读当前时间
//    DATA (write)      BLE 表盘数据分包下行（里程碑2：watchface-format.md）
// ============================================================
#pragma once

#include <stdint.h>

namespace Ble {

// faceCtr: FACE 特征写入回调（idx: 0~N-1）
typedef void (*FaceSelectFn)(uint8_t idx);

void begin(FaceSelectFn faceSel);
void loop();

}  // namespace Ble
