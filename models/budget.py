from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Budget:
    id: int
    category_id: int
    period_type: str  # 'monthly' or 'yearly'
    amount: int = field(metadata={"cli_format": "cents_to_dollars"})  # cents
    category_name: Optional[str] = None  # populated by repository joins
