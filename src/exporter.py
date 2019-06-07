#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys

sys.path.append(".")

import logging
import json
import os
from signal import SIGKILL
from kafka import KafkaConsumer, TopicPartition
from multiprocessing import Process
from multiprocessing import Queue
from Queue import Empty
import mysql.connector
from cs import CloudStack, CloudStackException
from lib.virtual_machine import VirtualMachine
from lib.account import Account

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT, stream=sys.stderr, level=logging.INFO)

kafka_bootstrap_hosts = os.environ["KAFKA_BOOTSTRAP"]
kafka_topic = os.environ["KAFKA_TOPIC"]
kafka_group = os.environ["KAFKA_GROUP"]

mysql_pdns_name = os.environ['MYSQL_PDNS_NAME']
mysql_pdns_user = os.environ['MYSQL_PDNS_USER']
mysql_pdns_password = os.environ['MYSQL_PDNS_PASSWORD']
mysql_pdns_host = os.environ['MYSQL_PDNS_HOST']
mysql_pdns_port = int(os.environ['MYSQL_PDNS_PORT'])

cs_endpoint = os.environ['CS_ENDPOINT']
cs_api_key = os.environ['CS_API_KEY']
cs_secret_key = os.environ['CS_SECRET_KEY']

dns_record_ttl = os.environ['DNS_RECORD_TTL']
dns_common_zone = os.environ['DNS_COMMON_ZONE']
dns_add_to_common_zone = os.environ['DNS_ADD_TO_COMMON_ZONE']

deadlock_interval = os.environ['DEADLOCK_INTERVAL']


def get_mysql():
    return mysql.connector.connect(host=mysql_pdns_host, port=mysql_pdns_port,
                                   user=mysql_pdns_user, passwd=mysql_pdns_password, database=mysql_pdns_name)


pdns_conn = get_mysql()

pdns_cursor = pdns_conn.cursor()
pdns_cursor.execute(
    "CREATE TABLE IF NOT EXISTS cs_mapping(uuid CHAR(36), record VARCHAR(255), ipaddress CHAR(39), "
    "UNIQUE(uuid, record, ipaddress))")
pdns_conn.commit()

pdns_cursor.close()
pdns_conn.close()

consumer = KafkaConsumer(kafka_topic,
                         auto_offset_reset='earliest',
                         group_id=kafka_group,
                         bootstrap_servers=kafka_bootstrap_hosts.split(","),
                         value_deserializer=lambda m: json.loads(m.decode('utf8')),
                         enable_auto_commit=False)

cs = CloudStack(endpoint=cs_endpoint,
                key=cs_api_key,
                secret=cs_secret_key)


def extract_create_payload(job_result):
    job_result = job_result.replace("org.apache.cloudstack.api.response.UserVmResponse/virtualmachine/", "", 1)
    return json.loads(job_result)


def update_a_zone(cursor, account, vm, domain):
    cursor.execute("SELECT id FROM domains WHERE name = %s", (domain,))
    fqdn = vm.name + "." + domain
    row = cursor.fetchone()
    if row is not None:
        domain_id = row[0]
        cursor.execute(
            """REPLACE INTO records (name, type, content, ttl, prio, change_date, ordername, auth, domain_id) 
            VALUES (%s, 'A', %s, %s, 0, UNIX_TIMESTAMP(), %s, 1, %s)""",
            (fqdn, vm.ip4, dns_record_ttl, vm.name, domain_id))
        if vm.ip6 is not None:
            cursor.execute(
                """REPLACE INTO records (name, type, content, ttl, prio, change_date, ordername, auth, domain_id) 
                VALUES (%s, 'AAAA', %s, %s, 0, UNIX_TIMESTAMP(), %s, 1, %s)""",
                (fqdn, vm.ip6, dns_record_ttl, vm.name, domain_id))
        cursor.execute("""INSERT IGNORE INTO cs_mapping (uuid, record) VALUES(%s,%s)""", (vm.uuid, fqdn))

        group_fqdn = vm.group_fqdn(account, domain)
        if group_fqdn:
            logging.info("Group FQDN: %s" % group_fqdn)
            cursor.execute(
                """REPLACE INTO records (name, type, content, ttl, prio, change_date, ordername, auth, domain_id) 
                VALUES (%s, 'A', %s, %s, 0, UNIX_TIMESTAMP(), %s, 1, %s)""",
                (group_fqdn, vm.ip4, dns_record_ttl, vm.name, domain_id))
            cursor.execute("""INSERT IGNORE INTO cs_mapping (uuid, record, ipaddress) VALUES (%s,%s,%s)""",
                           (vm.uuid, group_fqdn, vm.ip4))
            if vm.ip6 is not None:
                cursor.execute(
                    """REPLACE INTO records (name, type, content, ttl, prio, change_date, ordername, auth, domain_id) 
                    VALUES (%s, 'AAAA', %s, %s, 0, UNIX_TIMESTAMP(), %s, 1, %s)""",
                    (group_fqdn, vm.ip6, dns_record_ttl, vm.name, domain_id))
                cursor.execute("""INSERT IGNORE INTO cs_mapping (uuid, record, ipaddress) VALUES (%s,%s,%s)""",
                               (vm.uuid, group_fqdn, vm.ip6))


