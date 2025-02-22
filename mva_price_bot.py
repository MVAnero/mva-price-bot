import discord
from discord.ext import tasks
import requests
import asyncio
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# Get secrets from environment variables (set in Replit Secrets)
TOKEN = os.getenv("TOKEN")
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID"))
VCS_API_KEY = os.getenv("VCS_API_KEY")

# MVA token symbol
MVA_TOKEN_SYMBOL = "MVA"

# VeChainStats API endpoint
VECHAIN_API = "https://api.vechainstats.com/v2/token/price"

# Discord client setup
intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

# Keep-alive HTTP server
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def start_server():
    server = HTTPServer(('0.0.0.0', 8080), KeepAliveHandler)
    server.serve_forever()

# Function to fetch MVA price from VeChainStats
def get_mva_price():
    try:
        headers = {
            "Authorization": f"Bearer {VCS_API_KEY}",
            "Content-Type": "application/json"
        }
        params = {
            "token": MVA_TOKEN_SYMBOL,
            "expanded": "true",
            "VCS_API_KEY": VCS_API_KEY
        }
        logger.info(f"Requesting: {VECHAIN_API} with params {params}")
        response = requests.get(VECHAIN_API, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if not data.get("status", {}).get("success", False):
            logger.warning(f"API request failed: {data}")
            return None

        price_usd = data.get("data", {}).get("price_usd")
        if price_usd is None:
            logger.warning(f"Price data not found in response: {data}")
            return None

        price = float(price_usd)
        logger.info(f"MVA/USD price fetched from VeChainStats: ${price}")
        return price
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error fetching MVA price: {e}")
        logger.error(f"Response content: {e.response.text if e.response else 'No content'}")
        return None
    except Exception as e:
        logger.error(f"General Error fetching MVA price: {e}")
        return None

# Function to truncate a float to 4 decimals without rounding
def truncate_to_4_decimals(price):
    price_str = str(price)
    integer_part, decimal_part = price_str.split(".") if "." in price_str else (price_str, "0")
    decimal_part = (decimal_part + "0000")[:4]
    return float(f"{integer_part}.{decimal_part}")

# Task to update voice channel name
@tasks.loop(minutes=15)
async def update_voice_channel():
    channel = client.get_channel(VOICE_CHANNEL_ID)
    if channel is None:
        logger.error(f"Voice channel with ID {VOICE_CHANNEL_ID} not found.")
        return

    price = get_mva_price()
    if price:
        truncated_price = truncate_to_4_decimals(price)
        new_name = f"MVA: ${truncated_price}"
    else:
        new_name = "MVA: N/A"
    
    if len(new_name) > 100:
        new_name = new_name[:100]
    
    try:
        await channel.edit(name=new_name)
        logger.info(f"Updated voice channel name to: {new_name}")
    except discord.errors.HTTPException as e:
        logger.warning(f"Failed to update voice channel: {e}")
    except Exception as e:
        logger.error(f"Error updating voice channel: {e}")

# Bot event: When ready
@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    if not update_voice_channel.is_running():
        await asyncio.sleep(60)
        update_voice_channel.start()

# Start keep-alive server in a separate thread
threading.Thread(target=start_server, daemon=True).start()

# Run the bot
client.run(TOKEN)