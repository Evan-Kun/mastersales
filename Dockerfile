FROM python:3.12-slim

# System dependencies for WeasyPrint (PDF generation) and Playwright (LinkedIn scraping)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint deps
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev \
    # Playwright/Chromium deps
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libasound2 libpangocairo-1.0-0 libgtk-3-0 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium

COPY . .

EXPOSE 8899

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8899"]
