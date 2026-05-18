# Denali

Denali weather forecasts via InReach.

## TODO

 - Forecast types
 - Model selection
 - Compression of responses

## Forecasts

Forecast types:
 - 10 day, 1 day resolution, 2 models
 - 5 day, 1 day resolution, 4 models 
 - 1 day, 1 hour resolution, 1 model
 - 5 day, 6 hour resolution, 1 model
 - 5 day, 12 hour resolution, 2 models

 The model choices are:
  - ECMWF
  - GFS
  - ICON
  - Meteoblue



There are three forecast types which correspond to the three type of check in messages:
 - `I'm checking in. Everything is okay.`: 5-day upper mountain forecast.
 - `I'm starting my trip.`: Detailed 2-day upper mountain forecast.
 - `I'm ending my trip.`: 5-day airstrip forecast.
