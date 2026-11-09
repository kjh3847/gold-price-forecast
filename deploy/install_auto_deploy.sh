#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$EUID" != 0 ]]; then
    echo 'Run this installer with sudo.' >&2
    exit 1
fi

source_dir="$(dirname -- "${BASH_SOURCE[0]}")"
install_dir=/opt/gold-forecast-autodeploy
repository=https://github.com/kjh3847/gold-price-forecast.git
install -d -m 0755 "$install_dir"
if [[ ! -d "$install_dir/repo/.git" ]]; then
    GIT_TERMINAL_PROMPT=0 git clone --branch main --single-branch "$repository" "$install_dir/repo"
fi
install -m 0644 "$source_dir/auto_deploy.py" "$install_dir/auto_deploy.py"
if [[ ! -f "$install_dir/baseline" ]]; then
    python3 "$install_dir/auto_deploy.py" "$install_dir/repo" "$install_dir/baseline" --baseline
fi

cat > /etc/systemd/system/gold-forecast-autodeploy.service <<'EOF'
[Unit]
Description=Deploy tested gold forecast commits
Wants=network-online.target
After=network-online.target docker.service
Requires=docker.service

[Service]
Type=oneshot
Environment=GIT_TERMINAL_PROMPT=0
Environment=WEB_BIND=0.0.0.0
Environment=WEB_PORT=8080
Environment=AWS_REGION=ap-northeast-2
Environment=COLLECTION_LOG_GROUP=/gold-forecast/events
Environment=COLLECTION_LOG_STREAM=ec2-api
ExecStart=/usr/bin/python3 /opt/gold-forecast-autodeploy/auto_deploy.py /opt/gold-forecast-autodeploy/repo /opt/gold-forecast-autodeploy/baseline
EOF

cat > /etc/systemd/system/gold-forecast-autodeploy.timer <<'EOF'
[Unit]
Description=Check for tested gold forecast commits

[Timer]
OnActiveSec=30s
OnUnitInactiveSec=2min

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now gold-forecast-autodeploy.timer
systemctl list-timers gold-forecast-autodeploy.timer --no-pager
