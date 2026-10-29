// ============================================================
//  face.h — 表盘抽象接口
//  每个表盘 = 一个 WatchFace 子类，编译期注册进注册表。
//  后续 BLE 下发的外置表盘（见 docs/watchface-format.md）
//  走独立的数据驱动渲染，不经过这个编译期接口。
// ============================================================
#pragma once

#include <stdint.h>
#include "config.h"

#ifdef ARDUINO
class MatrixPanel_I2S_DMA;
#endif

// 表盘运行时上下文：所有表盘共享的显示/时间/配置入口
struct FaceEnv {
  uint32_t nowMs;      // millis()
  uint32_t nowEpoch;   // Unix 时间戳（NTP 或 BLE 校准后有效）
  bool     epochValid; // 网络时间是否已同步过
  float    tempC;      // 传感器温度，NAN=无传感器
  float    humi;       // 湿度，NAN=无传感器
};

class WatchFace {
public:
  WatchFace(const char* id, const char* name) : _id(id), _name(name) {}
  virtual ~WatchFace() {}

  const char* id()   const { return _id; }
  const char* name() const { return _name; }

  // 被选中时调用（加载配置/重置动画相位）
  virtual void onSelect() {}
  // 每帧调用（纯逻辑，不直接画）
  virtual void tick(const FaceEnv& env) = 0;
  // 每帧调用（渲染到 framebuffer）
  virtual void render() = 0;

protected:
  const char* _id;
  const char* _name;
};

// 表盘注册表（faces.cpp 实现）
namespace Faces {
  static const int MAX_FACES = 8;
  extern WatchFace* gList[MAX_FACES];
  extern int        gCount;
  void add(WatchFace* f);
  WatchFace* byIndex(int i);   // i 越界返回 nullptr
  WatchFace* byId(const char* id);
  void registerBuiltins();     // 注册内置表盘（faces.cpp 定义）
}
