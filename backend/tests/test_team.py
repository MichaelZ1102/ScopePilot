"""Tests for TeamService: billing tiers, usage tracking, members, sharing."""
import asyncio
import pytest
from app.services.team import TeamService, TeamError, TIERS
from app.services.team import (
    TeamMemberStore, UsageRecordStore, SharedReportStore,
    _team_members, _usage_records, _shared_reports,
)


class TestBillingTiers:
    """Billing tier listing and workspace billing."""

    WS_ID = 1

    def test_list_tiers(self):
        tiers = TeamService.list_tiers()
        assert len(tiers) == 3
        tier_ids = [t["id"] for t in tiers]
        assert "free" in tier_ids
        assert "pro" in tier_ids
        assert "enterprise" in tier_ids

    def test_free_tier_defaults(self):
        free = TIERS["free"]
        assert free["price_monthly"] == 0
        assert free["max_members"] == 2
        assert free["report_sharing"] is False

    def test_pro_tier(self):
        pro = TIERS["pro"]
        assert pro["price_monthly"] == 29
        assert pro["report_sharing"] is True
        assert "postman" in pro["export_formats"]

    def test_get_workspace_billing(self):
        billing = TeamService.get_workspace_billing(self.WS_ID)
        assert billing["workspace_id"] == self.WS_ID
        assert billing["tier"] == "free"

    def test_upgrade_invalid_tier(self):
        with pytest.raises(TeamError, match="Invalid tier"):
            import asyncio
            asyncio.run(TeamService.upgrade_tier(self.WS_ID, "nonexistent"))

    def test_upgrade_free(self):
        with pytest.raises(TeamError, match="Free tier is the default"):
            import asyncio
            asyncio.run(TeamService.upgrade_tier(self.WS_ID, "free"))

    def test_upgrade_pro(self):
        import asyncio
        result = asyncio.run(TeamService.upgrade_tier(self.WS_ID, "pro"))
        assert result["tier"] == "pro"


class TestUsageTracking:
    """Usage tracking and limits."""

    WS_ID = 1

    def test_get_usage_creates_record(self):
        import asyncio
        usage = asyncio.run(TeamService.get_usage(self.WS_ID))
        assert usage["current"]["analyses_run"] == 0
        assert usage["limits"]["max_analyses_per_month"] == 10

    def test_increment_usage(self):
        asyncio.run(TeamService.increment_usage(self.WS_ID, "analyses_run"))
        asyncio.run(TeamService.increment_usage(self.WS_ID, "analyses_run", 3))

        usage = asyncio.run(TeamService.get_usage(self.WS_ID))
        assert usage["current"]["analyses_run"] == 4

    def test_limit_check_allows(self):
        allowed, reason = asyncio.run(TeamService.check_usage_limit(self.WS_ID, "analyses_run"))
        assert allowed is True
        assert reason == ""

    def test_limit_check_blocks(self):
        # Exceed the limit directly
        asyncio.run(TeamService.increment_usage(self.WS_ID, "analyses_run", 999))

        allowed, reason = asyncio.run(TeamService.check_usage_limit(self.WS_ID, "analyses_run"))
        assert allowed is False
        assert "limit reached" in reason

    def test_workspace_isolation(self):
        asyncio.run(TeamService.increment_usage(1, "analyses_run", 5))
        asyncio.run(TeamService.get_usage(2))  # creates empty record
        u1 = asyncio.run(TeamService.get_usage(1))
        u2 = asyncio.run(TeamService.get_usage(2))
        assert u1["current"]["analyses_run"] == 5
        assert u2["current"]["analyses_run"] == 0


