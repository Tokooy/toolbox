# ============================================================
#  Toolbox 工具台 · Docker 运行镜像
#
#  用途：把整个 toolbox（hub + 美债看板 + 二维码生成）容器化，
#        便于迁移 / 部署到任意机器（Linux 服务器、NAS、VPS 等），
#        一条命令即可在无桌面环境下运行。
#
#  构建：
#     docker build -t toolbox .
#
#  运行（首次自动创建数据卷，数据不随容器销毁而丢失）：
#     docker run -d -p 8080:8080 \
#       -v toolbox_qr:/app/QRcode \
#       -v toolbox_treasury:/app/us-treasury-yields/data \
#       --name toolbox toolbox
#
#  访问：http://<主机IP>:8080（容器内无浏览器，访问方式同网页）
#  迁移：把镜像 export/推送或在新机器上重新 docker build + docker run 即可
# ============================================================
FROM python:3.12-slim

# 镜像内固定代码根目录（hub 以「非打包」模式运行，代码根 = 仓库根）
WORKDIR /app

# 运行依赖：仅二维码生成需要；hub 与美债看板均为纯 Python 标准库
RUN pip install --no-cache-dir "qrcode[pil]" pillow openpyxl

# 代码与预置数据（us-treasury-yields/data 含历史种子缓存，离线即可看图；
# 运行时建议把 QRcode 与 data 挂为数据卷，写入内容可持久化）
COPY hub/ hub/
COPY QRcode/ QRcode/
COPY us-treasury-yields/ us-treasury-yields/
COPY toolbox.spec ./

# 端口与输出缓冲
EXPOSE 8080
ENV PYTHONUNBUFFERED=1
# 容器内监听所有网卡，供 docker -p 8080:8080 把服务映射到宿主机
ENV HOST=0.0.0.0

# 容器内无桌面，自动打开浏览器的步骤会被服务端安全忽略；
# 服务监听地址由 HOST 环境变量控制（默认 0.0.0.0）
CMD ["python", "hub/server.py"]
