from sqlalchemy.orm import Session
from database.repositories.customer_repository import CustomerRepository
from database.models import Customer
from typing import List, Optional

class CustomerService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = CustomerRepository(session)

    def create_customer(self, customer_data: dict) -> Customer:
        return self.repo.create(customer_data)

    def get_customer(self, customer_id: int) -> Optional[Customer]:
        return self.repo.get_by_id(customer_id)

    def list_customers(self, skip: int = 0, limit: int = 100) -> List[Customer]:
        return self.repo.list_all(skip, limit)

    def update_customer(self, customer_id: int, update_data: dict) -> Optional[Customer]:
        customer = self.get_customer(customer_id)
        if customer:
            return self.repo.update(customer, update_data)
        return None
