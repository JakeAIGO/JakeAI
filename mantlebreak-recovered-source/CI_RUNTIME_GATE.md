# Automated Godot Runtime Gate

This package includes `.github/workflows/godot-qa.yml`.

When the project is placed in a GitHub repository, the workflow is designed to:
1. Install Godot 4.3 on an Ubuntu runner.
2. Import the project headlessly.
3. Run `SmokeTest.tscn`.
4. Run the 250-run autonomous balance simulation.
5. Parse/import the project again for script errors.
6. If QA passes, install Godot export templates.
7. Export `DeepShift.exe`.
8. Upload the Windows build as a GitHub Actions artifact.

This converts the current local-environment limitation into an automated build/test/export gate.

Important: the workflow itself still needs to run successfully before we can claim runtime QA or a working Windows executable.
