import json 
import os
import argparse

from pathlib import Path

import item_builder as item_builder
import catalog_builder as catalog_builder

parser = argparse.ArgumentParser(description='STAC builder.')
parser.add_argument("dataset_configuration_file", help="location of the dataset's configuration file")
parser.add_argument("s3_configuration_file", help="location of the s3 configuration file")
args = parser.parse_args()
dataset_configuration_file = args.dataset_configuration_file
s3_configuration_file = args.s3_configuration_file
print("Dataset configuration file location is:", dataset_configuration_file)
print("S3 configuration file location is:", s3_configuration_file)

# Dataset configuration file
conf_f = open(dataset_configuration_file)
conf = json.load(conf_f)

# S3 config
conf_s3_f = open(s3_configuration_file)
conf_s3 = json.load(conf_s3_f)

# Create destinations for items if they do not exist yet
localItemPath = Path(conf["destination"]["localItemPath"])
if localItemPath.exists() == False:
    localItemPath.mkdir(parents=True)


# Build STAC

# Create items
print("************************* Item builder starts. *************************")
item_builder.main(conf, conf_s3)

# Create catalog
if 'noCatalog' in conf:
    print("************************* No catalog will be built as noCatalog is True *************************")    
else:
    print("************************* Catalog builder starts. *************************")
    # Create destinations for catalog if they do not exist yet
    localCatalogPath = Path(conf["destination"]["localCatalogPath"])
    if localCatalogPath.exists() == False: 
        localCatalogPath.mkdir(parents=True)

    catalog_builder.main(conf)

print("************************* STAC is ready! *************************")