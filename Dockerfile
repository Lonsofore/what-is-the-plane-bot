FROM python:3.10

WORKDIR /app
COPY requirements.txt /app/
RUN pip install -r /app/requirements.txt

WORKDIR /app/src
COPY src /app/src

CMD python -u main.py