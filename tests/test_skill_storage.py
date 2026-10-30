from core.dynamic_registry import DynamicToolRegistry


def test_generated_skills_use_writable_user_vault(tmp_path, monkeypatch):
    bundle_features = tmp_path / "bundle" / "features"
    user_vault = tmp_path / "Application Support" / "NexusCore" / "skills"

    monkeypatch.setattr("core.dynamic_registry.FEATURES_DIR", bundle_features)
    monkeypatch.setattr("core.dynamic_registry.APPDATA_SKILLS_DIR", user_vault)

    result = DynamicToolRegistry.get_skills_directory()

    assert result == user_vault
    assert result.is_dir()
    assert not bundle_features.exists()
