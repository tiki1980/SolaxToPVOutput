# SolaxToPVOutput
My first python project, probably not the greatest code but it works :)

Upload the latest reading from SolaxCloud https://www.solaxcloud.com/ to PvOutput https://pvoutput.org

Pvoutput Api: https://pvoutput.org/help.html#api-addstatus
Solaccloud Api: https://www.solaxcloud.com/#/api (you must be logged in)


How to use:

* Rename config.yml_rename_this to config.yml and fill with your own values
* Install python dependencies: pip install pyyaml requests
* Schedule main.py to run every 5 minutes

For now it prints the output of the api requests to the console, this will be removed in a future release
