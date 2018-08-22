FROM ubuntu:16.04

MAINTAINER Bitworks Software info@bitworks.software

ENV KAFKA_BOOTSTRAP localhost:9092
ENV KAFKA_TOPIC cs-events
ENV DNS_RECORD_TTL 60

RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

RUN DEBIAN_FRONTEND=noninteractive apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y -q python-pip python-dev libmysqlclient-dev python-mysqldb
RUN pip install --upgrade pip
RUN pip install kafka-python
RUN pip install cs
RUN pip install ipaddress

COPY ./src /opt


WORKDIR /opt

CMD ["/bin/bash", "/opt/launch-exporter"]


