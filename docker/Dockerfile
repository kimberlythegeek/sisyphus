From python:2.7.15
ENV PYTHONUNBUFFERED 1

WORKDIR /app/

RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y \
  build-essential \
  python-dev \
  mysql-client \
  libsasl2-dev \
  libldap2-dev \
  libssl-dev

COPY requirements.txt .
RUN pip install -U -r requirements.txt
