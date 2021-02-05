# SolaxToPVOutput
My first python project, probably not the greatest code but it works :)

Upload the latest reading from SolaxCloud https://www.solaxcloud.com/ to PvOutput https://pvoutput.org

Pvoutput Api: https://pvoutput.org/help.html#api-addstatus
Solaccloud Api: https://www.solaxcloud.com/#/api (you must be logged in)

How to use:

* Copy config.yml_rename_this to config.yml and fill with your own values
  * PVoutput API key and system id
  * Solaxcloud registration number (not the serial number of the wifi module) + Api key. 
* Install python dependencies: pip install pyyaml requests
* Schedule main.py to run every 5 minutes (or with the term you set in PVOutput)

It currently does only output errors, a feature release will include debug options
