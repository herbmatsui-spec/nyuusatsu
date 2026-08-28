from sqlalchemy.orm import Session
from database.repositories.partner_repository import PartnerRepository
from database.models import Partner
from typing import List, Optional

class PartnerService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = PartnerRepository(session)

    def create_partner(self, partner_data: dict) -> Partner:
        return self.repo.create(partner_data)

    def get_partner(self, partner_id: int) -> Optional[Partner]:
        return self.repo.get_by_id(partner_id)

    def list_partners(self, skip: int = 0, limit: int = 100) -> List[Partner]:
        return self.repo.list_all(skip, limit)

    def update_partner(self, partner_id: int, update_data: dict) -> Optional[Partner]:
        partner = self.get_partner(partner_id)
        if partner:
            return self.repo.update(partner, update_data)
        return None
