import React from 'react';
import Plot from 'react-plotly.js';

import './App.css';
import '../chart-builder/utils/maps';
import {axisMap} from "../chart-builder/constants";

class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      loadingData: true,
      dataSources: {},
      traces: [],
      layout: {},
      frames: [],
    }
  }

  componentDidMount() {
    this.fetchQueryResults();
  }

  fetchQueryResults = () => {
    fetch(`/datasets/${this.props.datasetId}/chart/${this.props.chartId}/data`)
      .then((resp) => resp.json())
      .then((data) => {
        const dataSources = { ...this.state.dataSources, ...data.data };
        const newState = {
          dataSources,
          loadingData: false,
          layout: this.props.chartData.layout ? this.props.chartData.layout : {},
          frames: this.props.chartData.frames ? this.props.chartData.frames : [],
        };
        if (this.props.chartData.traces) {
          newState.traces = this.props.chartData.traces.map(trace => {
            trace[axisMap[trace.type].x] = dataSources[trace[axisMap[trace.type].xsrc]];
            trace[axisMap[trace.type].y] = dataSources[trace[axisMap[trace.type].ysrc]];
            if (trace.textsrc) trace.text = dataSources[trace.textsrc];
            return trace;
          });
        }
        this.setState(newState)
      }).catch((err) => {
        console.error('ERROR', err)
        this.setState({
          loadingData: false,
          queryError: 'An error occurred while fetching data for the chart'
        });
    });
  }

  render() {
    return (
      <div className="app">
        {this.state.loadingData ?
          <div className="govuk-grid-row">
            <div className="govuk-!-margin-bottom-4 loading-spinner chart-loading-spinner" />
            <p className="govuk-heading-s" style={{textAlign: "center"}}>Loading chart...</p>
          </div>
          :
           <Plot
              data={this.state.traces}
              layout={this.state.layout}
              config={{ mapboxAccessToken: '-' }}
              frames={this.state.frames}
              dataSources={this.state.dataSources}
              useResizeHandler
              style={{width: '100%', height: '100%'}}
              divId="embedded-chart"
            />
        }
        </div>
    );
  }
}

export default App;
