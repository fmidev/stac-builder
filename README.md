# Stac-builder

This is a prototype utility to convert BEAM-DIMAP metadata into STAC items (https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md)


## Requirements

The prototype is built using Python 3.6 and a bunch of other tools. Development was done on Ubuntu 18.04. The Python packages used are listed in requirements.txt.

GDAL 2.4.0 is also required, for Ubuntu, you can install it using the [UbuntuGIS PPA](https://launchpad.net/~ubuntugis/+archive/ubuntu/ppa)

## Usage

You need to have a s3cmd configuration file with the right access keys and host_base configuration. 

### Sentinel 1

`python3 tiff2stac.py -b pta --s3_prefix sen2/s2m --h_url https://pta.data.lit.fmi.fi/ --b_url https://pta.data.lit.fmi.fi/stac/`

### Sentinel 2 (dims)

`python3 dim2stac.py -b pta --s3_prefix sen1/s1_grd_meta_prep --h_url https://pta.data.lit.fmi.fi/ --b_url https://pta.data.lit.fmi.fi/stac/`

If the s3cmd config file is not at $HOME/.s3cfg, you can specify the path to the file via the parameter `--s3cfg`.

## Interesting things

There is a project for OL + COG that could provide an interesting viewer int he future: https://github.com/cholmes/cog-map

