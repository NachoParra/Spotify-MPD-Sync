#! /usr/bin/env python

import spotipy
from spotipy import oauth2
from spotipy.oauth2 import SpotifyClientCredentials
from mpd import MPDClient
from mpd.base import CommandError
from collections import defaultdict
from re import sub
from os import environ
import os

class Spotify():
    def __init__(self):
        self.client_id = os.getenv('SPOTIPY_CLIENT_ID')
        self.client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')
        self.redirect_uri = os.getenv('SPOTIPY_REDIRECT_URI')
        self.username = environ.get("SPOTIFY_USERNAME")
        self.cache_path = ".cache-" + str(self.username)
        self.scope = 'user-library-read playlist-read-private user-read-currently-playing'
        self.sp_oauth = oauth2.SpotifyOAuth(self.client_id, self.client_secret, self.redirect_uri, scope=self.scope, cache_path=self.cache_path)
        token_info = self.sp_oauth.get_cached_token()
        if token_info:
            print ("Found cached token!")
            access_token = token_info['access_token']
        else:
            while True:
                auth_url = sp_oauth.get_authorize_url()
                print(auth_url)
                response = input("Enter the URL you were redirected to: ")
                code = sp_oauth.parse_response_code(response)
                token_info = sp_oauth.get_access_token(code)
                # Auth'ed API request
                if token_info:
                    access_token = token_info['access_token']
                    break

        self.sp = spotipy.Spotify(access_token)

        self.mpd_client = MPDClient()
        #self.mpd_client.connect("127.0.0.1", 6600)
        self.mpd_server = environ.get("MOPIDY_SERVER")
        self.mpd_client.connect(str(self.mpd_server), 6600)

        self._playlists = defaultdict(lambda: [])

    def fmt_track(self, track_id):
        return "spotify:track:{0}".format(track_id)

    def sanitize_playlist(self, playlist):
        return sub(r'[\/\n\r]', "", playlist)

    @property
    def playlists(self):
        if self._playlists:
            return self._playlists

        #playlists = self.sp.user_playlists(self.username)
        playlists = self.sp.current_user_playlists()

        while playlists:
            for playlist in playlists['items']:
                for track in self.sp.user_playlist(self.username,
                                                   playlist["id"],
                                                   fields="tracks,next")["tracks"]["items"]:

                    self._playlists[self.sanitize_playlist(playlist["name"])].append(
                            self.fmt_track(track["track"]["id"])
                        )

            if playlists["next"]:
                playlists = self.sp.next(playlists)
            else:
                playlists = None

        return self._playlists

    def persist_playlists(self):
        for playlist in self.playlists:
            try:
                # The actual MPD playlist as it currently is
                current_playlist_stored = set(self.mpd_client.listplaylist(playlist))
            except CommandError as e:
                print(e)
                current_playlist_stored = set()

            # The spotify playlist as it currently is
            new_playlist = self.playlists[playlist]

            if set(new_playlist) != current_playlist_stored:
                print("{0} has missing tracks, trying to add them".format(playlist))
                try:
                    self.mpd_client.playlistclear(playlist)
                except CommandError as e:
                    print(e)

                # Now it should be safe to add any new playlist items
                for track_id in new_playlist:
                    try:
                        self.mpd_client.playlistadd(playlist, track_id)
                    except CommandError as e:
                        print(e)
                        print("Could not add {0}".format(track_id))
                        continue


def run_sync():
    spotify = Spotify()
    spotify.persist_playlists()
