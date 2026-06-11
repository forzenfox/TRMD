ARG BASE_IMAGE=trmd-base

# ============================================================
# 第一阶段：按当前架构筛选二进制文件
# ============================================================
FROM ${BASE_IMAGE}:latest AS preparer
ARG TARGETARCH
ARG TARGETVARIANT

COPY res/bin/ /tmp/bin/
RUN case "${TARGETARCH}" in \
        amd64) \
            mv /tmp/bin/ttyd.x86_64 /tmp/bin/ttyd && \
            mv /tmp/bin/tmux.linux-amd64 /tmp/bin/tmux ;; \
        arm64) \
            mv /tmp/bin/ttyd.aarch64 /tmp/bin/ttyd && \
            mv /tmp/bin/tmux.linux-arm64 /tmp/bin/tmux ;; \
        arm) \
            cp /tmp/bin/ttyd.armhf /tmp/bin/ttyd ;; \
    esac && \
    chmod +x /tmp/bin/ttyd /tmp/bin/tmux 2>/dev/null || true && \
    rm -f /tmp/bin/ttyd.* /tmp/bin/tmux.* /tmp/bin/rar* /tmp/bin/MediaInfo.* /tmp/bin/libmediainfo.*

# ============================================================
# 第二阶段：最终运行时镜像
# ============================================================
FROM ${BASE_IMAGE}:latest

# 复制筛选后的二进制文件（仅保留当前架构所需的）
COPY --from=preparer /tmp/bin/ ./res/bin/

# 复制项目代码
COPY main.py .
COPY module/ ./module/

# 设置挂载点
VOLUME ["/app/TRMD", "/app/downloads", "/app/sessions", "/app/temp", "/app/form"]

# 运行应用
CMD ["python", "main.py", "--config", "/app/TRMD/config.yaml"]