from dataclasses import dataclass
from typing import Optional


@dataclass
class Budget:
    id: int
    category_id: int
    period_type: str  # 'monthly' or 'yearly'
    amount: int  # cents
    category_name: Optional[str] = None  # populated by repository joins
