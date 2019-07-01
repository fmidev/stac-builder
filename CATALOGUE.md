# FMI Sentinel STAC Catalogue (FSSC)


Primary goal is to make a STAC catalogue for browsers. The demo will be a browser application that can efficiently 1) identify which sentinel images are relevant in a given geographical extent (taken most likely from the viewing area of a map component) and taken at a specific time, 2) access those web optimized geotiffs to efficiently rertrieve and display the level of detail required for the screen resolution.

## Catalogue organisation

For the browser to be able to achieve this, the catalogue is organised as so:

/
    link rel="child" ->
        /[dataset]
            link rel="child" ->
                /[dataset]/[location]
                    link rel="child" ->
                        /[dataset]/[location]/[time]
                            link rel="item" ->
                                /somehwere/over/the/rainbow.tif.json

### Dataset

Dataset for a DIM file is now just S1, S2, S3 etc. The value is the dataset string as-is.


### Location

Military grid 100km
 vs
geohash with 3 letters - this may be better because it's likely easier to deal with in JS (no need for a grid dataset etc.)
 with
georaptor https://github.com/ashwin711/georaptor ... hmm. maybe not
 .. or
polygon-geohasher https://github.com/Bonsanto/polygon-geohasher



### Time

Each image is binned based on the datetime of the image. The bin is determined by the floor of the datetime (round down to the start of the day). The value for the bin is YYYY-MM-DD



## Generation of the catalogue

1. Process all dim files with dim2stac.py to generate item descriptions
    * Store the attributes dataset, location and time bin in properties, perhaps in a special property value object
2. Process the item descriptions and bin each item based on
    * Dataset
    * Location (in a grid)
    * Time bin
3. Determine collactions
    * Unique combinations of dataset + location + time bin => item collections
    * Unique combinations of dataset + location => location collections
    * Each dataset => dataset collection
    * One root collection
4. Produce JSON files for each collection above





