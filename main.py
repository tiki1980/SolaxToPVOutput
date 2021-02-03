from solaxCloud import getRealTimeInfo
from config import get_config
from pvoutput import uploadToPvOutput

#solaxapi variables
config = get_config()

#request latest reading from solaxcloud
solaxData = getRealTimeInfo(config["SolaxCloud"]["tokenId"], config["SolaxCloud"]["registrationNr"])

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
    raise Exception("Solaxcloud returned Failure in Json")


