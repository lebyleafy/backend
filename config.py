import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

NEXT_PUBLIC_API_URL = os.getenv('NEXT_PUBLIC_API_URL')
NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USERNAME = os.getenv('NEO4J_USERNAME')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
ETHERSCAN_API_URL = os.getenv('ETHERSCAN_API_URL')

if not all([NEXT_PUBLIC_API_URL, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, ETHERSCAN_API_KEY, ETHERSCAN_API_URL]):
    raise ValueError("Please check your .env file. Some required environment variables are missing.")
