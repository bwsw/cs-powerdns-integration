# CloudStack Event-based Integration for PowerDNS

The service creates A, AAAA and PTR records in PowerDNS for newly created virtual machines and removes those records when VMs are being removed. The service uses PowerDNS with MySQL backend. Currently only records for ip/ipv6 directly attached to VM is supported. Domain suffixes defined for CloudStack domains are supported. Resulting A, AAAA records a constructed as vm-name.domain-suffix-name, where ```domain-suffix-name``` is a domain suffix defined for CloudStack domain.

## Rationale

CloudStack VR maintains DNS A records for VMs but since VR is a ephemeral entity which can be removed and recreated, which IP addresses can be changed, it's inconvenient to use it for zone delegation. Also, it's difficult to pair second DNS server with it as it requires VR hacking. So, to overcome those difficulties and provide external users with FQDN access to VMs we implemented the solution.

## How to use it

**Deploy CloudStack with Kafka Event Bus**. Take a look at official [guide](http://docs.cloudstack.apache.org/projects/cloudstack-administration/en/4.11/events.html).

**Deploy PowerDNS with MySQL backend, and (optionally) PowerAdmin**. Quickly, you can use simple PowerDNS packed Docker image:

```bash
docker run -d --name pdns-master 
            -e MYSQL_HOST=10.252.2.1 \
            -e MYSQL_PORT=3306 \
            -e MYSQL_USER=dns \
            -e DB_ENV_MYSQL_ROOT_PASSWORD=changeme \
            -e MYSQL_DB=pdns \
            -p 153:53/udp \
            -p 153:53 \
            -p 127.0.0.1:8081:80 \
            bwsw/docker-pdns
```

> Don't create ```pdns``` database. The container will do it. Just GRANT required privileges to ```dns``` user.

**Create necessary zones in PowerDNS**. Zones which will be filled must be created in PowerDNS. If a zone is absent for certain DNS suffix, those records will not be added into PowerDNS. PTR zones for IPv4 and IPv6 must be created as well. Use Poweradmin for management.

**Deploy exporter container**. Exporter is provided in the form of Docker image, which can be started in seconds:

```bash
docker run --restart=always -d --name dns-exporter  \
	-e KAFKA_BOOTSTRAP=10.252.2.4:9092,10.252.2.3:9092,10.252.2.2:9092 \
        -e KAFKA_TOPIC=cs-events \
        -e KAFKA_GROUP=export-pdns-1 \
        -e CS_ENDPOINT=https://server/client/api \
        -e CS_API_KEY=secret \
        -e CS_SECRET_KEY=secret \
        -e MYSQL_PDNS_NAME=pdns \
        -e MYSQL_PDNS_HOST=10.252.2.1 \
        -e MYSQL_PDNS_PORT=3306 \
        -e MYSQL_PDNS_PASSWORD=secret \
        -e MYSQL_PDNS_USER=dns \
        bwsw/cs-powerdns-integration
```

View logs with:

```
docker logs -f dns-exporter
```

**Test it**. Create VM and ensure appropriate records are accessible.

```
nslookup -q=PTR -port=153 <vm_ipv4> 10.252.2.4
nslookup -q=PTR -port=153 <vm_ipv6> 10.252.2.4
nslookup -q=A -port=153 vm-name.domain-name 10.252.2.4
nslookup -q=AAAA -port=153 vm-name.domain-name 10.252.2.4
```

> You can modify records further as they are not modified longer. As for current implementation, modified records are persistent and are not removed upon VM removal.

**Scale**. Deploy second PowerDNS. Use another ```KAFKA_GROUP``` value for second exporter.

**Delegate**. Add necessary NS records into zone, delegate it, add records in RIPE/IANA/APNIC/etc DB. 

## License

Licensed under Apache 2.0 license.
