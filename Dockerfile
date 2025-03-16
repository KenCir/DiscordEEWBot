FROM python:3.12-slim

RUN apt update && apt install -y

ARG USERNAME=discordeewbot
ARG GROUPNAME=discordeewbot
ARG UID=1000
ARG GID=1000
ARG WORKDIR=/app

ENV TZ Asia/Tokyo

RUN groupadd -g $GID $GROUPNAME && \
    useradd -m -s /bin/bash -u $UID -g $GID $USERNAME

RUN mkdir -p $WORKDIR && \
    chown -R $USERNAME:$GROUPNAME $WORKDIR

USER $USERNAME

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python", "main.py"]