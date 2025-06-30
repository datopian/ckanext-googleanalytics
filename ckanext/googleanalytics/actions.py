from . import dbutil
from ckan.plugins import toolkit
import json
import logging

log = logging.getLogger(__name__)

@toolkit.side_effect_free
def resource_stat(context, data_dict):
    '''
    Fetch resource stats
    '''
    resource_id = data_dict['resource_id']
    result = dbutil.get_resource_stat(resource_id)[0]
    return json.dumps(result)

@toolkit.side_effect_free
def package_stat(context, data_dict):
    '''
    Fetch package stats
    '''
    package_id = data_dict['package_id']
    try:
        result = dbutil.get_package_stat(package_id)[0]
    except Exception as e:
        return '0'
    return json.dumps(result)
