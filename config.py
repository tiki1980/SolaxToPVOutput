import yaml
import os

def get_config():
    with open(os.path.join(os.path.dirname(__file__),"config.yml"), "r") as yamlfile:
        try:
            config = yaml.load(yamlfile, Loader=yaml.FullLoader)
        except yaml.YAMLError as err:
            raise SystemExit(err)
    return config
   