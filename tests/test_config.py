from refurboard_py import config


def test_default_config_round_trip(tmp_path, monkeypatch):
    target = tmp_path / "refurboard.config.json"

    def fake_config_dir():
        return tmp_path

    monkeypatch.setattr(config, "_config_dir", fake_config_dir)

    cfg = config.load_config()
    assert cfg.camera.device_id == 0
    cfg.detection.sensitivity = 0.9
    config.save_config(cfg)

    loaded = config.load_config()
    assert loaded.detection.sensitivity == 0.9
