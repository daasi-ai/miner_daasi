# import base  # noqa
# == Import Packages == 
import bittensor as bt
import argparse
import asyncio
import copy
import threading
from template.utils.read_file import read_json_file
import time
import traceback
import logging
from colorama import Fore, Style, init


from abc import ABC, abstractmethod
from typing import Tuple
from config import check_config, get_config
from template.protocol import *
# from template.utils import *
# import template
import sys
import os


valid_hotkeys = []

class ColorFormatter(logging.Formatter):
    FORMAT = "%(asctime)s |     %(levelname)s     | %(message)s"
    FORMATS = {
        logging.DEBUG: Fore.BLUE + FORMAT + Style.RESET_ALL,
        logging.INFO: Fore.GREEN + FORMAT + Style.RESET_ALL,
        logging.WARNING: Fore.YELLOW + FORMAT + Style.RESET_ALL,
        logging.ERROR: Fore.RED + FORMAT + Style.RESET_ALL,
        logging.CRITICAL: Fore.RED + Style.BRIGHT + FORMAT + Style.RESET_ALL
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.FORMAT)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Create a logger
logger = logging.getLogger('colorful_logger')
logger.setLevel(logging.DEBUG)

# Create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Add the custom formatter to the console handler
ch.setFormatter(ColorFormatter())

# Add the console handler to the logger
logger.addHandler(ch)

class StreamMiner(ABC):
    def __init__(self, config=None, axon=None, wallet=None, subtensor=None):
        bt.logging.info("starting stream miner")
        base_config = copy.deepcopy(config or get_config())
        self.config = self.config()
        self.config.merge(base_config)
        check_config(StreamMiner, self.config)
        bt.logging.info(self.config)  # TODO: duplicate print?
        self.prompt_cache: dict[str, Tuple[str, int]] = {}
        self.request_timestamps = {}

        # Activating Bittensor's logging with the set configurations.
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.info("Setting up bittensor objects.")

        # Wallet holds cryptographic information, ensuring secure transactions and communication.
        self.wallet = wallet or bt.wallet(config=self.config)
        bt.logging.info(f"Wallet {self.wallet}")

        # subtensor manages the blockchain connection, facilitating interaction with the Bittensor blockchain.
        self.subtensor = subtensor or bt.subtensor(config=self.config)
        bt.logging.info(f"Subtensor: {self.subtensor}")
        bt.logging.info(
            f"Running miner for subnet: {self.config.netuid} "
            f"on network: {self.subtensor.chain_endpoint} with config:"
        )

        # metagraph provides the network's current state, holding state about other participants in a subnet.
        self.metagraph = self.subtensor.metagraph(self.config.netuid)
        bt.logging.info(f"Metagraph: {self.metagraph}")

        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            bt.logging.error(
                f"\nYour validator: {self.wallet} if not registered to chain connection: {self.subtensor} "
                f"\nRun btcli register and try again. "
            )
            sys.exit()
        else:
            # Each miner gets a unique identity (UID) in the network for differentiation.
            self.my_subnet_uid = self.metagraph.hotkeys.index(
                self.wallet.hotkey.ss58_address
            )
            bt.logging.info(f"Running miner on uid: {self.my_subnet_uid}")

        # The axon handles request processing, allowing validators to send this process requests.
        self.axon = axon or bt.axon(wallet=self.wallet, port=self.config.axon.port)
        # Attach determiners which functions are called when servicing a request.
        bt.logging.info("Attaching forward function to axon.")
        # print(f"Attaching forward function to axon. {self._prompt}")
        self.axon.attach(
            forward_fn=self._share_node_detail
        ).attach(
            forward_fn=self._receive_node_score
        )

        bt.logging.info(f"Axon created: {self.axon}")

        # Instantiate runners
        self.should_exit: bool = False
        self.is_running: bool = False
        self.thread: threading.Thread = None
        self.lock = asyncio.Lock()
        self.request_timestamps: dict = {}
        # thread = threading.Thread(target=get_valid_hotkeys, args=(self.config,))
        # thread.start()

    @abstractmethod
    def config(self) -> bt.config:
        ...
    
    def _share_node_detail(self, synapse:GetNodeDetail) -> GetNodeDetail:
        return self.share_node_detail(synapse)
    
    def _receive_node_score(self, synapse:SendMinerScore) -> SendMinerScore:
        return self.receive_node_score(synapse)

    @classmethod
    @abstractmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        ...

    def _share_node_detail(self, synapse:GetNodeDetail) -> GetNodeDetail:
        return self.share_node_detail(synapse)

    def _receive_node_score(self, synapse:SendMinerScore) -> SendMinerScore:
        return self.receive_node_score(synapse)
    

    @abstractmethod
    def share_node_detail(self, synapse:GetNodeDetail) -> GetNodeDetail:
        ...
    
    @abstractmethod
    def receive_node_score(self, synapse:SendMinerScore) -> SendMinerScore:
        ...

    def run(self):
        if not self.subtensor.is_hotkey_registered(
            netuid=self.config.netuid,
            hotkey_ss58=self.wallet.hotkey.ss58_address,
        ):
            bt.logging.error(
                f"Wallet: {self.wallet} is not registered on netuid {self.config.netuid}"
                f"Please register the hotkey using `btcli s register --netuid 77` before trying again"
            )
            sys.exit()
        bt.logging.info(
            # f"Serving axon {StreamPrompting} "
            f"on network: {self.config.subtensor.chain_endpoint} "
            f"with netuid: {self.config.netuid}"
        )
        self.axon.serve(netuid=self.config.netuid, subtensor=self.subtensor)
        bt.logging.info(f"Starting axon server on port: {self.config.axon.port}")
        self.axon.start()
        self.last_epoch_block = self.subtensor.get_current_block()
        bt.logging.info(f"Miner starting at block: {self.last_epoch_block}")
        bt.logging.info("Starting main loop")
        step = 0
        try:
            while not self.should_exit:
                _start_epoch = time.time()

                # --- Wait until next epoch.
                current_block = self.subtensor.get_current_block()
                while (
                    current_block - self.last_epoch_block
                    < self.config.miner.blocks_per_epoch
                ):
                    # --- Wait for next bloc.
                    time.sleep(1)
                    current_block = self.subtensor.get_current_block()
                    # --- Check if we should exit.
                    if self.should_exit:
                        break

                # --- Update the metagraph with the latest network state.
                self.last_epoch_block = self.subtensor.get_current_block()

                metagraph = self.subtensor.metagraph(
                    netuid=self.config.netuid,
                    lite=True,
                    block=self.last_epoch_block,
                )
                log = (
                    f"Step:{step} | "
                    f"Block:{metagraph.block.item()} | "
                    f"Stake:{metagraph.S[self.my_subnet_uid]} | "
                    f"Rank:{metagraph.R[self.my_subnet_uid]} | "
                    f"Trust:{metagraph.T[self.my_subnet_uid]} | "
                    f"Consensus:{metagraph.C[self.my_subnet_uid] } | "
                    f"Incentive:{metagraph.I[self.my_subnet_uid]} | "
                    f"Emission:{metagraph.E[self.my_subnet_uid]}"
                )
                bt.logging.info(log)

                # --- Set weights.
                if not self.config.miner.no_set_weights:
                    pass
                step += 1

        except KeyboardInterrupt:
            self.axon.stop()
            bt.logging.success("Miner killed by keyboard interrupt.")
            sys.exit()

        except Exception:
            bt.logging.error(traceback.format_exc())

    def run_in_background_thread(self) -> None:
        if not self.is_running:
            bt.logging.debug("Starting miner in background thread.")
            self.should_exit = False
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            self.is_running = True
            bt.logging.debug("Started")

    def stop_run_thread(self) -> None:
        if self.is_running:
            bt.logging.debug("Stopping miner in background thread.")
            self.should_exit = True
            self.thread.join(5)
            self.is_running = False
            bt.logging.debug("Stopped")

    def __enter__(self):
        self.run_in_background_thread()

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop_run_thread()

    

