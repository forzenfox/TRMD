ARG BASE_IMAGE=trmd-base:latest
FROM ${BASE_IMAGE}

# 复制项目代码
COPY main.py .
COPY module/ ./module/

# 设置挂载点
VOLUME ["/app/TRMD", "/app/downloads", "/app/sessions", "/app/temp", "/app/form"]

# 运行应用（配置文件在工作目录）
CMD ["python", "main.py"]