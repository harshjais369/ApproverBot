FROM python:3.14-slim

WORKDIR /app

# Create a non-root user to run the app
RUN addgroup --system botgroup && adduser --system --ingroup botgroup botuser

# Install dependencies first (layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create the persistent data directory and set permissions BEFORE copying code
RUN mkdir -p /app/data && chown -R botuser:botgroup /app/data

# Copy application source and explicitly assign ownership to your non-root user
COPY --chown=botuser:botgroup . .

USER botuser

CMD ["python", "bot.py"]
