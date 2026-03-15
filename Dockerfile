FROM python:3.12-slim

# Create a non-root user to run the app
RUN addgroup --system botgroup && adduser --system --ingroup botgroup botuser

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Ensure there is no .env baked into the image
RUN rm -f .env .env.example

# Persistent data directory for SQLite
RUN mkdir -p /app/data && chown botuser:botgroup /app/data

USER botuser

CMD ["python", "bot.py"]
