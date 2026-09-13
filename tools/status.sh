set -eu
systemctl --user show astro-kiosk -p ActiveState -p NRestarts
systemctl show astro-panel -p ActiveState -p NRestarts
chromium --version
curl -s http://127.0.0.1:8080/api/status | python3 -c 'import sys,json; d=json.load(sys.stdin); print({k: v.get("updated_at") for k,v in d.items() if isinstance(v,dict)}); print(d["errors"])'
vcgencmd get_throttled
vcgencmd measure_temp
free -h
