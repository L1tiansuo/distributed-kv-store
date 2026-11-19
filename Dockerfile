# 三副本 KV Store 的节点镜像（容器方式，可选）
#
# 选 alpine 而不是 python:slim，原因很实际：本机拉 python:slim 只有 20KB/s，
# 30MB 要跑二十多分钟；alpine + apk add python3 一分钟内就能装好，
# 镜像也更小（约 55MB）。节点代码只用标准库，两种基础镜像都能跑。

FROM alpine:3.20

RUN apk add --no-cache python3

WORKDIR /app
COPY src/node.py /app/node.py

EXPOSE 7301

# alpine 里可执行文件名是 python3，不是 python
ENTRYPOINT ["python3", "/app/node.py"]
