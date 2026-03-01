#!/bin/bash

BT_MAC="XX:XX:XX:XX:XX:XX"
BT_NAME="HK Aura BT"
INTRO_SONG_URL="https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"

echo "[+] Connecting to $BT_NAME"
blueutil --connect "$BT_MAC"
sleep 3

echo "[+] Setting audio output"
SwitchAudioSource -s "$BT_NAME"

echo "[+] Playing intro"
mpv --no-video --quiet --length=2 "$INTRO_SONG_URL"

echo "[✓] Done"
