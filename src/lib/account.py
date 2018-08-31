import logging
import ipaddress

class Account:
    def __init__(self, cs_api, cmd_info):
        self.cs_api = cs_api
        self.uuid = cmd_info['account']
        self._get_account()

    def _get_account(self):
        accounts = self.cs_api.listAccounts(id = self.uuid)
        self.name = accounts['account'][0]['name'].lower()
        self.network_domain = None
        try:
            self.network_domain = accounts['account'][0]['networkdomain'].lower()
        except:
            pass
