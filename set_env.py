import yaml
import os

with open("config.yml", "r") as file:
    config = yaml.safe_load(file)

for key, value in config.items():
    print(f"export {key.upper()}={value}")
