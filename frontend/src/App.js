import React, { Component } from 'react';
import logo from './logo.svg';
import './App.css';



class App extends Component {
  constructor(props) {
    super(props);
    this.state = {
      videos: [],
      currentVideo: null,
      playlist: []
    };

    window.nextvideo = this.next.bind(this);
    this.load(this.next);
  }

  componentDidMount() {
    this.timerID = setInterval(
      () => this.load(),
      2500
    );
  }

  componentWillUnmount() {
    clearInterval(this.timerID);
  }

  load(cb) {
    this.loadJSON((data) => {
      let videoIds = Object.keys(this.state.videos);
      let newVideoIds = Object.keys(data.videos);
      let playlist = this.state.playlist;
      for (var key in newVideoIds) {
        if (!(key in videoIds)) {
          console.log("Directly added video to playlist", this.state.videos[parseInt(key)+1])
          playlist.push(parseInt(key)+1);
        }
      }
      this.setState(Object.assign({}, data, {playlist}));
      console.log("Refreshed database")
      if(cb) {cb.bind(this)()}
    });
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
    let newVideo, currentVideo, playlist;

    if (Object.keys(this.state.videos).length == 0) {
      console.log("No videos available for play next.");
      this.setState({currentVideo: null});

    } else {
      playlist = this.state.playlist;
      if (playlist.length < 1) {
        console.log("Playlist is empty");
        playlist = this.createPlaylist()
      }
      currentVideo = playlist.pop();
      console.log("Now playing", currentVideo, this.state.videos[currentVideo]);
      this.setState({playlist, currentVideo});
    }

    // } else if(!this.state.currentVideo) {
    //   new_video = Object.keys(this.state.videos).length > 0 ? Object.keys(this.state.videos)[0] : null;
    //   console.log("Starting playback with video", new_video, this.state.videos[new_video]);
    //   this.setState({currentVideo: new_video});

    // } else {
    //   new_video = parseInt(this.state.currentVideo) + 1;
    //   if(new_video > Object.keys(this.state.videos).length) {
    //     new_video = 1;
    //   }
    //   console.log("Now playing", new_video, this.state.videos[new_video]);
    //   this.setState({currentVideo: new_video});
    // }
  }

  createPlaylist() {
    console.log("Playlist refill..");
    let videoIds = Object.keys(this.state.videos);
    let playlist = Array(5).fill(1).map(
      () => videoIds[Math.floor(Math.random()*videoIds.length)]
    );
    return playlist
  }

  componentDidUpdate(prevProps, prevState) {
    if (prevState.currentVideo !== this.state.currentVideo && "player" in Object.keys(window)) {
      console.log("Load new video and start playback");
      window.player.load();
      window.player.play();
    }
  }

  render() {
    let player;
    let video = this.state.videos[this.state.currentVideo];
    let url = video ? video.url : "";

    if (this.state.currentVideo) {
      player = <VideoPlayer
            source={video.url}
            onEnded={() => {this.next()}}
          />;
    } else {
      player = "No video loaded.";
    }

    return (
      <div className="App">
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

  componentDidUpdate(prevProps, prevState) {
    if (prevProps.source !== this.props.source) {
      console.log("Updated component source, reload & play..");
      this.player.load();
      this.player.play();
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


export default App;
