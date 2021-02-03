import requests
import os
from urllib.parse import urljoin,urlencode
import json

PVOUTPUT_URL = 'https://pvoutput.org/'

#https://pvoutput.org/help.html#api-addstatus
#https://pvoutput.org/service/r2/addstatus.jsp

#create url can be done simpler but i like this method
def build_api_url():
    BASE_URL = os.environ.get("BASE_URL", PVOUTPUT_URL)
    path = f"/service/r2/addstatus.jsp"
    query = ''
    return urljoin(BASE_URL, path + query)

#getrealtime info api call
def uploadToPvOutput(systemId, apikey, acPower, yieldTodayWh,uploadDate,uploadTime):
    apiUrl = build_api_url()
    pvoutputdata = {
      'd': str(uploadDate),
      't': str(uploadTime),
      'v1': str(yieldTodayWh),
      'v2': str(acPower)
    }

    headerspv = {
        'X-Pvoutput-SystemId': str(systemId),
        'X-Pvoutput-Apikey': str(apikey)
    }
    try:
        response = requests.post(apiUrl, headers=headerspv, data=pvoutputdata)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)
    except requests.exceptions.RequestException as err:
        raise SystemExit(err)
    print(response.status_code, response.text)
    return response.text
