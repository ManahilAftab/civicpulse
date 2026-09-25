from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Complaint
from app.repositories.complaint_repository import ComplaintRepository
from app.seed import run_seed
from app.seed_data import SEED_COMPLAINTS


def test_seed_is_idempotent_and_spread_across_categories(engine):
    with Session(engine) as session:
        repo = ComplaintRepository(session)
        assert run_seed(repo) == len(SEED_COMPLAINTS) >= 30
        assert run_seed(repo) == 0  # second run changes nothing
        assert session.scalar(select(func.count()).select_from(Complaint)) == len(SEED_COMPLAINTS)
        categories = repo.count_by("category")
    assert len(categories) == 6 and min(categories.values()) >= 3
