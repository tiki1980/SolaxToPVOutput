import yaml

def get_config():
    with open("config.yml", "r") as yamlfile:
        try:
            config = yaml.load(yamlfile, Loader=yaml.FullLoader)
        except yaml.YAMLError as err:
            raise SystemExit(err)
    return config
   