def update_ptr_zone(cursor, vm):
    cursor.execute("SELECT id FROM domains WHERE name = %s", (vm.ip4_ptr_zone,))
    row = cursor.fetchone()
    if row is not None:
        domain_id = row[0]
        cursor.execute(
            """REPLACE INTO records (name, type, content, ttl, prio, change_date, auth, domain_id) 
            VALUES (%s, 'PTR', %s, %s, 0, UNIX_TIMESTAMP(), 1, %s)""",
            (vm.ip4_ptr, vm.fqdn, dns_record_ttl, domain_id))
        cursor.execute("""INSERT IGNORE INTO cs_mapping (uuid, record) VALUES(%s,%s)""", (vm.uuid, vm.ip4_ptr))

    if vm.ip6 is not None:
        cursor.execute("SELECT id FROM domains WHERE name = %s", (vm.ip6_ptr_zone,))
        row = cursor.fetchone()
        if row is not None:
            domain_id = row[0]
            cursor.execute(
                """REPLACE INTO records (name, type, content, ttl, prio, change_date, auth, domain_id) 
                VALUES (%s, 'PTR', %s, %s, 0, UNIX_TIMESTAMP(), 1, %s)""",
                (vm.ip6_ptr, vm.fqdn, dns_record_ttl, domain_id))
            cursor.execute("""INSERT IGNORE INTO cs_mapping (uuid, record) VALUES(%s,%s)""", (vm.uuid, vm.ip6_ptr))


def create_new_records(m):
    jr = "jobResult"

    def create_match():
        return "commandEventType" in m \
               and "status" in m \
               and m["commandEventType"].lower() == "VM.CREATE".lower() \
               and m["status"].lower() == "SUCCEEDED".lower()

    def start_match():
        return "commandEventType" in m \
               and "status" in m \
               and m["commandEventType"].lower() == "VM.START".lower() \
               and m["status"].lower() == "SUCCEEDED".lower()

    is_create_event = create_match()
    is_start_event = start_match()

    if is_create_event or is_start_event:

        account = Account(
            cs_api=cs,
            cmd_info=m)

        job_result = extract_create_payload(m[jr])

        vm = VirtualMachine(
            cs_api=cs,
            vm_info=job_result)

        if not (vm.domain and vm.ip4):
            return

        vm.dump()

        c = pdns_conn.cursor()

        # delete old a records
        c.execute("DELETE FROM records WHERE name = %s", (vm.fqdn,))

        # Add A, AAAA records
        if dns_add_to_common_zone == 'true':
            update_a_zone(c, account, vm, dns_common_zone)

        if account.network_domain:
            update_a_zone(c, account, vm, account.network_domain)
        else:
            update_a_zone(c, account, vm, vm.domain)

        # Add PTR records, except when VM is started
        if not is_start_event:
            update_ptr_zone(c, vm)

        pdns_conn.commit()
        c.close()


def delete_removed_records(m):
    vm_field = "VirtualMachine"
    status_field = "status"
    status_value = "Completed"
    event_field = "event"
    event_value = "VM.DESTROY"
    if vm_field in m \
            and status_field in m \
            and event_field in m \
            and m[status_field].lower() == status_value.lower() \
            and m[event_field].lower() == event_value.lower():
        vm_uuid = m[vm_field].lower()
        c = pdns_conn.cursor()
        c.execute("SELECT record, ipaddress FROM cs_mapping where uuid = %s", (vm_uuid,))
        rows = c.fetchall()
        for r in rows:
            logging.info("Deleting DNS entries: record=%s, ipaddress=%s" % r)
            if r[1]:
                c.execute("DELETE FROM records WHERE name = %s AND content = %s", r)
            else:
                c.execute("DELETE FROM records WHERE name = %s", (r[0],))
        c.execute("DELETE FROM cs_mapping WHERE uuid = %s", (vm_uuid,))
        pdns_conn.commit()
        c.close()


def monitor(q, pid):
    while True:
        try:
            q.get(timeout=int(deadlock_interval))
        except Empty:
            break
    logging.info("No events in %s seconds. May be internal deadlock happened. Reset the system." % deadlock_interval)
    os.kill(pid, SIGKILL)
    exit(0)


if __name__ == '__main__':
    q = Queue()
    pid = os.getpid()
    mon = Process(target=monitor, args=(q, pid))
    mon.start()
    while True:
        msgs = consumer.poll(1000, 10)
        if bool(msgs):
            msgs = msgs[TopicPartition(topic=kafka_topic, partition=0)]
            for m in msgs:
                m = m.value
                try:
                    pdns_conn = get_mysql()
                    create_new_records(m)
                    delete_removed_records(m)
                    pdns_conn.close()
                    consumer.commit()
                except CloudStackException:
                    pass
                q.put(m)
