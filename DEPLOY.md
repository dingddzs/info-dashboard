# 信息源监控看板 - Vercel 部署指南

## 部署步骤

### 1. 创建 GitHub 仓库
1. 访问 https://github.com/new
2. 仓库名设为 `info-dashboard` 或其他名字
3. 不要勾选 "Add a README file"
4. 点击 "Create repository"

### 2. 本地初始化并推送
在命令行执行：
```bash
cd D:\ai\knowledge\dashboard

git init
git add .
git commit -m "Initial commit"

# 替换为你的仓库地址
git remote add origin https://github.com/你的用户名/info-dashboard.git
git push -u origin main
```

### 3. 部署到 Vercel
1. 访问 https://vercel.com
2. 使用 GitHub 账号登录
3. 点击 "New Project"
4. 选择刚才创建的仓库
5. 点击 "Deploy"

### 4. 手机访问
部署完成后，Vercel 会给你一个 URL（如 `xxx.vercel.app`）
- 在手机上打开这个网址
- 点击浏览器菜单 → "添加到主屏幕"
- 就会像 App 一样显示了！

## 注意事项
- Vercel 免费版每次部署会重置数据（数据库重置）
- 如果需要持久化数据，需要升级付费版或使用云数据库
- 本地运行版本数据会保存在本地，不受影响
