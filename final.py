from requests import post, get
import requests
import secrets
import string
import webbrowser
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
import re
import time
from dotenv import load_dotenv
import os

# Purpose:
# The purpose of this program is to display the lyrics
# of a currently playing song on Spotify.
# This program utilizes the Spotify and Genius Web API,
# and BeautifulSoup. This program runs in the terminal only.
# Make sure to set up your local server as the program
# relies on localhost to run.

# Data Structure
class TrieNode:
    def __init__(self):
        self.children = dict()
        self.endOfWord = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    # Inserts the string word into the trie.
    def insert(self, word: str) -> None:
        curr = self.root

        for c in word:
            if c not in curr.children:
                curr.children[c] = TrieNode()
            curr = curr.children[c]

        curr.endOfWord = True
        
    # Returns true if the string word is in the trie (i.e., was inserted before), and false otherwise.
    def search(self, word: str) -> bool:
        curr = self.root

        for c in word:
            if c not in curr.children:
                return False
            if curr.endOfWord == True: 
                # if the first string is found, exit out and return True
                return True
            curr = curr.children[c]

        return curr.endOfWord
        
redirect_uri = 'http://localhost'
state = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
scope = 'user-read-currently-playing' # gets song user is currently listening to
url = f'https://accounts.spotify.com/authorize?response_type=token&client_id={os.getenv(client_id)}&scope={scope}&redirect_uri={redirect_uri}&state={state}'
genius_scope = 'me create_annotation manage_annotation vote'

# OAuth process for both Spotify and Genius
response = requests.get(url)
# Open the URL in a web browser for the user to grant access
webbrowser.open(url)
# Wait for user interaction and capture the redirected URL
redirected_url = input("Enter the final URL after granting access: ")

parsed_url = urlparse(redirected_url)
query_params = parse_qs(parsed_url.fragment)

# Extract the values from the query parameters
access_token = query_params.get('access_token', [''])[0]
token_type = query_params.get('token_type', [''])[0]
expires_in = query_params.get('expires_in', [''])[0]
state = query_params.get('state', [''])[0]

genius_url = f'https://api.genius.com/oauth/authorize?client_id={os.getenv(genius_client_id)}&redirect_uri={redirect_uri}&scope={genius_scope}&state={state}&response_type=code'
response = requests.get(genius_url)
# Open the URL in a web browser for the user to grant access
webbrowser.open(genius_url)



# Get Authorization header (OAuth)
def get_auth_header(token):
    return {"Authorization": "Bearer " + token}

# Purpose: 
# The purpose of this function is to
# obtain the currently playing song in a user's Spotify account.
# This is done via a GET request to the Spotify Web API.
# This function takes in a trie data structure and returns 
# a list storing the song name, artist name, and JSON object of the song information.
# i.e. ["song name", "artist", "song JSON object"]
def get_current_song(trie):
    endpoint = 'https://api.spotify.com/v1/me/player/currently-playing'
    headers = get_auth_header(access_token)
    song_info = []

    # A GET request to the API
    response = requests.get(endpoint, headers=headers)
    json_resp = response.json()
    
    song_name = json_resp["item"]["name"]
    artist_name = json_resp["item"]["album"]["artists"][0]["name"]

    artist_name = (artist_name.strip()).upper()
    
    song_info.append(song_name)
    song_info.append(artist_name)
    # adding JSON object of song info
    song_info.append(json_resp) 
    trie.insert(artist_name) 

    return song_info

# Purpose: 
# The purpose of this function is to 
# obtain the JSON response from the Genius API
# after making a search request to the Genius API.
def genius_search_req(song_name, trie):
    endpoint = 'https://api.genius.com/search'
    headers = get_auth_header(os.getenv(genius_access_token))
    song_title = song_name

    params = {'q': song_title}
    json_song_info = None
    artist_found = False

    # A GET request to the API
    response = requests.get(endpoint, params=params, headers=headers)
    json_resp = response.json()
    
    # Traverse through every song in the ["response"]["hits"] section of the JSON
    for song in json_resp["response"]["hits"]:
        genius_artist_name = ((song["result"]["primary_artist"]["name"]).strip()).upper()
        capture_group = (re.search("^.*?(?=&)", genius_artist_name))
        
        if capture_group: 
            # Case that handles two artists for a song
            artist_found = trie.search(capture_group[0].strip()) 
        else:
            artist_found = trie.search(genius_artist_name.strip())
           
        if artist_found:
             json_song_info = song
             break

    return json_song_info

# Purpose: 
# The purpose of this function is to scrape the lyrics
# from the Genius website. I utilized BeautifulSoup
# to scrape the HTML data from Genius. I sent a 
# GET request to the Genius API to obtain the correct
# path for the desired song. This function returns 
# a list of the lyrics. 
def get_song_lyrics(api_path):
    endpoint = f'https://api.genius.com{api_path}'
    headers = get_auth_header(os.getenv(genius_access_token))
    lyrics = []

    response = requests.get(endpoint, headers=headers)
    json_resp = response.json()
    path = json_resp["response"]["song"]["path"]
    
    # html scraping
    page_url = f'https://genius.com{path}'
    page = requests.get(page_url)
    html = BeautifulSoup(page.text, "html.parser")
   
    # Remove the script tags placed in the lyrics
    [h.extract() for h in html('script')]
    # Div container where the lyrics reside in the HTML page
    lyrics_container = html.find_all("div", class_="Lyrics__Container-sc-1ynbvzw-5 Dzxov")
    
    # Replace all instances of <br> with '\n'
    for container in lyrics_container:
        for br in container.find_all("br"):
            br.replace_with("\n")
            
    for lyric in lyrics_container:
        lyrics.append(lyric.get_text())

    return lyrics

def main():
    while True:
        trie = Trie()
        song_info_list = get_current_song(trie) 
        song_json_obj = song_info_list[2]
        song_status = song_json_obj['currently_playing_type']

       
        if song_status =='track':
            song_info = genius_search_req(song_info_list[0], trie)

            if song_info:
                song_api_path = song_info['result']['api_path']
                lyrics = get_song_lyrics(song_api_path)
                length = song_json_obj['item']['duration_ms']

                progress = song_json_obj['progress_ms']
                time_left = int(((length - progress) / 1000))
                
                for line in lyrics:
                    print(line)
                
                # Pause program until next song
                time.sleep(time_left) 
            else:
                print("ERROR: Song NOT FOUND")
                break
        

if __name__ == "__main__":
    main()