import React, { Component } from 'react';
import logo from './logo.svg';
import './App.css';
import WeatherImage from './WeatherImage';
import { Models, Regions } from './constants';
import 'rc-slider/assets/index.css';
import Slider from 'rc-slider';
import { fromPairs, range } from 'lodash';
import moment from 'moment';

const marks = Object.assign({
  0: '0',
}, fromPairs(range(6, 84).map(i => [i, i % 6 === 0 ? i.toString() : ''])))

class App extends Component {
  constructor(props) {
    super(props)

    this.state = {
      hour: 0,
      region: Regions.WesternWashington
    };

    this.onChange = this.onChange.bind(this);
  }

  onChange(hour) {
    this.setState({ hour });
  }

  render() {
    return (
      <div className="App">
        <h2>
          Weather data from{' '}
          <a href="https://atmos.washington.edu/wrfrt/data/timeindep/gfsinit.d3.6hr.html" target="blank">
            UW
          </a>
        </h2>


        <div className="HourSlider">
          <Slider min={0} max={84} marks={marks} step={null} onChange={this.onChange} defaultValue={0} />
        </div>

        <h1>
          {moment().add(this.state.hour + 1, 'hours').format('dddd, hA')}
        </h1>

        <WeatherImage model={Models.Precip} region={this.state.region} hour={this.state.hour}/>
        <WeatherImage model={Models.RainAndSnow} region={this.state.region} hour={this.state.hour}/>
      </div>
    );
  }
}

export default App;
