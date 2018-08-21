FROM ubuntu:16.04

MAINTAINER Bitworks Software info@bitworks.software

ENV KVM_HOST qemu+tcp://root@10.252.1.35:16509/system
ENV KAFKA_BOOTSTRAP localhost:9092
ENV KAFKA_TOPIC kvm-metrics

ENV PAUSE 20
ENV GATHER_HOST_STATS true
ENV DEBUG true

RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

RUN DEBIAN_FRONTEND=noninteractive apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y -q python-pip python-dev libmysqlclient-dev python-mysqldb
RUN pip install --upgrade pip
RUN pip install kafka-python
RUN pip install cs


COPY ./src /opt


WORKDIR /opt

CMD ["/bin/bash", "/opt/launch-exporter"]


