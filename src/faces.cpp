// ============================================================
//  faces.cpp — 表盘注册表 + FacesAcc 实现
// ============================================================
#include "face.h"
#include "faces_access.h"

#include <string.h>

// 表盘声明（各 face_*.cpp 提供）
WatchFace* createFaceTest();
WatchFace* createFaceClock();
WatchFace* createFacePlasma();
WatchFace* createFaceRemote();

namespace Faces {

WatchFace* gList[MAX_FACES] = { nullptr };
int        gCount = 0;

void add(WatchFace* f) {
  if (gCount < MAX_FACES && f) gList[gCount++] = f;
}

WatchFace* byIndex(int i) {
  if (i < 0) i = 0;
  if (i >= gCount) i = gCount - 1;
  return (i >= 0 && gCount > 0) ? gList[i] : nullptr;
}

WatchFace* byId(const char* id) {
  for (int i = 0; i < gCount; ++i)
    if (gList[i] && strcmp(gList[i]->id(), id) == 0) return gList[i];
  return nullptr;
}

void registerBuiltins() {
  add(createFaceTest());     // 0 测试图案（接线验证）
  add(createFaceClock());    // 1 像素时钟（默认）
  add(createFacePlasma());   // 2 等离子动画
  add(createFaceRemote());   // 3 远程表盘（小程序 BLE 推送，见 docs/face-push-protocol.md）
}

}  // namespace Faces

namespace FacesAcc {
int gCurrent = 1;   // 默认像素时钟
int gDesired = -1;

void request(int idx) {
  if (idx < 0) { gDesired = -1; return; }
  // 循环切换；gCount>0 保证
  int n = Faces::gCount;
  gDesired = (n > 0) ? (idx % n) : -1;
}

int current() { return gCurrent; }
}  // namespace FacesAcc
