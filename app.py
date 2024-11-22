from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import httpx
from datetime import datetime, timezone
from transaction_details import get_transaction_details, get_latest_transactions, get_transaction_state_changes
from ethereum_client import EthereumClient
from database_connection import Neo4jConnection
from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME, ETHERSCAN_API_KEY, ETHERSCAN_API_URL
from typing import Optional
import asyncio
app = FastAPI()

# CORS middleware for allowing frontend to access the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Update with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Instantiate EthereumClient once for reuse
eth_client = EthereumClient()

# Decode method from input data
def decode_method(input_data):
    if input_data == '0x':
        return 'Transfer'
    else:
        method_id = input_data[:10]
        method_map = {
            '0xa9059cbb': 'Transfer',
            '0x095ea7b3': 'Approve',
            '0x23b872dd': 'TransferFrom',
            '0x2e1a7d4d': 'Burn',
            '0x40c10f19': 'Mint',
            '0xf305d719': 'Withdraw',
            '0x9ebea88c': 'Propose Block',
            '0xd0e30db0': 'Deposit ETH',
        }
        return method_map.get(method_id, 'Unknown Method')


# Fetch transactions for an address from Etherscan
async def get_transactions(address, api_key):
    url = f'https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=asc&apikey={api_key}'
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        
    if response.status_code == 200:
        data = response.json()
        if data['status'] == '1':
            return data['result']
        else:
            return []
    else:
        return []

# Create transaction data from raw transactions
def create_transaction_data(transactions):
    tx_data = []
    
    for tx in transactions:
        txn_fee = int(tx['gasUsed']) * int(tx['gasPrice']) / 10**18
        
        current_time = datetime.now(timezone.utc)
        txn_age = current_time - datetime.fromtimestamp(int(tx['timeStamp']), timezone.utc)
        
        tx_data.append({
            'hash': tx['hash'],
            'method': decode_method(tx['input']),
            'block': tx['blockNumber'],
            'age': str(txn_age).split('.')[0] + " ago",
            'from': tx['from'],
            'to': tx['to'],
            'amount': f"{int(tx['value']) / 10**18:.8f} ETH",
            'fee': f"{txn_fee:.8f}"
        })

    return sorted(tx_data, key=lambda x: x['method'])



