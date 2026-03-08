# 信息源监控看板 - 项目说明

## 项目概述
一个用于监控B站、RSS博客、小红书、知乎、微信公众号等信息源的工具，同时具备人脉管理功能（联系人、生日提醒、待办事项）。

## 快速启动

### 本地运行（Windows）
```bash
# 方法1: 双击运行
D:\ai\knowledge\启动看板.bat

# 方法2: 命令行运行
cd D:\ai\knowledge\dashboard
python app.py
# 访问 http://localhost:8080
```

### 云端运行（手机/外网访问）
- **Render地址**: https://info-dashboard-4c8c.onrender.com/
- **注意**: 免费版15分钟无访问会休眠，需等待唤醒

## 部署更新

代码托管在GitHub: https://github.com/dingddzs/info-dashboard

每次修改后会自动部署到Render，需等待1-2分钟。

## 功能列表

### 已实现
- [x] 多平台信源监控（B站、RSS、小红书、知乎、微信公众号）
- [x] 今日更新展示
- [x] 主题切换（可爱风、少女风、赛博朋克风、二次元、黑客风）
- [x] 人脉管理（添加联系人、性别、生日、身份、备忘）
- [x] 待办事项管理
- [x] 生日/待办提醒（10天内）
- [x] 提醒打勾取消
- [x] 侧边栏可收起/展开
- [x] 响应式设计（支持手机）
- [x] 信源添加/删除/启用禁用
- [x] 首页移除"添加信源"按钮

### 待处理/已知问题
- [ ] 本地与Render数据不同步（两者独立）
- [ ] 今日更新有时区问题（服务器时区差异）

## 技术栈
- Python (后端)
- SQLite (数据库)
- HTML/CSS/JS (前端)
- Vercel/Render (云端部署)

## 目录结构
```
D:\ai\knowledge\
├── 启动看板.bat          # Windows快速启动脚本
└── dashboard/
    ├── app.py           # 主应用
    ├── database.py      # 数据库模块
    ├── config_manager.py # 配置管理
    ├── fetchers.py      # 抓取模块
    ├── summarizer.py    # AI总结
    ├── dashboard.html   # 前端页面
    ├── themes/          # 主题CSS
    └── sources.json     # 信源配置
```

## 下次工作方向
1. 解决本地与Render数据同步问题
2. 完善信源抓取（小红书、知乎、微信公众号需额外开发）
3. 优化手机端体验

## 联系方式
如有问题，可通过GitHub仓库提交issue。
