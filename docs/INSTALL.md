# 安装指南

## 环境要求

- Windows 10/11。
- Python 3.10+，命令名可用 `python`。
- Adobe Photoshop 或 Photoshop Beta。
- Codex 桌面端支持本地插件和 MCP。

## 安装方式

### 克隆到 Codex 插件目录

```powershell
cd $env:USERPROFILE\.codex\plugins
git clone https://github.com/your-name/photoshop-beta-control.git
```

### 或复制到项目插件目录

```powershell
Copy-Item -Recurse "C:\path\to\photoshop-beta-control" ".\plugins\photoshop-beta-control"
```

## 检查 Photoshop 连接

```powershell
cd $env:USERPROFILE\.codex\plugins\photoshop-beta-control
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\photoshop_bridge.ps1 -Action find_progids
```

如果能看到 `Photoshop.Application...` 相关 ProgID，说明注册表里能找到 Photoshop。

继续检查状态：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\photoshop_bridge.ps1 -Action status
```

如果 Photoshop 第一次启动较慢，可以先手动打开 Photoshop，再重试。

## 常见问题

### 找不到 Photoshop COM

先运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\photoshop_bridge.ps1 -Action find_progids
```

如果找到了可用 ProgID，在启动 Codex 前设置：

```powershell
$env:PHOTOSHOP_PROG_ID = "Photoshop.Application.2026"
```

### PowerShell 执行策略拦截

本项目命令默认使用：

```powershell
-ExecutionPolicy Bypass
```

这只影响当前进程，不会永久修改系统策略。

### Codex 看不到插件

确认目录结构是：

```text
photoshop-beta-control/
  .codex-plugin/plugin.json
  .mcp.json
  scripts/mcp_server.py
  scripts/photoshop_bridge.ps1
  skills/photoshop-control/SKILL.md
```

然后重启 Codex 或重新加载插件。
