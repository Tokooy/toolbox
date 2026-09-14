# ============================================================
#  Toolbox 工具台 · Docker 运行镜像
#
#  用途：把整个工具台（core + hub + 各工具）容器化，
#        一条命令即可在任意装了 Docker 的机器上运行（Linux 服务器 / NAS / VPS），
#        无需安装 Python、无需桌面环境。
#
#  构建（**必须在仓库根目录执行**，构建上下文就是仓库根）：
#      docker build -f packaging/docker/Dockerfile -t toolbox .
#
#  运行（数据卷持久化，容器删了数据还在）：
#      docker run -d --name toolbox -p 8080:8080 \
#        -v toolbox_data:/app/data toolbox
#
#  访问：http://<主机IP>:8080
#  迁移：在新机器上重新 build + run，把数据卷带过去即可（详见 README）
# ============================================================
FROM python:3.12-slim

# 镜像内固定代码根目录（core.paths 以「非打包」模式工作：代码根 == /app）
WORKDIR /app

# 运行依赖只有二维码生成需要；core / hub / 美债看板都是纯 Python 标准库
RUN pip install --no-cache-dir "qrcode[pil]" pillow openpyxl

# 代码：公共内核 + 各工具（前端/后端）+ 工具台外壳
COPY core/ core/
COPY apps/ apps/
COPY hub/ hub/

# 内置美债历史缓存的「种子」：容器首次启动时由 apps/treasury/backend/store.py:ensure_seed()
# 复制到数据根（/app/data/treasury），因此命名卷与绑定挂载都能离线开箱即用
COPY data/treasury/ seed/treasury/

# 数据根指向 /app/data —— 建议把它挂成数据卷，容器重建也不丢数据
# TOOLBOX_NO_BROWSER：容器内没有桌面，明确关掉“自动打开浏览器”
ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    TOOLBOX_DATA_ROOT=/app/data \
    TOOLBOX_NO_BROWSER=1

EXPOSE 8080

# 容器内没有桌面，服务端「自动打开浏览器」会被安全忽略
CMD ["python", "hub/server.py"]
