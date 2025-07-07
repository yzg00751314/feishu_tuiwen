# 飞书小说下载系统 - 简化部署指南

专为已部署 MySQL 数据库的服务器设计的自动化部署方案

## 📋 系统概述

- **功能**: 从飞书多维表格拉取数据并自动下载文件
- **数据流程**: 飞书表格 → first_table → second_table → 文件下载
- **调度**: 每天早上8点自动执行完整流程
- **存储**: 文件保存到 `/home/feishu`
- **日志**: 详细的执行日志记录

## 🔄 核心功能

### 1. 数据拉取 (`fetch`)
- 从飞书多维表格获取最新数据
- 自动解析表格字段并保存到 `first_table`
- 支持分页获取大量数据

### 2. 数据同步 (`sync`)
- 将 `first_table` 新数据同步到 `second_table`
- 自动去重，只处理新增和更新的记录
- 支持断点续传

### 3. 文件下载 (`download`)
- 根据 `second_table` 中的文件token下载文件
- 自动创建项目文件夹
- 下载成功后更新状态标记

### 4. 完整流程 (`daily`)
- 按顺序执行：拉取 → 同步 → 下载
- 每天定时自动执行
- 完整的错误处理和日志记录

## 🚀 一键部署

### 1. 上传文件到服务器

将 `linux_bushu` 文件夹中的所有文件上传到服务器的临时目录：

```bash
# 例如上传到 /tmp/feishu_deploy
mkdir -p /tmp/feishu_deploy
cd /tmp/feishu_deploy
# 上传所有 .py 文件、.txt 文件、.sh 文件
```

### 2. 执行一键安装

```bash
# 进入部署目录
cd /tmp/feishu_deploy

# 给安装脚本执行权限
chmod +x install_cron.sh

# 执行安装（会提示配置数据库信息）
./install_cron.sh
```

### 3. 配置数据库信息

安装过程中会自动创建配置文件，需要编辑以下信息：

```bash
# 编辑配置文件
nano /opt/feishu/.env
```

修改以下配置项：
```env
# 数据库配置（如果是本地MySQL，保持localhost即可）
DB_HOST=localhost
DB_USER=你的数据库用户名
DB_PASSWORD=你的数据库密码
DB_DATABASE=makevideo

# 飞书API配置
FEISHU_APP_ID=你的飞书应用ID
FEISHU_APP_SECRET=你的飞书应用密钥
```

## ✅ 验证部署

### 检查定时任务

```bash
# 查看已设置的定时任务
crontab -l

# 应该看到类似这样的输出：
# 0 8 * * * /opt/feishu/run_daily.sh
```

### 手动测试运行

```bash
# 测试从飞书拉取数据
cd /opt/feishu
source venv/bin/activate
python3 cron_deployment.py fetch

# 测试数据同步
python3 cron_deployment.py sync

# 测试文件下载
python3 cron_deployment.py download

# 测试完整流程（推荐）
python3 cron_deployment.py daily
```

## 📊 监控和维护

### 查看日志

```bash
# 查看今天的执行日志
tail -f /var/log/feishu/cron.log

# 查看最近的日志
tail -n 100 /var/log/feishu/cron.log

# 查看特定日期的日志
grep "2024-01-15" /var/log/feishu/cron.log

# 查看错误日志
grep -i error /var/log/feishu/cron.log
```

### 查看下载文件

```bash
# 查看所有下载的项目
ls -la /home/feishu/

# 查看特定项目的文件
ls -la /home/feishu/项目名称_时间戳/

# 统计下载的文件数量
find /home/feishu -type f | wc -l
```

### 系统状态检查

```bash
# 检查服务是否在明天会执行
crontab -l | grep feishu

# 检查磁盘空间
df -h /home/feishu

# 检查日志大小
du -h /var/log/feishu/
```

## 🔧 常见操作

### 手动执行任务

```bash
# 从飞书拉取最新数据
cd /opt/feishu && source venv/bin/activate && python3 cron_deployment.py fetch

# 立即执行一次完整任务（拉取+同步+下载）
cd /opt/feishu && source venv/bin/activate && python3 cron_deployment.py daily

# 清理测试数据
cd /opt/feishu && source venv/bin/activate && python3 cron_deployment.py clean
```

### 修改执行时间

```bash
# 编辑定时任务
crontab -e

# 修改时间（例如改为下午2点）
# 0 14 * * * /opt/feishu/run_daily.sh
```

### 停用定时任务

```bash
# 编辑 crontab
crontab -e

# 在任务行前加 # 注释掉
# # 0 8 * * * /opt/feishu/run_daily.sh
```

### 完全卸载

```bash
# 删除定时任务
crontab -e  # 删除相关行

# 删除项目文件
sudo rm -rf /opt/feishu

# 删除日志
sudo rm -rf /var/log/feishu

# 删除下载目录（注意：会删除所有下载的文件）
sudo rm -rf /home/feishu
```

## 🛠️ 故障排查

### 任务没有执行

1. **检查 cron 服务**:
   ```bash
   sudo systemctl status cron
   sudo systemctl start cron  # 如果未启动
   ```

2. **检查任务权限**:
   ```bash
   ls -la /opt/feishu/run_daily.sh  # 确保有执行权限
   ```

3. **查看系统日志**:
   ```bash
   sudo journalctl -u cron -f
   ```

### 数据库连接失败

1. **检查 MySQL 服务**:
   ```bash
   sudo systemctl status mysql
   ```

2. **测试数据库连接**:
   ```bash
   mysql -h localhost -u 用户名 -p数据库名
   ```

3. **检查配置文件**:
   ```bash
   cat /opt/feishu/.env | grep DB_
   ```

### 文件下载失败

1. **检查网络连接**:
   ```bash
   ping open.feishu.cn
   ```

2. **检查飞书API配置**:
   ```bash
   cat /opt/feishu/.env | grep FEISHU_
   ```

3. **检查磁盘空间**:
   ```bash
   df -h /home/feishu
   ```

## 📈 性能优化

### 日志轮转

创建日志轮转配置：

```bash
sudo nano /etc/logrotate.d/feishu
```

内容：
```
/var/log/feishu/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 your_username your_username
}
```

### 磁盘空间监控

添加磁盘空间检查到定时任务：

```bash
# 编辑 crontab
crontab -e

# 添加磁盘检查（每天检查一次）
0 9 * * * df -h /home/feishu | awk 'NR==2{print $5}' | sed 's/%//' | awk '{if($1>80) print "磁盘空间不足："$1"%"}' >> /var/log/feishu/disk_alert.log
```

## 📞 支持命令

```bash
# 手动执行测试
cd /opt/feishu && source venv/bin/activate && python3 cron_deployment.py daily

# 测试飞书数据拉取
cd /opt/feishu && source venv/bin/activate && python3 cron_deployment.py fetch

# 查看当前配置
cat /opt/feishu/.env

# 重新安装（保留配置）
cd /tmp/feishu_deploy && ./install_cron.sh --skip-test

# 查看版本信息
cd /opt/feishu && source venv/bin/activate && pip list | grep -E "(requests|pandas|pymysql)"
```

---

## 📋 部署清单

- [x] 上传项目文件到服务器
- [x] 执行安装脚本 `./install_cron.sh`
- [x] 配置数据库信息 `/opt/feishu/.env`
- [x] 验证定时任务 `crontab -l`
- [x] 测试手动执行
- [x] 检查日志输出
- [x] 确认文件下载目录

部署完成后，系统将每天早上8点自动执行数据同步和文件下载任务！ 