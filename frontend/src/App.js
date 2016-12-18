import React, { Component } from 'react';
import './App.css';



class App extends Component {
  constructor(props) {
    super(props);
    this.state = {
      videos: [],
      currentVideo: null,
      playlist: [],
      infos: [],
      config: {}
    };

    window.nextvideo = this.next.bind(this);
    this.load(this.next);
  }

  componentDidMount() {
    this.timerID = setInterval(
      () => this.load(),
      1000
    );
    this.addInfo("Ready");
  }

  componentWillUnmount() {
    clearInterval(this.timerID);
  }

  load(cb) {
    // cb is only set if this is the first run during startup

    this.loadJSON((data) => {
      let videoIds = Object.keys(this.state.videos);
      let newVideoIds = Object.keys(data.videos);
      let playlist = this.state.playlist;
      if (!cb) {
        for (var key in newVideoIds) {
          if (!(key in videoIds)) {
            console.log("Directly added video to playlist", this.state.videos[parseInt(key)])
            this.addInfo("!!! NEW CLIP INCOMING !!!");
            playlist.push(parseInt(key)+1);
          }
        }
      }
      this.setState(Object.assign({}, data, {playlist}));
      if(cb) {
        this.addInfo("Got " + Object.keys(data.videos).length + " items")
        cb.bind(this)()
      }
    });
  }

  addInfo(info) {
    let infos = Object.assign([], this.state.infos);
    infos.push(info);
    this.setState({infos});
  }

  loadJSON(callback) {
    var jsonObj = new XMLHttpRequest();
    jsonObj.overrideMimeType("application/json");
    jsonObj.open('GET', "/data.json", true);
    jsonObj.onreadystatechange = function () {
      if (jsonObj.readyState == 4 && jsonObj.status == "200") {
        let a = JSON.parse(jsonObj.responseText);
        callback(a);
      }
    };
    jsonObj.send(null);
  }

  next() {
    let currentVideo, playlist;

    if (Object.keys(this.state.videos).length === 0) {
      console.log("No videos available for play next.");
      this.setState({currentVideo: null});

    } else {
      playlist = this.state.playlist;
      if (playlist.length < 1) {
        this.addInfo("Shuffling..");
        playlist = this.createPlaylist()
      }
      currentVideo = playlist.pop();
      let video = this.state.videos[currentVideo];
      this.addInfo("Now playing item #" + currentVideo);
      this.setState({playlist, currentVideo});
    }
  }

  createPlaylist() {
    console.log("Playlist refill..");
    let videoIds = Object.keys(this.state.videos);
    let playlist = Array(5).fill(1).map(
      () => videoIds[Math.floor(Math.pow(Math.random(), 0.8)*videoIds.length)]
    );
    return playlist
  }

  componentDidUpdate(prevProps, prevState) {
    if (prevState.currentVideo !== this.state.currentVideo && "player" in Object.keys(window)) {
      console.log("Load new video and start playback");
      window.player.load();
      window.player.play();
    }

    if (prevState.config.timeout_enabled !== this.state.config.timeout_enabled) {
      if (this.state.config.timeout_enabled) {
        this.addInfo(this.state.config.timeout_delay + "s timeout");
      } else {
        this.addInfo("Timeout disabled");
      }
    }
  }

  render() {
    let player;
    let video = this.state.videos[this.state.currentVideo];

    if (this.state.currentVideo) {
      player = <VideoPlayer
            source={video ? video.url : ""}
            onEnded={() => {this.next()}}
            next={() => {this.next()}}
            onKeyDown={(e) => {this.next()}}
            getConfig={(k) => {return this.state.config[k]}}
          />;
    } else {
      player = "Playlist empty.";
    }

    return (
      <div className="App">
        <Info
          infos={this.state.infos}
        />
        <p>
          {player}
        </p>
      </div>
    );
  }
}

class VideoPlayer extends React.Component {
  constructor(props) {
    super(props);
    this.player = {play: () => {console.log("Cannot play before mount")}};
  }

  componentDidMount() {
    this.timerID = setInterval(
      () => this.checkStillPlaying(),
      1000
    );
  }

  componentDidUpdate(prevProps, prevState) {
    if (prevProps.source !== this.props.source) {
      console.log("Updated component source, reload & play..");
      this.player.load();
      this.player.play();

      if ("timerID2" in Object.keys(this)) {
        clearInterval(this.timerID2);
      }

      if (this.props.getConfig("timeout_enabled") === true) {
        console.log("timeout set");
        this.timerID2 = setInterval(
          () => {
            console.log("Timeout next clip")
            this.props.next()
          },
          parseInt(this.props.getConfig("timeout_delay")) * 1000
        );
      }
    }
  }

  registerPlayer(ref) {
    this.player = ref;
  }

  fullscreen() {
    if (this.player) {
      if (this.player.requestFullscreen) {
        this.player.requestFullscreen();
      } else if (this.player.msRequestFullscreen) {
        this.player.msRequestFullscreen();
      } else if (this.player.mozRequestFullScreen) {
        this.player.mozRequestFullScreen();
      } else if (this.player.webkitRequestFullscreen) {
        this.player.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT);
      }
    } else {
      console.log("No player element for toggling fullscreen");
    }
  }

  checkStillPlaying() {
    if (this.player.paused) {
      this.player.play();
    }
  }

  render() {
    return <video
      onEnded={() => {this.props.onEnded()}}
      ref={(ref) => {this.registerPlayer(ref)}}
      autoPlay
      onClick={() => {this.fullscreen()}}
      id="myvideo" >
          <source src={this.props.source}></source>
    </video>
  }
};

const Info = (props) => {
  let lines = props.infos.slice(-5).map((l, i) => <p key={i}>{l}</p>);
  return <div className="info">
    {lines}
  </div>
};


export default App;