@app.get("/api/address/{address}")
async def get_address_info(addressToFetch: str):
    """
    Get information about an Ethereum address.
    This endpoint matches the exact path your frontend is trying to access.
    """
    try:
        logger.info(f"Fetching address info for: {addressToFetch}")
        
        # Get address overview from Ethereum client
        address_info = await eth_client.get_address_overview(addressToFetch)
        
        if not address_info:
            logger.warning(f"No data found for address: {addressToFetch}")
            raise HTTPException(status_code=404, detail="Address not found")
        
        # Fetch current gas price
        try:
            gas_price = await eth_client.get_gas_price()
            gas_price_gwei = f"{gas_price:.2f}"  # Format to 2 decimal places
        except Exception as e:
            logger.error(f"Error fetching gas price: {str(e)}")
            gas_price_gwei = "N/A"
        
        # Format the response to match your frontend's expected structure
        response_data = {
            "success": True,
            "data": {
                "address": addressToFetch,
                "balance": address_info.get("balance", "0"),
                "totalSent": address_info.get("totalSent", "0"),
                "totalReceived": address_info.get("totalReceived", "0"),
                "value": address_info.get("balanceUSD", "0"),
                "tokenHoldings": address_info.get("tokenHoldings", []),
                "gas": gas_price_gwei,  # Dynamically fetched gas price
                "privateNameTag": address_info.get("privateNameTag"),
                "firstSeen": address_info.get("firstSeen"),
                "lastSeen": address_info.get("lastSeen"),
                "fundedBy": address_info.get("fundedBy"),
                "multichainInfo": address_info.get("multichainInfo")
            }
        }
        
        logger.info(f"Successfully fetched data for address: {addressToFetch}")
        return response_data

    except Exception as e:
        logger.error(f"Error processing request for address {addressToFetch}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Fetch data from Etherscan
async def get_etherscan_data(address, api_key):
    transactions = await get_transactions(address, api_key)
    if transactions:
        return create_transaction_data(transactions)
    return []

async def get_transaction_details_with_retry(tx_hash, max_retries=3):
    for attempt in range(max_retries):
        try:
            details = await get_transaction_details(tx_hash)
            if details:
                return details
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logging.error(f"All attempts failed for transaction {tx_hash}")
                return None
        await asyncio.sleep(1)  # Wait for 1 second before retrying


@app.get("/api/transaction/{tx_hash}")
async def transaction(tx_hash: str):
    if not is_valid_tx_hash(tx_hash):
        logging.error(f"Invalid transaction hash format: {tx_hash}")
        raise HTTPException(status_code=400, detail="Invalid transaction hash format")
    
    logging.info(f"Fetching details for transaction hash: {tx_hash}")
    details = await get_transaction_details_with_retry(tx_hash)
    
    if details:
        logging.info(f"Redirecting to transaction details for hash: {tx_hash}")
        # Redirecting to the transaction detail endpoint
        return RedirectResponse(url=f"/api/transaction_detail/{tx_hash}")
    else:
        logging.error(f"Transaction with hash {tx_hash} not found")
        raise HTTPException(status_code=404, detail=f"Transaction with hash {tx_hash} not found")

def is_valid_tx_hash(tx_hash: str) -> bool:
    # Replace with actual validation logic
    return len(tx_hash) == 66 and tx_hash.startswith("0x")


@app.get("/api/transaction_detail/{tx_hash}")
async def transaction_detail(tx_hash: str):
    try:
        logging.info(f"Fetching detailed transaction info for hash: {tx_hash}")
        details = await get_transaction_details_with_retry(tx_hash)
        if details:
            gas_risk_score = await calculate_gas_risk_score(details)
            details["gas_risk_score"] = gas_risk_score
            return JSONResponse(content=details)
        else:
            logging.error(f"Transaction not found or failed to fetch for hash: {tx_hash}")
            raise HTTPException(status_code=404, detail="Failed to fetch transaction details. Please try again later.")
    except Exception as e:
        logging.error(f"Error fetching transaction details for {tx_hash}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch transaction details. Please try again later.")

@app.get("/api/transaction/{tx_hash}/state")
async def transaction_state(tx_hash: str):
    if not is_valid_tx_hash(tx_hash):
        raise HTTPException(status_code=400, detail="Invalid transaction hash format")
    
    try:
        logging.info(f"Fetching state changes for transaction hash: {tx_hash}")
        # Use the implementation from transaction_details.py
        state_changes = await get_transaction_state_changes(tx_hash)
        
        if state_changes is None or len(state_changes) == 0:
            return JSONResponse(content=[])
        
        return JSONResponse(content=state_changes)
        
    except Exception as e:
        logging.error(f"Error fetching state changes for transaction {tx_hash}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch state changes. Please try again later."
        )
    
async def get_transaction_state_changes(tx_hash):
    try:
        # Assuming you are using Etherscan's API to fetch transaction state changes
        url = f'https://api.etherscan.io/api?module=transaction&action=getstatus&txhash={tx_hash}&apikey={os.getenv("ETHERSCAN_API_KEY")}'
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        
        if response.status_code != 200:
            logging.error(f"API request failed with status {response.status_code}: {response.text}")
            return None
        
        data = response.json()
        
        if data.get('status') != '1':
            logging.error(f"API response status not OK: {data}")
            return None
        
        # Process and return state change data if valid
        return data.get('result')
    
    except Exception as e:
        logging.error(f"Unexpected error in get_transaction_state_changes: {e}")
        return None

async def get_transaction_logs(tx_hash):
    try:
        # Etherscan API request to fetch logs for the given transaction hash
        url = f'https://api.etherscan.io/api?module=logs&action=getLogs&txhash={tx_hash}&apikey={os.getenv("ETHERSCAN_API_KEY")}'
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        
        if response.status_code != 200:
            logging.error(f"API request failed with status {response.status_code}: {response.text}")
            return None
        
        data = response.json()
        if data.get('status') != '1':
            logging.error(f"API response status not OK: {data}")
            return None
        
        return data.get('result')  # Return the logs, which may indicate state changes
    
    except Exception as e:
        logging.error(f"Unexpected error in get_transaction_logs: {e}")
        return None


@app.get("/api/latest_transactions")
async def latest_transactions():
    transactions = await get_latest_transactions()
    if transactions:
        return JSONResponse(content=transactions)
    else:
        raise HTTPException(status_code=404, detail="No transactions found")

@app.get("/api/ethereum_data")
async def ethereum_data():
    try:
        latest_block_number = await eth_client.get_latest_block_number()
        gas_price = await eth_client.get_gas_price()
        jco_price = await eth_client.get_jco_price()
        jco_change = await eth_client.get_jco_price_change()
        
        address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"  # Example address
        balance_latest = await eth_client.get_balance(address)
        
        historical_block_number = latest_block_number - 100 if latest_block_number else None
        balance_historical = None
        if historical_block_number:
            balance_historical = await eth_client.get_balance(address, block=historical_block_number)

        return JSONResponse(content={
            "latestBlockNumber": latest_block_number,
            "gasPrice": gas_price,
            "jcoPrice": jco_price,
            "jcoChange": jco_change,
            "currentBalance": f"{balance_latest:.6f} ETH" if balance_latest is not None else "N/A",
            "historicalBalance": f"{balance_historical:.6f} ETH" if balance_historical is not None else "N/A",
            "historicalBlockNumber": historical_block_number
        })
    except Exception as e:
        logging.error(f"Error fetching Ethereum data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch Ethereum data. Please try again later.")

@app.get("/api/transaction/{tx_hash}/state")
async def transaction_state(tx_hash: str):
    if not is_valid_tx_hash(tx_hash):
        raise HTTPException(status_code=400, detail="Invalid transaction hash format")
        
    try:
        logging.info(f"Fetching state changes for transaction hash: {tx_hash}")
        state_changes = await get_transaction_state_changes(tx_hash)
        
        if state_changes is None:
            raise HTTPException(status_code=404, detail="Transaction not found")
            
        return JSONResponse(content=state_changes)
        
    except Exception as e:
        logging.error(f"Error fetching state changes: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch state changes. Please try again later."
        )
    
@app.get("/api/address/{address}/transactions")
async def get_address_transactions(address: str):
    api_key = os.getenv('ETHERSCAN_API_KEY')  # Load API key from env variables
    if not api_key:
        logging.error("ETHERSCAN_API_KEY not found in environment variables")
        raise HTTPException(status_code=500, detail="Server configuration error")
    
    try:
        transactions = await get_etherscan_data(address, api_key)
        if transactions:
            return JSONResponse(content=transactions)
        else:
            logging.error(f"No transactions found for address {address}")
            raise HTTPException(status_code=404, detail="No transactions found for this address")
    except Exception as e:
        logging.error(f"Error fetching transactions for address {address}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching transactions")

@app.get("/api/transaction/{tx_hash}/state")
async def transaction_state(tx_hash: str):
    if not is_valid_tx_hash(tx_hash):
        raise HTTPException(status_code=400, detail="Invalid transaction hash format")
        
    try:
        logging.info(f"Fetching state changes for transaction hash: {tx_hash}")
        state_changes = await get_transaction_state_changes(tx_hash)
        
        if state_changes is None:
            raise HTTPException(status_code=404, detail="Transaction not found")
            
        return JSONResponse(content=state_changes)
        
    except Exception as e:
        logging.error(f"Error fetching state changes: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch state changes. Please try again later."
        )
    
# Calculate gas risk score
async def calculate_gas_risk_score(transaction_details):
    try:
        gas_price = float(transaction_details.get("Gas Price", "0").split()[0])  # Extract numeric value
        gas_used = float(transaction_details.get("Gas Used", "0"))
        
        # Get current network gas price asynchronously
        current_gas_price = await eth_client.get_gas_price()

        # Calculate risk factors
        price_factor = gas_price / current_gas_price if current_gas_price > 0 else 1
        usage_factor = gas_used / 21000  # Assuming 21000 is the standard gas limit

        # Combine factors (you can adjust weights as needed)
        risk_score = (price_factor * 0.7 + usage_factor * 0.3) * 100

        return min(risk_score, 100)  # Cap the score at 100
    except Exception as e:
        logging.error(f"Error calculating gas risk score: {e}")
        return 0  # Return 0 if there's an error in calculation

# If running directly, start the server
if __name__ == '__main__':
    import uvicorn
    logging.info("Server is starting on http://0.0.0.0:8000")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(app, host="0.0.0.0", port=8000)
