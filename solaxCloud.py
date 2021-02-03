import requests
import os
from urllib.parse import urljoin,urlencode
import json

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
    try:
        response = requests.get(apiUrl)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)
    except requests.exceptions.RequestException as err:
        raise SystemExit(err)
    jprint(response.json())
    return response.json()
