#!/usr/bin/python
# -*- coding: utf-8 -*-
# (c) 2017, Alen Komic
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible. If not, see <http://www.gnu.org/licenses/>.
#
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: zabbix_action
short_description: Zabbix action creates/deletes/gets/updates
description:
   - This module allows you to create, modify, get and delete Zabbix action entries.
version_added: "1.0"
author:
    - "@daianmartinho"
requirements:
    - "python >= 2.6"
    - "zabbix-api >= 0.5.3"
options:
    action_name:
        description:
            - Name of the action in Zabbix.
        required: true
    status:
        description:
            - Type of action. (4 - active, 5 - passive)
        required: false
        choices: ['active', 'passive']
        default: "active"
    state:
        description:
            - State of the action.
            - On C(present), it will create if action does not exist or update the action if the associated data is different.
            - On C(absent) will remove a action if it exists.
        required: false
        choices: ['present', 'absent']
        default: "present"
    esc_period:
        description:
            - Default operation step duration.
            - Must be greater than 60 seconds.
            - Accepts seconds, time unit with suffix and user macro.
        required: true
        default: "2m"
    eventsource:
        description:
            - (constant) Type of events that the action will handle. 
            - Possible values: 
                - 0 (event created by a trigger)
                - 1 (event created by a discovery rule)
                - 2 (event created by active agent auto-registration)
                - 3 (internal event)
        choices: ['0','1','2','3']
        default: "0"
        required: true
    operations:
        description:
            - defines an operation that will be performed when an action is executed
        required: true
        default: {}
    
extends_documentation_fragment:
    - zabbix
'''

EXAMPLES = '''
- name: Create a new action or update an existing action info
  local_action:
    module: zabbix_action
    server_url: http://monitor.example.com
    login_user: username
    login_password: password
    action_name: Exampleaction
    status: active
    state: present
    esc_period: 2m
    eventsource: 1
    operations:
        -   operationtype: 0
            esc_period: 0s
            esc_step_from: 1
            esc_step_to: 2
            evaltype: 0
            opmessage_grp:
                usrgrpid: 7
            opmessage:
                default_msg: 1
                mediatypeid: 1
        -   operationtype: 1
            esc_step_from: 3
            esc_step_to: 4
            evaltype: 0
            opconditions:
                conditiontype: 14
                operator: 0
                value: 0
            opcommand_grp:
                groupid: 2
            opcommand:
                type: 4
                scriptid: 3

'''

RETURN = ''' # '''


from ansible.module_utils.basic import AnsibleModule
try:
    from zabbix_api import ZabbixAPI

    HAS_ZABBIX_API = True
except ImportError:
    HAS_ZABBIX_API = False


