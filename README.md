# Pulse Plugin Sensor (Kafka Edition)

The purpose of the container is to monitor remote libvirt KVM hypervisor host and gather the information about VM resource usage. It is implemented in python2.7 with libvirt. It stores collected statistics to a kafka topic.

Currently it collects next metrics: 
 - Host: CPU statistics, RAM statistics
 - Virtual machines: cpuTime, RAM usage, disk IO, network IO

Features:
 - purposed for KVM hypervisor
 - tested with block devices located in files (native for Apache Cloudstack and NFS storage)
 - bundled as easy to use Docker container (one container per one virtualization host)
 
 Known to work with:
 - Apache Cloudstack 4.3 with KVM hypervisor and NFS primary storage
 - Apache Cloudstack 4.9 with KVM hypervisor and NFS primary storage
 - Apache Cloudstack 4.11.1 with KVM hypervisor and local primary storage

Usage:

```
# create topic
docker run --rm -it wurstmeister/kafka:1.0.0 sh -c "JMX_PORT= /opt/kafka/bin/kafka-topics.sh --create --zookeeper zk1:2181 --replication-factor 3 --partitions 1 --topic kvm-metrics

# deploy service
docker run --restart=always -d --name 10.252.1.11 \
             -v /root/.ssh:/root/.ssh \
             -e PAUSE=10 \
             -e KAFKA_BOOTSTRAP=host1:9092,host2:9092,host3:9092 \
             -e KAFKA_TOPIC=kvm-metrics \
             -e GATHER_HOST_STATS=true
             -e DEBUG=true \
             -e KVM_HOST=qemu+ssh://root@10.252.1.11/system \
             bwsw/cs-pulse-sensor-kafka

# test it
docker run --rm -it wurstmeister/kafka:1.0.0 sh -c "JMX_PORT= /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server host1:9092,host2:9092,host3:9092 --topic kvm-metrics --max-messages 1000 --from-beginning"
```

## Container Parameters

Container supports next configuration parameters:

- KVM_HOST - fqdn for libvrt KVM connection line
- PAUSE - interval between metering
- KAFKA_BOOTSTRAP - comma separated list of kafka bootstrap servers
- KAFKA_TOPIC - topic where to place data
- GATHER_HOST_STATS - if to collect information about a hypervisor host
- DEBUG - print or avoid JSON dumps inside docker container (useful for troubleshooting in attached mode)

## Data structure

All series are stored in InfluxDB compatible format. Just read them from Kafka and import into InfluxDB.

Virtualization node series stored into kafka look like:

```
[
    {
        "fields": {
            "freeMem": 80558,
            "idle": 120492574,
            "iowait": 39380,
            "kernel": 1198652,
            "totalMem": 128850,
            "user": 6416940
        },
        "measurement": "nodeInfo",
        "tags": {
            "vmHost": "qemu+ssh://root@10.252.1.33/system"
        },
        "time": "2018-08-17T09:00:35Z"
    }
]
```

Virtual machine series stored into kafka look like:

```
[
    {
        "fields": {
            "cpuTime": 1070.75,
            "cpus": 4
        },
        "measurement": "cpuTime",
        "tags": {
            "vmHost": "qemu+ssh://root@10.252.1.33/system",
            "vmId": "i-376-1733-VM",
            "vmUuid": "12805898-0fda-4fa6-9f18-fac64f673679"
        },
        "time": "2018-08-17T09:00:35Z"
    },
    {
        "fields": {
            "maxmem": 4194304,
            "mem": 4194304,
            "rss": 1443428
        },
        "measurement": "rss",
        "tags": {
            "vmHost": "qemu+ssh://root@10.252.1.33/system",
            "vmId": "i-376-1733-VM",
            "vmUuid": "12805898-0fda-4fa6-9f18-fac64f673679"
        },
        "time": "2018-08-17T09:00:35Z"
    },
    {
        "fields": {
            "readBytes": 111991494,
            "readDrops": 0,
            "readErrors": 0,
            "readPackets": 1453303,
            "writeBytes": 3067403974,
            "writeDrops": 0,
            "writeErrors": 0,
            "writePackets": 588124
        },
        "measurement": "networkInterface",
        "tags": {
            "mac": "06:f2:64:00:01:54",
            "vmHost": "qemu+ssh://root@10.252.1.33/system",
            "vmId": "i-376-1733-VM",
            "vmUuid": "12805898-0fda-4fa6-9f18-fac64f673679"
        },
        "time": "2018-08-17T09:00:35Z"
    },
    {
        "fields": {
            "allocatedSpace": 890,
            "ioErrors": -1,
            "onDiskSpace": 890,
            "readBytes": 264512607744,
            "readIOPS": 16538654,
            "totalSpace": 1000,
            "writeBytes": 930057794560,
            "writeIOPS": 30476842
        },
        "measurement": "disk",
        "tags": {
            "image": "cc8121ef-2029-4f4f-826e-7c4f2c8a5563",
            "pool": "b13cb3c0-c84d-334c-9fc3-4826ae58d984",
            "vmHost": "qemu+ssh://root@10.252.1.33/system",
            "vmId": "i-376-1733-VM",
            "vmUuid": "12805898-0fda-4fa6-9f18-fac64f673679"
        },
        "time": "2018-08-17T09:00:35Z"
    }
]

```

## License

Licensed under Apache 2.0 license.
