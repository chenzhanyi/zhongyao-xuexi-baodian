# 中药学习宝典 Android 壳

纯 WebView 壳，打开即加载 `https://zhongyi.9yzs.cn/中药学习宝典.html`（手机版主程序），无引导页、无本地内容。

## 特性

- 全屏 WebView，启用 JS / DOM Storage（localStorage 正常工作，收藏、背诵进度、脉诊记录均保存）
- 下拉刷新
- 系统返回键走网页历史
- 无网络时显示重试遮罩
- 自适应屏幕旋转、输入法
- 状态栏颜色与站点一致（墨绿 #2f5d3a）

## 获取 APK

代码推送到 `main` 后，GitHub Actions 自动构建：

1. 仓库页面 → **Actions** → **Build Android APK**
2. 选最新一次成功的 run
3. 底部 Artifacts 下载 `zhongyi-debug-apk.zip`，解压得到 `app-debug.apk`
4. 手机安装（需允许"安装未知来源应用"）

debug 签名可直接安装使用。如需上架应用商店再做 release 签名。

## 本地构建

需要 JDK 17 + Android SDK（platform 34、build-tools 34）：

```bash
cd android-app
gradle wrapper --gradle-version 8.9   # 首次
./gradlew assembleDebug
# 产物：app/build/outputs/apk/debug/app-debug.apk
```

## 改服务器地址

`app/src/main/java/cn/zyzs/zhongyi/MainActivity.java` 顶部的 `HOME_URL`。
