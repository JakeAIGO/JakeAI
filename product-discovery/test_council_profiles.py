import unittest

import council_profiles as profiles


class CouncilProfileTests(unittest.TestCase):
    def test_known_profiles_require_all_five_independent_seats(self):
        self.assertEqual(set(profiles.PROFILES), {"full", "product", "security", "commercial", "release"})
        for profile in profiles.PROFILES.values():
            self.assertEqual(profile.required_seats, profiles.ALL_SEATS)
            self.assertTrue(profile.human_approval_required)

    def test_unknown_profile_fails_closed(self):
        with self.assertRaises(ValueError):
            profiles.get_profile("anything-goes")

    def test_profile_overlay_preserves_dissent_and_human_gate(self):
        text = profiles.profile_overlay("release")
        self.assertIn("Preserve dissent", text)
        self.assertIn("Human approval remains required", text)

    def test_no_profile_has_release_authority(self):
        for name in profiles.PROFILES:
            self.assertFalse(profiles.release_authority(name))


if __name__ == "__main__":
    unittest.main()
