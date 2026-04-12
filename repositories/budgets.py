from typing import List, Optional

from models.budget import Budget


class BudgetRepository:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def find_all(self) -> List[Budget]:
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                """
                SELECT b.id, b.category_id, b.period_type, b.amount, c.name
                FROM budgets b
                JOIN categories c ON b.category_id = c.id
                ORDER BY c.name, b.period_type
                """
            )
            return [
                Budget(
                    id=row[0],
                    category_id=row[1],
                    period_type=row[2],
                    amount=row[3],
                    category_name=row[4],
                )
                for row in cursor.fetchall()
            ]

    def find(self, budget_id: int) -> Optional[Budget]:
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                """
                SELECT b.id, b.category_id, b.period_type, b.amount, c.name
                FROM budgets b
                JOIN categories c ON b.category_id = c.id
                WHERE b.id = ?
                """,
                (budget_id,),
            )
            row = cursor.fetchone()
            if row:
                return Budget(
                    id=row[0],
                    category_id=row[1],
                    period_type=row[2],
                    amount=row[3],
                    category_name=row[4],
                )
            return None

    def create(self, category_id: int, period_type: str, amount: int) -> Budget:
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO budgets (category_id, period_type, amount) VALUES (?, ?, ?)",
                (category_id, period_type, amount),
            )
            conn.commit()
            budget_id = cursor.lastrowid
        return self.find(budget_id)

    def update_amount(self, budget_id: int, amount: int) -> Optional[Budget]:
        with self.db_manager.connect() as conn:
            cursor = conn.execute(
                "UPDATE budgets SET amount = ? WHERE id = ?",
                (amount, budget_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        return self.find(budget_id)

    def delete(self, budget_id: int) -> bool:
        with self.db_manager.connect() as conn:
            cursor = conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
            conn.commit()
            return cursor.rowcount > 0
