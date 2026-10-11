# 可用工具

## 设备管理

| 工具 | 描述 |
|------|------|
| GetDevices | 列出所有智能家居设备，可按设备类型筛选（如"thermostat"、"light"、"lock"、"camera"） |
| ControlDevice | 控制智能设备，执行操作（如开关、设置温度等） |
| GetScenes | 列出可用的智能家居场景 |
| ExecuteScene | 通过场景ID激活预定义场景 |

## 使用说明

- 控制设备前，先使用 GetDevices 查看可用设备及其ID
- ControlDevice 需要 device_id 和 action 参数；部分操作需要额外参数（如温控器设置温度时需提供 temperature 参数）
- GetScenes 可查看预定义的自动化场景
- ExecuteScene 激活一个可能同时控制多个设备的场景