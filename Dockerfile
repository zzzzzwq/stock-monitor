FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建必要目录
RUN mkdir -p logs data

# 暴露端口
EXPOSE 8080

# 入口脚本（先初始化DB，再启动）
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
