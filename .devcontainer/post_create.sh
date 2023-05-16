#!/bin/bash

set -e

sudo apt update
sudo apt install -y build-essential python3-gdal libgdal-dev gdal-bin awscli

pip3 --disable-pip-version-check install  "setuptools<58.0"

pip3 --disable-pip-version-check install --user -r requirements.txt
