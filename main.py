import discord
from discord.ext import commands
from discord import ui
import asyncio
import json
import os
import html
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from threading import Thread


# =========================================================
# KONFIGURACJA
# =========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("Brak DISCORD_TOKEN w pliku .env")

# Kanał głównego panelu ticketów
TICKET_PANEL_CHANNEL_ID = 1563911023755264133

# Kategoria ticketów
TICKET_CATEGORY_ID = 1563911023495352410

# Kanał transcriptów
TRANSCRIPT_CHANNEL_ID = 1563911023495352412

# Kanał powitań
WELCOME_CHANNEL_ID = 1563911023495352416


# =========================================================
# ROLE
# =========================================================

# Rekrutacja
RECRUITMENT_ROLE_ID = 1563911021863641237

# Klatki + Inne
GENERAL_SUPPORT_ROLE_ID = 1563911022270619701

# Support do wszystkiego
UNIVERSAL_SUPPORT_ROLE_ID = 1563911022270619701


# =========================================================
# OBRAZKI
# =========================================================

# Panel ticketów
PANEL_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/1508833559551410198/"
    "1548676447579676672/"
    "Gemini_Generated_Image_8lu4pd8lu4pd8lu4.jpg"
    "?ex=6aa7ecd6&is=6aa69b56"
    "&hm=76ee4baf615ec0737403f12741f42168b7d6e3db24486e9460eced6071f95bb5"
)

# Ticket
TICKET_IMAGE_URL = PANEL_IMAGE_URL

# Powitanie
WELCOME_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/1508833559551410198/"
    "1548676441854705775/"
    "Gemini_Generated_Image_o4qcdio4qcdio4qc.jpg"
    "?ex=6aa7ecd4&is=6aa69b54"
    "&hm=562654d9233117f320f4f8bc738d14da08e8e8bffdc4d6252b63c16c077a0c&"
)

# Loader transcriptu
TRANSCRIPT_LOADING_IMAGE = (
    "https://cdn.discordapp.com/attachments/1508833559551410198/"
    "1548680146813325363/"
    "obraz_2026-09-13_143612130-removebg-preview.png"
    "?ex=6aa7f048&is=6aa69ec8"
    "&hm=bb0cce064bcc6c62ff5e903adfa486cfccfe13e4e051cde1f94596d1a341b760"
)


# =========================================================
# EMOJI
# =========================================================

ARROW = "<a:strzal:1568726971943354459>"
PONNY = "<:ponny:1568727308137922621>"


# =========================================================
# DANE
