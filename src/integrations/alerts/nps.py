"""
NPS alert provider implementation.
"""

from typing import List
from ...models import Alert
from ...config import NPS_API_KEY
from ...nps_client import get_alerts_for_park
from . import AlertProvider


class NPSAlertProvider(AlertProvider):
    """Wrapper around existing NPS alerts client."""
    
    def get_alerts(self, location_id: str) -> List[Alert]:
        """
        Fetch alerts from NPS for a park code.
        
        Args:
            location_id: NPS park code (e.g., "yose")
        
        Returns:
            List of Alert objects
        """
        if not NPS_API_KEY:
            return []
        
        return get_alerts_for_park(location_id)
