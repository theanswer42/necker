from dataclasses import dataclass


@dataclass
class Account:
    id: int
    name: str  # [a-z_] format, e.g., "bofa_checking"
    type: str  # ingestion module name, e.g., "bofa"
    description: str  # human readable, e.g., "Bank of America Checking Account"

    def to_dict(self) -> dict:
        """Convert account to dictionary for database storage."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
        }
