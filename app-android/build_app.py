#!/usr/bin/env python3
"""
像素时钟 APP — 构建脚本（Windows）

一键编译 Android APK。自动处理：
- 定位 JDK（优先用完整 JDK，没有则用 JRE —— Gradle 够用）
- 定位 Android SDK
- 中文路径问题：Kotlin 编译器在中文路径下会乱码，
  自动把工程复制到纯 ASCII 临时目录再构建，构建完再把 APK 搬回来

用法:
    python build_app.py                 # 构建 debug APK
    python build_app.py --release       # 构建 release APK（需先配签名）
    python build_app.py --install       # 构建后用 adb 安装到已连接设备
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or r"F:\android-toolchain\android-sdk"
JRE_CANDIDATES = [
    r"F:\Tools\java\jdk-21.0.12.1+1-jre",
    r"F:\Tools\java25\jdk-25.0.4.1+1-jre",
]
GRADLE_CANDIDATES = [
    r"F:\android-toolchain\gradle-8.7\bin\gradle.bat",
    os.path.join(HERE, "gradle", "bin", "gradle.bat"),
]


def find_java_home():
    jh = os.environ.get("JAVA_HOME")
    if jh and os.path.isdir(jh):
        return jh
    for c in JRE_CANDIDATES:
        if os.path.isdir(c):
            return c
    return None


def find_gradle():
    for c in GRADLE_CANDIDATES:
        if os.path.isfile(c):
            return c
    return None


def has_nonascii(path):
    return any(ord(ch) > 127 for ch in path)


def build(release=False, install=False):
    java_home = find_java_home()
    gradle = find_gradle()
    if not java_home:
        print("[x] 找不到 JDK/JRE。请安装 JDK 17+ 或设置 JAVA_HOME")
        sys.exit(1)
    if not gradle:
        print("[x] 找不到 Gradle。请安装 Gradle 8.7+ 或设置路径")
        sys.exit(1)
    if not os.path.isdir(SDK):
        print(f"[x] 找不到 Android SDK: {SDK}")
        sys.exit(1)

    print(f"[i] JAVA_HOME = {java_home}")
    print(f"[i] Gradle    = {gradle}")
    print(f"[i] SDK       = {SDK}")

    task = "assembleRelease" if release else "assembleDebug"

    # 中文路径 → 复制到 ASCII 临时目录构建
    workdir = HERE
    tmp = None
    if has_nonascii(HERE):
        tmp = tempfile.mkdtemp(prefix="pixelclock_build_")
        print(f"[i] 路径含中文，复制到临时 ASCII 目录构建: {tmp}")
        for item in ["app", "gradle", "build.gradle.kts", "settings.gradle.kts", "gradle.properties"]:
            src = os.path.join(HERE, item)
            if os.path.exists(src):
                if os.path.isdir(src):
                    shutil.copytree(src, os.path.join(tmp, item), dirs_exist_ok=True,
                                    ignore=shutil.ignore_patterns("build", ".gradle"))
                else:
                    shutil.copy2(src, os.path.join(tmp, item))
        workdir = tmp

    env = dict(os.environ)
    env["JAVA_HOME"] = java_home
    env["ANDROID_HOME"] = SDK
    env["ANDROID_SDK_ROOT"] = SDK
    env["GRADLE_USER_HOME"] = env.get("GRADLE_USER_HOME", r"F:\android-toolchain\gradle-home")
    env["PATH"] = os.path.join(java_home, "bin") + os.pathsep + env.get("PATH", "")

    print(f"[i] 开始构建: {task}")
    cmd = [gradle, "--no-daemon", task]
    r = subprocess.run(cmd, cwd=workdir, env=env)
    if r.returncode != 0:
        print("[x] 构建失败")
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(r.returncode)

    # 产物搬回
    apk_name = "app-release.apk" if release else "app-debug.apk"
    built = os.path.join(workdir, "app", "build", "outputs", "apk",
                         "release" if release else "debug", apk_name)
    final = os.path.join(HERE, "像素时钟-v1.0.0.apk" if not release else "像素时钟-v1.0.0-release.apk")
    if os.path.exists(built):
        shutil.copy2(built, final)
        print(f"[✓] APK: {final}  ({os.path.getsize(final)} bytes)")

    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)

    if install:
        adb = os.path.join(SDK, "platform-tools", "adb.exe")
        if os.path.exists(adb):
            print("[i] 安装到设备…")
            subprocess.run([adb, "install", "-r", final])
        else:
            print("[!] 找不到 adb，跳过安装")


if __name__ == "__main__":
    build(
        release="--release" in sys.argv,
        install="--install" in sys.argv,
    )
