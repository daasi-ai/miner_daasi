from enum import Enum
from typing import AsyncIterator, Dict, List, Literal, Optional

import bittensor as bt
import pydantic


    
class GetNodeDetail( bt.Synapse ):
    response: Optional[list] = pydantic.Field(
        None,
        title="response",
        description="Response received from miner"
    )
    

class SendMinerScore( bt.Synapse ):
    # miner_score: str = pydantic.Field(
    #     "",
    #     title="Miner Score",
    #     description="Send node score to miner"
    # )
    details: Optional[dict] = pydantic.Field(
        None,
        title="Node Details ",
        description="Node Details provided from validator"
    )