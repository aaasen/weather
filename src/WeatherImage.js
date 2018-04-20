import React from 'react';

export default function WeatherImage ({ model, region, hour }) {
    const hourString = hour.toString().padStart(2, '0');
    const url = `https://atmos.washington.edu/wrfrt/data/timeindep/images_d3/${region}${model}1.${hourString}.0000.gif`

    return (
        <img src={url}/>
    );
}
