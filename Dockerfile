FROM python:3.12-slim

# Undgå .pyc filer og bufret stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Installer afhængigheder i eget lag så de caches ved genbygning
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiér applikationskode
COPY . .

# Opret mappe til SQLite og ICS-filer
RUN mkdir -p /data/calendars

# Database gemmes i /data så den overlever container-genstarter via volume
ENV DATABASE_URL=sqlite:////data/shift_calendar.db

# Sørg for at static/calendars peger på /data/calendars
RUN ln -sfn /data/calendars /app/static/calendars

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]