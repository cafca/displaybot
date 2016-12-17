import React, { Component } from 'react';
import logo from './logo.svg';
import './App.css';

class App extends Component {
  constructor(props) {
    super(props);
    this.state = {videos: []};
    this.load();
  }

  componentDidMount() {
    this.timerID = setInterval(
      () => this.load(),
      3000
    );
  }

  componentWillUnmount() {
    clearInterval(this.timerID);
  }

  loadJSON(callback) {

    callback.bind(this);

    var jsonObj = new XMLHttpRequest();
    jsonObj.overrideMimeType("application/json");
    jsonObj.open('GET', "/data.json", true);
    jsonObj.onreadystatechange = function () {
          if (jsonObj.readyState == 4 && jsonObj.status == "200") {
            // callback(jsonObj.responseText);

            let a = JSON.parse(jsonObj.responseText);
            callback(a);
          }
    };
    jsonObj.send(null);
  }

  load() {
    this.loadJSON((data) => {
      this.setState(data);
    });
  }

  render() {
    return (
      <div className="App">
        <div className="App-header">
          <img src={logo} className="App-logo" alt="logo" />
          <h2>Welcome to React</h2>
        </div>
        <p>{this.state.videos.length}</p>
      </div>
    );
  }
}

export default App;