class Action(object):
    def __init__(self, module, zbx):
        self._module = module
        self._zapi = zbx
        self.existing_data = None

    def action_exists(self, action_name):
        result = self._zapi.action.get({
            'output': 'extend', 
            'selectOperations': 'extend',
            "selectRecoveryOperations": "extend",
            "selectFilter": "extend",
            'filter': {'name': action_name}})

        if len(result) > 0 and 'actionid' in result[0]:
            self.existing_data = result[0]
            return result[0]['actionid']
        else:
            return result

    def add_action(self, data):
        try:
            if self._module.check_mode:
                self._module.exit_json(changed=True)

            parameters = {}
            for item in data:
                if data[item]:
                    parameters[item] = data[item]

            action_ids_list = self._zapi.action.create(parameters)
            self._module.exit_json(changed=True,
                                   result="Successfully added action %s (%s)" %
                                          (data['name'], data['status']))
            if len(action_ids_list) >= 1:
                return action_ids_list['actionids'][0]
        except Exception as e:
            self._module.fail_json(msg="Failed to create action %s: %s" %
                                   (data['name'], e))

    def delete_action(self, action_id, action_name):
        try:
            if self._module.check_mode:
                self._module.exit_json(changed=True)
            self._zapi.action.delete([action_id])
            self._module.exit_json(changed=True,
                                   result="Successfully deleted" +
                                          " action %s" % action_name)
        except Exception as e:
            self._module.fail_json(msg="Failed to delete action %s: %s" %
                                       (action_name, str(e)))

    def compile_interface_params(self, new_interface):
        old_interface = {}
        if 'interface' in self.existing_data and \
           len(self.existing_data['interface']) > 0:
            old_interface = self.existing_data['interface']

        final_interface = old_interface.copy()
        final_interface.update(new_interface)
        final_interface = dict((k, str(v)) for k, v in final_interface.items())

        if final_interface != old_interface:
            return final_interface
        else:
            return {}

    def update_action(self, action_id, data):
        try:
            if self._module.check_mode:
                self._module.exit_json(changed=True)
            parameters = {'actionid': action_id}

            for item in data:
                if data[item] and item in self.existing_data and \
                   self.existing_data[item] != data[item]:
                    parameters[item] = data[item]

            if 'interface' in parameters:
                parameters.pop('interface')

            if 'interface' in data and data['status'] == '6':
                new_interface = self.compile_interface_params(data['interface'])
                if len(new_interface) > 0:
                    parameters['interface'] = new_interface

            if len(parameters) > 1:
                self._zapi.action.update(parameters)
                self._module.exit_json(
                    changed=True,
                    result="Successfully updated action %s (%s)" %
                           (data['host'], action_id)
                )
            else:
                self._module.exit_json(changed=False)
        except Exception as e:
            self._module.fail_json(msg="Failed to update action %s: %s" %
                                       (data['host'], e))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            server_url=dict(type='str', required=True, aliases=['url']),
            login_user=dict(type='str', required=True),
            login_password=dict(type='str', required=True, no_log=True),            
            http_login_user=dict(type='str', required=False, default=None),
            http_login_password=dict(type='str', required=False,
                                     default=None, no_log=True),
            validate_certs=dict(type='bool', required=False, default=True),
            timeout=dict(type='int', default=10),
            action_name=dict(type='str', required=True, default=None),
            status=dict(default="active", choices=['active', 'passive']),
            state=dict(default="present", choices=['present', 'absent']),
            esc_period=dict(type='str', required=False, default='2m'),
            eventsource=dict(type='int', required=True, default=None),            
            operations=dict(type='list', required=True)
        ),
        supports_check_mode=True
    )

    if not HAS_ZABBIX_API:
        module.fail_json(msg="Missing requried zabbix-api module" +
                             " (check docs or install with:" +
                             " pip install zabbix-api)")

    server_url = module.params['server_url']
    login_user = module.params['login_user']
    login_password = module.params['login_password']
    http_login_user = module.params['http_login_user']
    http_login_password = module.params['http_login_password']
    validate_certs = module.params['validate_certs']
    timeout = module.params['timeout']
    action_name = module.params['action_name']
    status = module.params['status']
    state = module.params['state']
    esc_period = module.params['esc_period']
    eventsource = module.params['eventsource']
    operations = module.params['operations']

    # convert enabled to 0; disabled to 1
    status = 6 if status == "passive" else 5

    zbx = None
    # login to zabbix
    try:
        zbx = ZabbixAPI(server_url, timeout=timeout,
                        user=http_login_user,
                        passwd=http_login_password,
                        validate_certs=validate_certs)
        zbx.login(login_user, login_password)
    except Exception as e:
        module.fail_json(msg="Failed to connect to Zabbix server: %s" % e)

    action = Action(module, zbx)

    # check if action already exists
    action_id = action.action_exists(action_name)

    if action_id:
        if state == "absent":
            # remove action
            action.delete_action(action_id, action_name)
        else:
            action.update_action(action_id, {
                'name': action_name,                
                'status': str(status),
                'esc_period': str(esc_period),
                'eventsource': int(eventsource),
                'operations': operations
            })
    else:
        if state == "absent":
            # the action is already deleted.
            module.exit_json(changed=False)

        action_id = action.add_action(data={
            'name': action_name,                
            'status': str(status),
            'esc_period': str(esc_period),
            'eventsource': int(eventsource),
            'operations': operations
        })


if __name__ == '__main__':
    main()
