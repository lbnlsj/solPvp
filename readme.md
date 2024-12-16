# Ubuntu SolPvp 项目安装部署指南

## 1. 系统要求
- Ubuntu 20.04 或更新版本
- Python 3.8 或以上


## 2. 安装 Miniconda
```bash
# 下载 Miniconda 安装脚本
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# 运行安装脚本
bash Miniconda3-latest-Linux-x86_64.sh

# 使环境变量生效
source ~/.bashrc
```

## 3. 验证 Conda 安装
```bash
conda --version
```

## 4. 配置 Python 环境
```bash
# 创建新的 conda 环境
conda create -n solpvp python=3.10

# 激活环境
source activate solpvp
```

## 5. 安装系统依赖
```bash
# 安装编译工具和开发包
sudo apt update
sudo apt install -y python3-dev build-essential git
```

## 6. 克隆项目代码
```bash
git clone https://github.com/lbnlsj/solPvp.git
cd solPvp
```

## 7. pip requirements.txt
```bash
pip install -r requirements.txt

```

## 8. 创建项目目录结构
```bash
无
```

## 9. 运行项目
```bash
python app.py
```
服务器将在 http://localhost:9488 启动

## 10. 验证部署

检查服务是否正常运行：
```bash
# 检查进程
ps aux | grep python

# 检查端口
netstat -tupln | grep 9488

# 检查日志输出
tail -f nohup.log  # 如果使用 nohup 运行
```

## 11. 后台运行（可选）
```bash
# 使用 nohup 后台运行
nohup python app.py > nohup.log 2>&1 &

# 查看进程
ps aux | grep python

# 实时查看日志
tail -f nohup.log
```

## 12. 常见问题解决

### 依赖安装失败
```bash
# 升级 pip
pip install --upgrade pip

# 安装 wheel
pip install wheel

# 重新安装依赖
pip install --no-cache-dir -r requirements.txt
```

### 权限问题
```bash
# 修改项目目录权限
sudo chown -R $USER:$USER .
chmod -R 755 .
```

### 端口被占用
```bash
# 查找占用端口的进程
sudo netstat -tupln | grep 9488

# 终止进程
sudo kill -9 <进程ID>
```

## 13. 维护建议

1. 定期更新代码：
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

2. 数据备份：
```bash
# 备份数据目录
cp -r data/ data_backup_$(date +%Y%m%d)
```

3. 日志管理：
```bash
# 定期清理日志
find . -name "*.log" -size +100M -exec rm -f {} \;
```

## 14. 监控

1. 监控系统资源：
```bash
# CPU 和内存使用
top

# 磁盘使用
df -h

# 查看日志
tail -f nohup.log
```

2. 检查服务状态：
```bash
# 检查程序是否运行
ps aux | grep python

# 检查端口状态
netstat -tupln | grep 9488
```

## 注意事项

1. 确保服务器防火墙配置正确：
```bash
sudo ufw allow 9488
```

2. 定期检查日志文件大小：
```bash
ls -lh nohup.log
```

3. 保持系统更新：
```bash
sudo apt update
sudo apt upgrade
```

4. 定期备份数据：
   - 配置文件
   - 交易记录
   - 钱包信息

## 结束语

完成以上步骤后，SolPvp 项目应该已经在 Ubuntu 系统上成功部署并运行。如果遇到问题，请检查：
- Python 环境配置
- 依赖包安装状态
- 网络连接
- 系统资源使用情况
- 日志输出信息

建议保持系统和依赖包的定期更新，并做好数据备份工作。