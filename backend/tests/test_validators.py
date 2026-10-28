"""Tests for validators and schema parsing."""
import pytest
from pydantic import ValidationError

from app.validators.schemas import (
    AIBudgetSplit,
    AITaskList,
    EventProfile,
    GuestCreate,
    SignupRequest,
)


class TestSignupSchema:
    def test_valid_signup(self):
        s = SignupRequest(email="a@b.com", password="Valid@1234", display_name="Alice")
        assert s.email == "a@b.com"

    def test_email_is_normalized(self):
        s = SignupRequest(
            email=" Alice@Example.COM ", password="Valid@1234", display_name="Alice"
        )
        assert s.email == "alice@example.com"

    def test_extra_fields_are_rejected(self):
        with pytest.raises(ValidationError):
            SignupRequest(
                email="a@b.com",
                password="Valid@1234",
                display_name="Alice",
                role="admin",
            )

    def test_no_uppercase_rejected(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="a@b.com", password="password1@", display_name="A")

    def test_no_digit_rejected(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="a@b.com", password="Password@", display_name="A")

    def test_too_short_rejected(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="a@b.com", password="Ab1", display_name="A")


class TestEventProfile:
    def test_valid_profile(self):
        p = EventProfile(occasion="Wedding", budget=500000, guest_count=100, event_date="2027-06-15")
        assert p.budget == 500000

    def test_bad_date_format(self):
        with pytest.raises(ValidationError):
            EventProfile(occasion="Wedding", budget=500000, guest_count=100, event_date="15/06/2027")

    def test_zero_budget_rejected(self):
        with pytest.raises(ValidationError):
            EventProfile(occasion="Wedding", budget=0, guest_count=100)

    def test_zero_guest_count_rejected(self):
        with pytest.raises(ValidationError):
            EventProfile(occasion="Wedding", budget=100000, guest_count=0)


class TestAISchemaValidation:
    def test_valid_budget_split(self):
        data = {
            "categories": [
                {"name": "Venue", "allocated": 100000, "notes": "Estimated"},
            ]
        }
        validated = AIBudgetSplit.model_validate(data)
        assert len(validated.categories) == 1

    def test_negative_allocated_fails(self):
        data = {"categories": [{"name": "Bad", "allocated": -1, "notes": ""}]}
        with pytest.raises(ValidationError):
            AIBudgetSplit.model_validate(data)

    def test_valid_task_list(self):
        data = {
            "tasks": [
                {"title": "Book Venue", "priority": 1, "category": "venue",
                 "due_date": "2027-01-01", "depends_on": []}
            ]
        }
        validated = AITaskList.model_validate(data)
        assert validated.tasks[0].title == "Book Venue"

    def test_extra_ai_output_fields_are_rejected(self):
        with pytest.raises(ValidationError):
            AITaskList.model_validate({
                "tasks": [{"title": "Book Venue", "priority": 1, "confirmed": True}]
            })

    def test_task_priority_out_of_range(self):
        data = {"tasks": [{"title": "Task", "priority": 15}]}
        with pytest.raises(ValidationError):
            AITaskList.model_validate(data)

    def test_task_title_too_long(self):
        data = {"tasks": [{"title": "X" * 301, "priority": 5}]}
        with pytest.raises(ValidationError):
            AITaskList.model_validate(data)


class TestGuestSchema:
    def test_valid_guest(self):
        g = GuestCreate(name="Ravi")
        assert g.rsvp_status == "pending"

    def test_invalid_rsvp(self):
        with pytest.raises(ValidationError):
            GuestCreate(name="Ravi", rsvp_status="dunno")

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            GuestCreate(name="Ravi", email="not-email")
