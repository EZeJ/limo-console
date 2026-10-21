# 开发说明

[English](CONTRIBUTING.md)

使用 Python 3.10+ 和 Node.js 18+，在虚拟环境中安装 `requirements-dev.txt`。当前单元测试与模拟预览不需要 ROS。

```sh
python -m unittest discover -s tests -v
node tests/test_i18n.js
node --check robot/web/app.js
node --check robot/web/i18n.js
python -m compileall -q robot scripts companion harness
bash -n scripts/install.sh scripts/tunnel.sh robot/manage.sh robot/env.sh
python scripts/preview.py
```

项目没有前端构建工具。修改 `robot/web/` 后刷新预览即可。截图应来自预览，它不包含真实相机图像、地图或机器人连接。检查中英文、窄屏、键盘焦点和滑块/数值联动。切换语言不应发送运动指令，也不应丢弃尚未保存的速度输入。

英文原文和中文翻译集中放在 `messages.js`。动态文本使用 `t()`；HTML 使用 `data-i18n` 或其 aria、alt、placeholder 变体。服务端的人类可读消息使用英文，API 字段与枚举保持稳定。外部 ROS 进程的技术诊断可能保留原始语言。

驾驶逻辑变化需要有意义的保护测试，包括超时、锁定、双向限速及导航独立限速。不要将真实运动作为自动单元测试的一部分。机器人集成测试应在另行准备的可控环境中进行，并由能随时停车的操作者监看。

提交前检查暂存文件。运行地图、数据包、照片、日志、状态文件、凭据和个人连接设置不属于本仓库。示例和截图不要加入真实设备地址，也不要公开正在运行的机器人接口。

拉取请求应说明具体行为变化、已执行的验证，以及仍依赖的硬件条件。修改集成配置时保留上游许可证说明。

电脑端数据页面在服务启动时加载；修改后应在结束录制时重启电脑端服务，再刷新浏览器。可用 `--browse-only --port 18767` 启动独立开发实例。
