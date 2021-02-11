import logging
import os
from solaxcloud import getRealTimeInfo
from config import get_config
from pvoutput import uploadToPvOutput

#get config file
config = get_config()

#enable logging
#get log level from config file
numericLogLevel = getattr(logging, config["SolaxToPVOutput"]["logLevel"].upper(), 10)
#determine log path
logFile = os.path.join(os.path.dirname(__file__),"solaxtopvoutput.log")
logging.basicConfig(
        filename=logFile,
        #encoding='utf-8', only supported in python 3.9
        level=numericLogLevel,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
logger = logging.getLogger(__name__)
#ignore urllib3 debug info if set
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.info(f'Started SolaxToPVOutput')

#request latest reading from solaxcloud
solaxData = getRealTimeInfo(config["SolaxCloud"]["tokenId"], config["SolaxCloud"]["registrationNr"])

#if latest reading is succesfull
if solaxData["success"] == 1:
    #get values from json
    yieldTodayKWh = solaxData["result"]["yieldtoday"]
    acPower = solaxData["result"]["acpower"]
    uploadDateTime = solaxData["result"]["uploadTime"]
    #convert kwh to wat hour 
    yieldTodayWh = yieldTodayKWh * 1000 
    #convert datetime to seperate values as requested by pvoutput
    #2021-02-03 17:11:45 to 20210203 & 17:11
    uploadDate = uploadDateTime[0:10].replace('-','')
    uploadTime = uploadDateTime[11:16]

    pvoutput = uploadToPvOutput(config["PVOutput"]["systemid"], config["PVOutput"]["apikey"], acPower, yieldTodayWh,uploadDate,uploadTime)
else:
    logger.error("Solaxcloud returned Failure in Json")
    logger.error(str(solaxData))

logging.info(f'Finished SolaxToPVOutput')
