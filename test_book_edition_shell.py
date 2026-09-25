from book_edition_shell import SHELL_PROFILES

def test_reference_batch_has_shell_profiles():
    expected={"JAE-TTM-001","JAE-SH-001","JAE-DRAC-001","JAE-TI-001","JAE-FRANK-001","JAE-ALICE-001","JAE-MOBY-001","JAE-PRIDE-001","JAE-JANE-001","JAE-DORIAN-001"}
    assert expected==set(SHELL_PROFILES)

def test_all_shell_profiles_are_non_impersonation_profiles():
    for p in SHELL_PROFILES.values():
        assert "celebrity" not in p["narrator"].lower()
