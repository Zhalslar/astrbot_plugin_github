
<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_github?name=astrbot_plugin_github&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_github

_✨ [astrbot](https://github.com/AstrBotDevs/AstrBot) github插件 ✨_  

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)

</div>

## 🤝 介绍

对接github的所有接口，实现丰富多彩的功能

## 📦 安装

在astrbot的插件市场搜索astrbot_plugin_github，点击安装，等待完成即可。如果安装失败还可以直接克隆源码到插件文件夹：

```bash
# 克隆仓库到插件目录
cd /AstrBot/data/plugins
git clone https://github.com/Zhalslar/astrbot_plugin_search_video

# 控制台重启AstrBot
```

## ⚙️ 配置

### 插件配置

请在astrbot面板配置，插件管理 -> astrbot_plugin_github -> 操作 -> 插件配置

| 配置项                    | 必填/选填 | 说明                                                                                     |
|-------------------------|-----------|----------------------------------------------------------------------------------------|
| `repositories`          | 必填      | 要监控的 GitHub 仓库列表，支持完整 URL（如 `https://github.com/owner/repo`）或短格式（如 `owner/repo`），仅填owner表示监控所有owner的仓库。 |
| `target_sessions`       | 必填      | 接收通知的目标会话 unified_msg_origin 列表。<br>获取方式：发送消息后查看日志中对应的 unified_msg_origin。   |
| `github_token`          | 强烈推荐  | GitHub 的 Personal Access Token，用于提高请求上限（认证后可达 5000 次/小时）。<br>仅需授予 **Metadata: Read** 权限。 |
| `check_interval`        | 可选      | 检查 GitHub 更新的时间间隔（单位：秒）。<br>建议：有 Token 时设为 30~60 秒，无 Token 时设为 120 秒以上。     |
| `enable_startup_notification` | 可选      | 插件启动时是否发送通知。默认为 `true`。<br>注意：若要显示详细用户信息，需配置 GitHub Token。          |

| /     | 。。。  |

## ⌨️ 使用说明

### 指令表

|     命令      |      说明       |
|:-------------:|:-----------------------------:|
| repositories   | 必填  | 要监控的GitHub仓库列表

### 示例图

## 👥 贡献指南

- 🌟 Star 这个项目！（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码

## 📌 注意事项

1. **GitHub API限制**: GitHub API对未认证请求有速率限制，建议不要将检查间隔设置过小
2. **网络连接**: 需要确保AstrBot服务器能够访问GitHub API
3. **会话ID**: 确保正确配置target_sessions，否则无法收到通知
4. **仓库格式**: 确保仓库URL格式正确，支持公开仓库的监控
5. **交流群**: 想第一时间得到反馈的可以来作者的插件反馈群（QQ群）：460973561（不点star不给进）