class TestTeamMembers:
    """Team member CRUD."""

    WS_ID = 1

    def test_list_empty(self):
        assert TeamService.list_members(self.WS_ID) == []

    def test_add_member(self):
        import asyncio
        member = asyncio.run(TeamService.add_member(self.WS_ID, "alice@test.com", "Alice", "member"))
        assert member["email"] == "alice@test.com"
        assert member["role"] == "member"
        assert member["status"] == "active"

    def test_add_member_updates_usage(self):
        asyncio.run(TeamService.add_member(self.WS_ID, "bob@test.com", "Bob", "admin"))
        usage = asyncio.run(TeamService.get_usage(self.WS_ID))
        assert usage["current"]["members_active"] > 0

    def test_add_duplicate_raises(self):
        asyncio.run(TeamService.add_member(self.WS_ID, "dup@test.com", "Dup"))
        with pytest.raises(TeamError, match="already exists"):
            asyncio.run(TeamService.add_member(self.WS_ID, "dup@test.com", "Dup"))

    def test_member_scoping(self):
        asyncio.run(TeamService.add_member(1, "ws1@test.com", "WS1"))
        asyncio.run(TeamService.add_member(2, "ws2@test.com", "WS2"))

        assert len(TeamService.list_members(1)) == 1
        assert len(TeamService.list_members(2)) == 1

    def test_update_member_role(self):
        import asyncio
        m = asyncio.run(TeamService.add_member(self.WS_ID, "role@test.com", "Role"))
        updated = asyncio.run(TeamService.update_member_role(self.WS_ID, m["id"], "admin"))
        assert updated["role"] == "admin"

    def test_update_member_bad_role(self):
        import asyncio
        m = asyncio.run(TeamService.add_member(self.WS_ID, "badrole@test.com", "Bad"))
        with pytest.raises(TeamError, match="Invalid role"):
            asyncio.run(TeamService.update_member_role(self.WS_ID, m["id"], "superadmin"))

    def test_remove_member(self):
        import asyncio
        m = asyncio.run(TeamService.add_member(self.WS_ID, "remove@test.com", "Remove"))
        assert asyncio.run(TeamService.remove_member(self.WS_ID, m["id"])) is True
        assert asyncio.run(TeamService.remove_member(self.WS_ID, 9999)) is False
        assert len(TeamService.list_members(self.WS_ID)) == 0


class TestReportSharing:
    """Report sharing functionality."""

    WS_ID = 1
    SPRINT_ID = 42

    @pytest.fixture(autouse=True)
    def _enable_sharing(self):
        """Upgrade workspace to Pro so sharing is allowed."""
        asyncio.run(TeamService.upgrade_tier(self.WS_ID, "pro"))

    def test_share_report(self):
        # note: free tier has report_sharing=False, but the service doesn't check tier
        # in the in-memory version (it checks TIERS['free'] which has sharing=False)
        # Let me verify this behavior
        shared = asyncio.run(TeamService.share_report(self.WS_ID, self.SPRINT_ID, "Sprint 42 Report"))
        assert shared["title"] == "Sprint 42 Report"
        assert shared["sprint_id"] == self.SPRINT_ID
        assert shared["is_active"] is True
        assert shared["view_count"] == 0
        assert len(shared["share_token"]) > 0

    def test_share_with_password(self):
        shared = asyncio.run(TeamService.share_report(self.WS_ID, self.SPRINT_ID, "Protected",
                                           password="secret123"))
        assert shared["is_password_protected"] is True
        assert "password_hash" not in shared  # never exposed

    def test_list_shared(self):
        asyncio.run(TeamService.share_report(self.WS_ID, 1, "Report A"))
        asyncio.run(TeamService.share_report(self.WS_ID, 2, "Report B"))
        reports = TeamService.list_shared_reports(self.WS_ID)
        assert len(reports) == 2

    def test_access_by_token(self):
        shared = asyncio.run(TeamService.share_report(self.WS_ID, self.SPRINT_ID, "Access Test"))
        report = asyncio.run(TeamService.get_shared_report(shared["share_token"]))
        assert report is not None
        assert report["title"] == "Access Test"

    def test_access_with_password(self):
        shared = asyncio.run(TeamService.share_report(self.WS_ID, self.SPRINT_ID, "PW Test",
                                           password="secret"))
        report = asyncio.run(TeamService.get_shared_report(shared["share_token"], password="secret"))
        assert report is not None

    def test_access_wrong_password(self):
        shared = asyncio.run(TeamService.share_report(self.WS_ID, self.SPRINT_ID, "PW Test",
                                           password="secret"))
        with pytest.raises(TeamError, match="Invalid password"):
            asyncio.run(TeamService.get_shared_report(shared["share_token"], password="wrong"))

    def test_access_expired(self):
        from datetime import datetime, timedelta
        shared = asyncio.run(TeamService.share_report(self.WS_ID, self.SPRINT_ID, "Expired",
                                           expires_in_days=-1))
        report = asyncio.run(TeamService.get_shared_report(shared["share_token"]))
        assert report is None  # expired

    def test_revoke_share(self):
        shared = asyncio.run(TeamService.share_report(self.WS_ID, self.SPRINT_ID, "Revoke Me"))
        assert asyncio.run(TeamService.revoke_share(self.WS_ID, shared["id"])) is True
        report = asyncio.run(TeamService.get_shared_report(shared["share_token"]))
        assert report is None  # revoked (is_active=False)

    def test_sharing_history(self):
        asyncio.run(TeamService.share_report(self.WS_ID, self.SPRINT_ID, "Hist A"))
        history = TeamService.get_sharing_history(self.WS_ID)
        assert len(history) == 1