class StreamingTemplateMiner(StreamMiner):
    print("Miner is started...")
    def config(self) -> bt.config:
        parser = argparse.ArgumentParser(description="Streaming Miner Configs")
        self.add_args(parser)
        return bt.config(parser)

    def add_args(cls, parser: argparse.ArgumentParser):
        pass

    """
        * This method shares the details of all the nodes with the validator.
        * The details it shares are the IP and status of the node
    """

    def share_node_detail(self, synapse:GetNodeDetail) -> GetNodeDetail:
        try:
            print("Get Node Details...")
            file_path = 'node_config.json'
            node_detail = read_json_file(file_path)    
            synapse.response = node_detail
            return synapse
        except Exception as e:
            print(f"Error in share_node_detail", e)
            return False
     
    def receive_node_score(self, synapse:SendMinerScore):
        try:
            print("Get Validator Score...")
            if 'Validator_name' in synapse.details:
                logger.info("HOTKEY: %s", synapse.details['Validator_name'])

            if 'score' in synapse.details:
                logger.info("TOTAL SCORE: %s", synapse.details['score'])

            if 'rank' in synapse.details:
                logger.info("RANK: %s", synapse.details['rank'])
            
            if 'message' in synapse.details:
                logger.info("MESSAGE: %s", synapse.details['message'])

            logger.info("====== Next Node Detail =======")
            
            
            return synapse
        except Exception as e:
            print(f"Error in share_node_detail", e)
            return False

if __name__ == "__main__":
    with StreamingTemplateMiner():
        while True:
            time.sleep(1.0)
    

