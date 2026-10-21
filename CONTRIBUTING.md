# Development

[中文](CONTRIBUTING.zh-CN.md)

Use Python 3.10+ and Node.js 18+. Install `requirements-dev.txt` in a virtual environment. ROS is not required for the current unit tests or the synthetic preview.

```sh
python -m unittest discover -s tests -v
node tests/test_i18n.js
node --check robot/web/app.js
node --check robot/web/i18n.js
python -m compileall -q robot scripts companion harness
bash -n scripts/install.sh scripts/tunnel.sh robot/manage.sh robot/env.sh
python scripts/preview.py
```

There is no bundler. Edit `robot/web/`, then reload the preview. Use the preview for screenshots: it has no real camera images, map files, or robot connection. Check both languages, narrow screens, focus states, and numeric-input/slider synchronization. Switching language must not send a driving command or discard unsaved speed input.

Keep English source messages and their Chinese translations in `messages.js`. Use `t()` for dynamic text and `data-i18n` (or its aria/alt/placeholder variants) for markup. The server's human-readable messages are English; API keys and enums are stable identifiers. Technical diagnostics returned by external ROS processes may remain in their original language.

Changes to driving require meaningful gate tests: timeout behavior, disarming, clamping in both directions, and preservation of independent navigation limits. Do not use physical movement as an automated unit-test fixture. Robot integration tests need a separate controlled environment and an operator able to stop the robot.

Review staged files before committing. Runtime maps, bags, photos, logs, state files, secrets, and personal connection settings do not belong in this repository. Do not add a real robot address to a screenshot or example. Do not publish a running robot endpoint.

Pull requests should explain the concrete behavior change, validation performed, and any remaining hardware assumptions. Preserve upstream license notices when changing integration configuration.
