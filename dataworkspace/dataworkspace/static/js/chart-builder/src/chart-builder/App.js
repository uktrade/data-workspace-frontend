import React from 'react';
import PlotlyEditor, {DefaultEditor} from 'react-chart-editor';
import plotly from 'plotly.js/dist/plotly';
import 'react-chart-editor/lib/react-chart-editor.css';

import './App.css';
import './utils/maps';
import {availableCharts, axisMap, queryStates} from "./constants";
import LoadingModal from "./components/LoadingModal";
import ErrorModal from "./components/ErrorModal";

// Hide unused parts of the UI
DefaultEditor.prototype.hasTransforms = () => false;
DefaultEditor.prototype.hasMaps = () => false;

class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      queryRunning: true,
      queryError: null,
      loadingData: false,
      savingChart: false,
      saveError: null,
      editorRevision: 0,
      dataSources: {},
      dataSourceOptions: [],
      traces: [],
      layout: {},
      frames: [],
    }
  }

  componentDidMount() {
    this.pollForQueryResults();
  }

  pollForQueryResults = () => {
    fetch(`/data-explorer/charts/query-status/${this.props.chartId}/`)
      .then((resp) => resp.json())
      .then((data) => {
        this.setState({
          queryError: data.error,
          queryRunning: data.state === queryStates.running,
          dataSourceOptions: data.columns.map(name => ({
            value: name,
            label: name,
          })),
        });
        if (data.state === queryStates.running) {
          setTimeout(() => {
            this.pollForQueryResults()
          }, 1000);
        }
        else if (data.state === queryStates.complete) {
          this.fetchQueryResults();
        }
    });
  }

  fetchQueryResults = () => {
    this.setState({ loadingData: true });
    fetch(`/data-explorer/charts/query-results/${this.props.chartId}/`)
      .then((resp) => resp.json())
      .then((data) => {
        console.log(`Fetched ${data.total_rows} rows in ${data.duration} seconds`);
        const dataSources = { ...this.state.dataSources, ...data.data };
        const newState = {
          dataSources,
          loadingData: false,
          editorRevision: this.state.editorRevision + 1,
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
      }).catch(e => {
        console.error(e);
        this.setState({
          loadingData: false,
          queryError: 'An error occurred while running your query'
        });
    });
  }

  resetChart = () => {
    this.setState({
      editorRevision: this.state.editorRevision + 1,
      layout: {},
      frames: [],
      traces: [],
    })
  }

  showStatusModal = () => {
    if (this.state.queryRunning) return <LoadingModal message="Running query" />;
    if (this.state.loadingData) return <LoadingModal message="Fetching data" />;
    if (this.state.savingChart) return <LoadingModal message="Saving chart" />;
    if (this.state.queryError) {
      return (
        <ErrorModal
          title="Failed to run your query"
          message={this.state.queryError}
          backLink={this.props.backLink}
        />
      );
    }
    if (this.state.saveError) {
      return (
        <ErrorModal
          title="Failed to save your chart"
          message={this.state.saveError}
          backLink={this.props.backLink}
        />
      );
    }
  }

  saveChart = () => {
    const that = this;
    this.setState({ savingChart: true });
    fetch(`/data-explorer/charts/edit/${this.props.chartId}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.getElementsByName('csrfmiddlewaretoken')[0].value,
      },
      body: JSON.stringify({
        config: {
          traces: this.state.traces.map(chart => {
            return {
              ...chart,
              x: [],
              y: [],
              lat: [],
              lon: [],
              text: [],
              // Our problem is transforms do not currently get updated when
              // the table is updated
              // transforms: chart.transforms ? chart.transforms.map(transform => {
              //   transform.target = [];
              //   return transform;
              // }) : [],
            }
          }),
          layout: this.state.layout,
          frames: this.state.frames,
        }
      }),
    })
    .then(function(resp) {
      that.setState({ savingChart: false });
      if (!resp.ok) {
        that.setState({ saveError: "Error saving your chart, please try again."})
        throw new Error('Failed to save chart');
      }
    })
    .catch((error) => {
      that.setState({ saveError: "Error saving your chart, please try again."})
      throw new Error(error);
    });
  }

  render() {
    return (
      <div className="app">
        {this.showStatusModal()}
        <div className="govuk-width-container">
          <div className="govuk-grid-row">
            <div className="govuk-grid-column-full" id="plotly-editor">
              <PlotlyEditor
                data={this.state.traces}
                layout={this.state.layout}
                config={{ editable: true, mapboxAccessToken: '-' }}
                frames={this.state.frames}
                dataSources={this.state.dataSources}
                dataSourceOptions={this.state.dataSourceOptions}
                plotly={plotly}
                onUpdate={(traces, layout, frames) => {
                  this.setState({traces, layout, frames});
                }}
                useResizeHandler
                debug
                advancedTraceTypeSelector
                traceTypesConfig={availableCharts}
                revision={this.state.editorRevision}
              >
                <DefaultEditor />
              </PlotlyEditor>
              <div className="govuk-grid-row chart-toolbar">
                <div className="govuk-grid-column-one-third">
                  <a className="govuk-button govuk-button--secondary" href={this.props.backLink}>
                    Back
                  </a>
                </div>
                <div className="govuk-grid-column-two-thirds">
                  <a href={`/data-explorer/charts/delete/${this.props.chartId}`} role="button" draggable="false" className="govuk-button govuk-button--warning">
                    Delete Chart
                  </a>
                  <button className="govuk-button govuk-button--secondary" onClick={() => this.resetChart()}>
                    Clear Chart
                  </button>
                  <button className="govuk-button" onClick={() => this.saveChart()}>
                    Save Chart
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}

export default App;
