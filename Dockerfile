FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8787
CMD ["openjev", "serve", "--host", "0.0.0.0", "--port", "8787"]
