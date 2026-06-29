import unittest

from butler.policies.autonomy import (
    ActionRequest,
    AutonomyPolicy,
    Decision,
    Risk,
)


class AutonomyPolicyTests(unittest.TestCase):
    def test_explicit_user_action_is_allowed(self) -> None:
        result = AutonomyPolicy(2).evaluate(
            ActionRequest("task.create", Risk.LOW, True, "user", explicitly_approved=True)
        )
        self.assertEqual(result.decision, Decision.ALLOW)

    def test_automated_write_requires_confirmation_at_default_level(self) -> None:
        result = AutonomyPolicy(2).evaluate(
            ActionRequest("task.create", Risk.LOW, True, "automation")
        )
        self.assertEqual(result.decision, Decision.REQUIRE_CONFIRMATION)

    def test_critical_action_is_denied_even_when_approved(self) -> None:
        result = AutonomyPolicy(4).evaluate(
            ActionRequest("security.disable", Risk.CRITICAL, False, "user", True)
        )
        self.assertEqual(result.decision, Decision.DENY)


if __name__ == "__main__":
    unittest.main()
