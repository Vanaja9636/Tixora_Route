"""
Tests for business rules enforcement.

Verifies:
- Safety priority rule PR-001
- Priority escalation logic
- SLA minutes per priority
- Routing rule enforcement across all four rules
"""
import pytest
from tixora_route.priority import enforce_priority, priority_score
from tixora_route.sla import SLA_MINUTES


class TestPriorityRules:
    def test_safety_low_becomes_urgent(self):
        """PR-001: safety+low → urgent."""
        p, reason = enforce_priority("safety", "low")
        assert p == "urgent"
        assert "PR-001" in reason or "urgent" in reason.lower()

    def test_safety_normal_becomes_urgent(self):
        """PR-001: safety+normal → urgent."""
        p, _ = enforce_priority("safety", "normal")
        assert p == "urgent"

    def test_safety_high_becomes_urgent(self):
        """PR-001: safety+high → urgent."""
        p, _ = enforce_priority("safety", "high")
        assert p == "urgent"

    def test_safety_urgent_stays_urgent(self):
        """PR-001: safety+urgent → urgent (no change)."""
        p, _ = enforce_priority("safety", "urgent")
        assert p == "urgent"

    def test_billing_low_stays_low(self):
        """Billing intent does not force priority changes."""
        p, _ = enforce_priority("billing", "low")
        assert p == "low"

    def test_billing_normal_stays_normal(self):
        p, _ = enforce_priority("billing", "normal")
        assert p == "normal"

    def test_technical_high_stays_high(self):
        p, _ = enforce_priority("technical", "high")
        assert p == "high"

    def test_priority_score_ordering(self):
        """Priority scores must be strictly ordered: low < normal < high < urgent."""
        assert priority_score("low") < priority_score("normal")
        assert priority_score("normal") < priority_score("high")
        assert priority_score("high") < priority_score("urgent")

    def test_unknown_intent_no_override(self):
        """Unknown intent must not override priority."""
        p, _ = enforce_priority("unknown_intent", "low")
        assert p == "low"


class TestSLAMinutes:
    def test_urgent_sla_is_30(self):
        assert SLA_MINUTES["urgent"] == 30

    def test_high_sla_is_120(self):
        assert SLA_MINUTES["high"] == 120

    def test_normal_sla_is_240(self):
        assert SLA_MINUTES["normal"] == 240

    def test_low_sla_is_480(self):
        assert SLA_MINUTES["low"] == 480

    def test_urgent_sla_shorter_than_normal(self):
        assert SLA_MINUTES["urgent"] < SLA_MINUTES["normal"]


class TestRoutingRules:
    def test_skill_enforcement(self, db):
        """RR-001: Routing must enforce skill matching."""
        from tixora_route.generator import generate
        from tixora_route.models import Ticket, Agent
        from tixora_route.routing import route_ticket
        from sqlalchemy import select
        generate(db, tickets=5, messages=5, seed=20261022, agent_count=10)
        t = db.scalar(select(Ticket))
        t.required_skill = "nonexistent_skill"
        db.flush()
        result = route_ticket(db, t)
        assert result["decision"] == "queued"

    def test_language_enforcement(self, db):
        """RR-002: Routing must enforce language matching."""
        from tixora_route.generator import generate
        from tixora_route.models import Ticket, Language
        from tixora_route.routing import route_ticket
        from sqlalchemy import select
        generate(db, tickets=5, messages=5, seed=20261022, agent_count=10)
        t = db.scalar(select(Ticket))
        # Use a valid language row that no generated agent speaks.
        unsupported_language = Language(code="zz", name="Unsupported")
        db.add(unsupported_language)
        db.flush()
        t.language = unsupported_language
        db.flush()
        result = route_ticket(db, t)
        assert result["decision"] == "queued"

    def test_capacity_enforcement(self, db):
        """RR-004: Routing must not assign to agents at capacity."""
        from tixora_route.generator import generate
        from tixora_route.models import Ticket, Agent
        from tixora_route.routing import route_ticket
        from sqlalchemy import select
        generate(db, tickets=5, messages=5, seed=20261022, agent_count=4)
        # Set all agents to capacity=0
        for a in db.scalars(select(Agent)):
            a.capacity = 0
        db.flush()
        for t in db.scalars(select(Ticket)):
            result = route_ticket(db, t)
            assert result["decision"] == "queued"
