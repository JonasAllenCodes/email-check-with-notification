FROM python:3.12-alpine

WORKDIR /app

COPY check-payment-email.py .

RUN chmod +x check-payment-email.py

ENTRYPOINT ["python", "check-payment-email.py"]
