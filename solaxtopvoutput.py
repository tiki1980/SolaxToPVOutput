#!/usr/bin/env python3
"""SolaxToPVOutput - copies Solax generation data to PVOutput"""

import logging
import time
import os
from urllib.parse import urljoin,urlencode
import json
import yaml
import requests

# MIT License
#
# Copyright (c) 2021 tiki1980
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Changelog:
# v0.2    10/Feb/24 Re-factored as a single file, added consumption data. Pylint score = 10/10
# v0.3    10/Feb/24 added test for valid consumption data

VERSION = "v0.3"

def jprint(obj):
    """ print json object for debugging purposes"""
    # create a formatted string of the Python JSON object
    text = json.dumps(obj, sort_keys=True, indent=4)
    print(text)

def get_real_time_solax_data(token, registration_nr):
    """ Real time data api call to Solax SolaxCloud"""

    api_url = "https://www.solaxcloud.com:9443/proxy/api/getRealtimeInfo.do"
    query = "?" + urlencode({"tokenId": token, "sn": registration_nr})
    api_url =  urljoin(api_url, query)

    logger.debug("Api url: %s", str(api_url))
    try:
        response = requests.get(api_url, timeout = 10)
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        logger.exception("HTTP Error")
    except requests.exceptions.RequestException:
        logger.exception("Exception occurred")
    logger.debug("HTTP Response status code: %s", str(response.status_code))
    logger.info(str(response.text))
    return response.json()

def upload_to_pvoutput(pvoutput_data):
    """ API call to upload 5-minute data"""

    api_url = "https://pvoutput.org/service/r2/addstatus.jsp"
    sys_id = config["PVOutput"]["systemid"]
    apikey = config["PVOutput"]["apikey"]

    headers_pv = {
        'X-Pvoutput-SystemId': str(sys_id),
        'X-Pvoutput-Apikey': str(apikey)
    }
    try:
        logger.debug("Api url: %s", str(api_url))
        logger.info("pvoutput_data: %s", str(pvoutput_data))
        response = requests.post(api_url, headers=headers_pv, data=pvoutput_data, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        logger.exception('HTTP Error')
    except requests.exceptions.RequestException:
        logger.exception('Exception occurred')
    logger.info("HTTP Response status code: %s", str(response.status_code))
    logger.debug(str(response.text))
    return response.text


if __name__ == '__main__':

    # Parse YAML configuration file
    with open(os.path.join(os.path.dirname(__file__),"config.yml"), "r", encoding='UTF-8') \
        as yamlfile:
        try:
            config = yaml.load(yamlfile, Loader=yaml.FullLoader)
        except yaml.YAMLError as err:
            raise SystemExit(err) from err

    # Enable logging, get log level from config file
    numericLogLevel = getattr(logging, config["SolaxToPVOutput"]["logLevel"].upper(), 10)
    logFile = os.path.join(os.path.dirname(__file__),"solaxtopvoutput.log")
    logging.basicConfig(
            filename=logFile,
            #encoding='utf-8', only supported in python 3.9
            level=numericLogLevel,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
    logger = logging.getLogger(__name__)
    logging.getLogger("urllib3").setLevel(logging.WARNING)  # Ignore urllib3 debug info if set
    logging.info("Started SolaxToPVOutput, version: %s", VERSION)

    while True:
        # Request latest data from SolaxCloud
        SolaxData = get_real_time_solax_data(config["SolaxCloud"]["tokenId"], \
            config["SolaxCloud"]["registrationNr"])

        # If latest reading is successful, parse data and upload to PVOutput
        if SolaxData["success"] is True:
            # Create 5-minute payload data for PVOutput
            # Useful fields in SolaxData (with sample data):
            # "acpower":2670.0,  # Instantaneous ac power generated (W)
            # "yieldtoday":6.1,  # Generation energy today (kWh)
            # "yieldtotal":1365.3,  # Lifetime generation energy
            # "feedinpower":2527.0,  # Instantaneous export power (W)
            # "feedinenergy":9.64,  # Export energy today (kWh)
            # "consumeenergy":22.2,  # Lifetime import energy (while running)

            gen_tot_wh: int = SolaxData["result"]["yieldtotal"] * 1000  # v1 = Lifetime energy gen
            gen_pwr: int = SolaxData["result"]["acpower"]  # v2 = Power generation

            cons_tot_wh: int = 0
            con_pwr: int = 0
            if SolaxData["result"]["consumeenergy"] is not None:
                cons_tot_wh = SolaxData["result"]["consumeenergy"] * 1000 # v3 = Energy consumption
            if SolaxData["result"]["feedinpower"] is not None:
                con_pwr = min(gen_pwr - SolaxData["result"]["feedinpower"], 0)  # v4 = Power cons

            upld_date_time = SolaxData["result"]["uploadTime"]
            upld_date = upld_date_time[0:10].replace('-','')
            upld_time = upld_date_time[11:16]

            pvoutput_payload = {
                'd': str(upld_date),
                't': str(upld_time),
                'v1': str(gen_tot_wh),
                'v2': str(gen_pwr),
                'v3': str(cons_tot_wh),
                'v4': str(con_pwr),
                'c1': "1"
            }

            pvoutput = upload_to_pvoutput(pvoutput_payload)

        else:
            logger.error("SolaxCloud returned failure in Json")
            logger.error(str(SolaxData))

        logger.debug("Sleeping for 5 minutes")
        time.sleep(300)
