import os
import time
import json
import smtplib
import requests
import datetime as dt
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from langchain_groq import ChatGroq
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.prebuilt import create_react_agent

load_dotenv()

MONTHS = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}
my_email = "wong.weijun923@gmail.com"
BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "bday.json"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

dDate = dt.date.today()
tDay = str(dDate.day).zfill(2)
tMonth = MONTHS[dDate.month]

people_today = data.get(tMonth, {}).get(tDay, [])

class ChristmasWish(BaseModel):
    message: str
    blessing: str

llm = ChatGroq(model="llama-3.3-70b-versatile")
parser = PydanticOutputParser(pydantic_object=ChristmasWish)
system_prompt = f"Friendly assistant. Sarcastic bday wishes. {parser.get_format_instructions()}"
agent = create_react_agent(model=llm, tools=[], prompt=system_prompt)

def send_bday_email(name, link, structured_msg):
    message_body = f"Dear {name}, {structured_msg.message} ⭐ {structured_msg.blessing}.\n\nSongs from your birth day: {link}"
    email_msg = f"Subject: Happy Birthday {name}!\n\n{message_body}"
    
    try:
        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
            connection.starttls()
            connection.login(user=my_email, password=os.getenv("EMAIL_PASSWORD"))
            connection.sendmail(from_addr=my_email, to_addrs=my_email, msg=email_msg.encode('utf-8'))
            print(f"📧 Email sent!")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def process_birthday(person):
    name = person["Name"]
    year = person["Year"]

    birth_date = f"{year}-{str(dDate.month).zfill(2)}-{tDay}"
    
    print(f"🎂 Processing {name}'s birthday (Born: {birth_date})...")


    header = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.billboard.com/charts/hot-100/{birth_date}"
    response = requests.get(url, headers=header)
    soup = BeautifulSoup(response.text, 'html.parser')
    song_names = [song.getText().strip() for song in soup.select("li ul li h3")][:20] # Limit to 20 for speed
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        scope="playlist-modify-private",
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI")
    ))
    
    user_id = sp.current_user()["id"]
    song_uris = []
    for song in song_names:
        result = sp.search(q=f"track:{song}", type="track", limit=1)
        if result["tracks"]["items"]:
            song_uris.append(result["tracks"]["items"][0]["uri"])

    if not song_uris:
        print(f"No songs found for {birth_date}")
        return

    playlist = sp.user_playlist_create(user=user_id, public=False, name=f"Top Hits from {birth_date} for {name}")
    sp.playlist_add_items(playlist["id"], song_uris)
    playlist_url = playlist["external_urls"]["spotify"]


    result = agent.invoke({"messages": [("human", "Generate a sarcastic bday wish")]})
    try:
        structured = parser.parse(result["messages"][-1].content)
        print(f"🎉 Playlist: {playlist_url}")
        send_bday_email(name, playlist_url, structured)
    except:
        print("AI wish failed to parse.")

if __name__ == "__main__":
    if people_today:
        for person in people_today:
            process_birthday(person)
    else:
        print("No birthdays today!")
