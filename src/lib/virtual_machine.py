import logging
import ipaddress

class VirtualMachine:
    def __init__(self, cs_api, vm_info):
        self.csapi = cs_api
        self._vm_info = vm_info
        self.name = vm_info['name'].lower()
        self.uuid = vm_info['id'].lower()
        self.domain = self._domain()
        self.nic0 = self._vm_info['nic'][0]
        self.ip4 = self._ip4()
        self.group = self._group()
        self._ip6()
        self._ip4_ptr()
        self._ip6_ptr()
        self.fqdn = "%s.%s" % (self.name, self.domain)

    def group_fqdn(self, account, domain):
        if self.group:
            safe_name = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
            name = filter(lambda x: x in safe_name, self.group)
            if len(name):
                return name.lower() + "-" + account.uuid[0:8] + "." + domain
            else:
                return None
        else:
            return None


    def _group(self):
        if 'group' not in self._vm_info:
            return None
        else:
            return self._vm_info['group']

    def _domain(self):
        domain = self.csapi.listDomains(id = self._vm_info['domainid'])
        try:
            return domain['domain'][0]['networkdomain'].lower()
        except:
            return None

    def _ip4(self):
        if 'ipaddress' not in self.nic0:
            return None
        return self.nic0['ipaddress']

    def _ip6(self):
        self.ip6 = None
        self.ip6_cidr = None
        if 'ip6address' in self.nic0:
            self.ip6 = self.nic0['ip6address']
            self.ip6_cidr = self.nic0['ip6cidr']

    def dump(self):
        logging.info("VM: %s" % self.fqdn)
        logging.info("IPv4: %s" % self.ip4)
        logging.info("IPv6: %s" % self.ip6)
        logging.info("IPv4 PTR: %s" % self.ip4_ptr)
        logging.info("IPv4 PTR Zone: %s" % self.ip4_ptr_zone)
        logging.info("IPv6 PTR: %s" % self.ip6_ptr)
        logging.info("IPv6 PTR Zone: %s" % self.ip6_ptr_zone)

    def _ip4_ptr(self):
        # Add PTR records
        # build ptr for ip address
        self.ip4_ptr_zone = None
        self.ip4_ptr = None
        if not self.ip4:
            return
        ip_parts = self.ip4.split('.')
        ip_parts.reverse()
        self.ip4_ptr_zone = ".".join(ip_parts[1:]) + ".in-addr.arpa"
        self.ip4_ptr = ".".join(ip_parts) + ".in-addr.arpa"

    def _ip6_ptr(self):
        self.ip6_ptr_zone = None
        self.ip6_ptr = None
        if not self.ip6:
            return
        pref_len = int(self.ip6_cidr.split('/')[1])
        pref_cut = (128 - pref_len) / 4 * 2 + 1
        ptr6_zone = ipaddress.IPv6Network(self.ip6_cidr).reverse_pointer
        self.ip6_ptr_zone = ptr6_zone.split('/')[1][pref_cut:]
        self.ip6_ptr = ipaddress.ip_address(self.ip6).reverse_pointer
