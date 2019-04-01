# Pastebin YHMV1zA8
From python:2.7.15
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y \
  build-essential \
  python-dev \
  mysql-client \
  libsasl2-dev \
  libldap2-dev \
  libssl-dev

RUN mkdir /config
ADD /requirements.txt /config/

ADD sisyphus /sisyphus
WORKDIR /sisyphus

RUN pip install -U -r /config/requirements.txt
