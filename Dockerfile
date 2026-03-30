# Stage 1: Build Tailwind CSS
FROM node:25-slim AS css-builder
WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm ci
COPY tailwind.config.js ./
COPY static/css/input.css static/css/
COPY app/templates/ app/templates/
RUN npx tailwindcss -i static/css/input.css -o static/css/style.css --minify

# Stage 2: Python application
FROM python:3.14-slim
WORKDIR /app

# pg_isready for entrypoint DB-ready check
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy built CSS from stage 1
COPY --from=css-builder /build/static/css/style.css static/css/style.css

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
