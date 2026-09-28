"""Boundary probe only: reject an OHLC-invalid observation before any engine call."""
from dataclasses import replace
from decimal import Decimal
from common import obs
from apex.data_catalog.contracts import validate_market_observation,ValidationError
valid=obs(4)
invalid=replace(valid,high=Decimal('1'))
try:
    validate_market_observation(invalid,prev_sequence=4)
except ValidationError as e:
    print('engine_called=False; invalid_observation_rejected_by_repository_validator=',str(e))
else:
    raise AssertionError('contract validator unexpectedly accepted invalid OHLC')
