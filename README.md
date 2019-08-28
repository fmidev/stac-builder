# Stac-builder

This is a prototype utility to convert BEAM-DIMAP metadata into STAC items (https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md)
The resulting catalogs are in use at https://pta.fmi.fi/ for demonstration

The tool has three parts:
* `tiff2stac.py` - lists geotiff files on S3 and produces STAC items of them (items are written in the folder `item/`) for Sentinel 2 mosaics
* `s1-tiff2stac.py` - same as above, but for Sentinel 1 mosaics
* `dim2stac.py` - lists DIM files on S3 and produces STAC items of them (items are written in the folder `item/`) for S1 single images
* `stac-item2index.py` - creates a stac catalog of the STAC items in folder `item/` (catalog files are written in the folder `catalog/`)

## Requirements

The prototype is built using Python 3.6 and a bunch of other tools. Development was done on Ubuntu 18.04. The Python packages used are listed in requirements.txt.

GDAL 2.4.0 is also required (3.0.1 also works), for Ubuntu, you can install it using the [UbuntuGIS PPA](https://launchpad.net/~ubuntugis/+archive/ubuntu/ppa)

## Usage

You need to have a s3cmd configuration file with the right access keys and host_base configuration. 

### Sentinel 2

`python3 tiff2stac.py -b pta --s3_prefix sen2/s2m --h_url https://pta.data.lit.fmi.fi/ --b_url https://pta.data.lit.fmi.fi/stac/`

### Sentinel 1 (dims)

`python3 dim2stac.py -b pta --s3_prefix sen1/s1_grd_meta_prep --h_url https://pta.data.lit.fmi.fi/ --b_url https://pta.data.lit.fmi.fi/stac/`

If the s3cmd config file is not at $HOME/.s3cfg, you can specify the path to the file via the parameter `--s3cfg`.

### Creating the catalog

`python3 stac-item2index.py`

## Interesting things

There is a project for OL + COG that could provide an interesting viewer int he future: https://github.com/cholmes/cog-map

