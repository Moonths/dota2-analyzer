FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
# 阿里云内网 PyPI 镜像, 避免 ECS 访问国外源超时
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com
COPY . .
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
