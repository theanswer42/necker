from dataclasses import dataclass, field


@dataclass
class Budget:
    id: int
    category_id: int
    period_type: str  # 'monthly' or 'yearly'
    amount: int = field(metadata={"cli_format": "cents_to_dollars"})  # cents
    category_name: str | None = None  # populated by repository joins
