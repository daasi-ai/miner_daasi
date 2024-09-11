# DAASI Miner Setup

Run the following script to set up the environment and install dependencies:

```bash
#!/bin/bash

# Update and install dependencies
sudo apt update
sudo apt install python3-pip python3-venv nodejs npm -y

# Create and activate virtual environment
python3 -m venv bit
source bit/bin/activate

# Install PM2
sudo npm i -g pm2

# Clone repository (replace with your actual repo URL)
git clone https://github.com/daasi-ai/miner_daasi
cd miner_daasi

# Install Python requirements
pip install -e .
```

## Running the Miner

- Make sure you have the node_config.json file with the correct node details from your enclave
- Add it running then add "running" if not add as "standby" 
- DO NOT CHANGE THE PORT OR USAGE_PORT VALUES IN THE JSON FILE

After installation, run the miner with your hotkey and coldkey:

```bash
# Run validator (replace 'your_hotkey' and 'your_coldkey' with your actual keys)
pm2 start miner/miner.py  --interpreter python3 -- --netuid 36 --subtensor.network test --wallet.name your_coldkey --wallet.hotkey your_hotkey --logging.debug
```