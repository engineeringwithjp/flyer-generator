"""Tests for campaign planner and anti-fatigue service rotation."""

from src.core.campaign_planner import CampaignPlanner


def test_plan_campaigns_count(sample_client):
    planner = CampaignPlanner()
    plans = planner.plan_campaigns(sample_client, count=2)
    assert len(plans) == 2
    assert plans[0]["service"] != plans[1]["service"]

def test_plan_campaigns_user_override(sample_client):
    planner = CampaignPlanner()
    plans = planner.plan_campaigns(
        sample_client,
        count=1,
        requested_campaign="Composite Siding",
        requested_focus="Built-in insulation"
    )
    assert len(plans) == 1
    assert plans[0]["service"] == "Composite Siding"
    assert plans[0]["focus"] == "Built-in insulation"
