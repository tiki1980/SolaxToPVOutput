import requests
import os
from urllib.parse import urljoin,urlencode
import json
import logging

logger = logging.getLogger(__name__)

SOLAXCLOUD_URL = 'https://www.solaxcloud.com:9443/'

#https://www.solaxcloud.com:9443/proxy/api/getRealtimeInfo.do?tokenId={tokenId}&sn={sn}

#print json object for debugging purposes
def jprint(obj):
    # create a formatted string of the Python JSON object
    text = json.dumps(obj, sort_keys=True, indent=4)
    print(text)

#create url
def build_api_url(token, sn):
    BASE_URL = os.environ.get("BASE_URL", SOLAXCLOUD_URL)
    path = f"proxy/api/getRealtimeInfo.do"
    query = "?" + urlencode(dict(tokenId=token, sn=sn))
    return urljoin(BASE_URL, path + query)

#getrealtime info api call
def getRealTimeInfo(token, registration_nr):
    apiUrl = build_api_url(token, registration_nr)
    logger.debug(f'Api url: {str(apiUrl)}')
    try:
        response = requests.get(apiUrl)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        logger.exception('HTTP Error')
    except requests.exceptions.RequestException as err:
        logger.exception('Exception occurred')
    logger.info(f'HTTP Response status code: {str(response.status_code)}')
    logger.debug(str(response.text))
    return response.json()
