import os
import json
import time
import requests
from dotenv import load_dotenv
from solders.keypair import Keypair
from solders.message import Message
from solders.signature import Signature
from solders.hash import Hash
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
import base58

# # Load private key from environment variable
# load_dotenv()
# PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")
# if not PRIVATE_KEY:
#   raise ValueError("Please set the SOLANA_PRIVATE_KEY environment variable.")

PRIVATE_KEY_JSON = [217,80,175,155,90,193,90,100,8,86,124,24,55,235,241,97,241,198,3,29,41,149,38,238,218,142,180,29,172,9,9,193,81,28,116,57,112,108,76,110,123,5,54,184,194,224,218,76,172,182,91,163,53,130,91,167,248,22,208,37,109,137,159,198]
PRIVATE_KEY="5oyP6rBbSKMoM5oQSKAW7ZeZMoqGvQ1EQSqpoVZ9GUCRbstopcd7u62pzySg3d51wNwx8DHpVAyxSA9mjYGYqUde"

# Parse the JSON array string → list of ints → bytes
try:
    secret_key_bytes = bytes(PRIVATE_KEY_JSON)
except Exception as e:
    raise ValueError("SOLANA_PRIVATE_KEY must be a valid JSON array of numbers") from e

# Create wallet (Keypair) from raw secret key bytes
wallet: Keypair = Keypair.from_bytes(secret_key_bytes)

wallet: Keypair = Keypair.from_base58_string(PRIVATE_KEY)

def sign_message(wallet: Keypair, message: str) -> dict:
  # Create a message object (not required for simple signing, but included for completeness)
  message_bytes = message.encode("utf-8")
  # Sign the message using the wallet's private key
  signature = wallet.sign_message(message_bytes)
  # Convert the signature to a base58 string
  signature_base58 = str(signature)
  # Decode base58 to bytes, then convert bytes to a list of integers
  signature_data = list(base58.b58decode(signature_base58))
  return {
    "data": signature_data,  # List of integers representing the signature
    "type": "ed25519",  # Signature type
  }


def login_to_rugcheck(wallet: Keypair):
  # Prepare the message to be signed
  message_data = {
    "message": "Sign-in to Rugcheck.xyz",
    "timestamp": int(time.time() * 1000),  # Current time in milliseconds
    "publicKey": str(wallet.pubkey()),  # Wallet's public key
  }
  message_json = json.dumps(message_data, separators=(',', ':'))

  # Sign the message
  signature = sign_message(wallet, message_json)

  # Prepare the request payload
  payload = {
    "signature": signature,  # Pass the signature as a JSON object
    "wallet": str(wallet.pubkey()),
    "message": message_data,  # Convert the message to hex
  }

  # Make the POST request
  try:
    response = requests.post(
      "https://api.rugcheck.xyz/auth/login/solana",
      headers={"Content-Type": "application/json"},
      data=json.dumps(payload),
    )
    if response.status_code == 200:
      response_data = response.json()
      print("Login successful:", response_data)
    else:
      print("Failed to login:", response.status_code, response.text)
  except Exception as e:
    print("Failed to login", e)


# Run the login process
login_to_rugcheck(wallet)