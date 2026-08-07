FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY db.py .
COPY manual_attendance/ ./manual_attendance/

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "manual_attendance.chat_app"]
