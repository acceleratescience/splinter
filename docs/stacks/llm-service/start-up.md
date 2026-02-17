# LLM Inference Service Startup

## Introduction 

This guide walks through a quickstart of the LLM service. We cover the basic steps, some quick penetration tests, adding a custom domain, adding additional models, and third party providers.

## Setup

First, SSH into your server and clone the `splinter` repo. Change the permissions for the relevant scripts:

```bash
chmod +x ./scripts/setup.sh
chmod +x ./scripts/monitoring.sh
chmod +x ./scripts/llm-service.sh
```

Copy the secrets template:

```bash
cp ./stacks/llm-service/.env.example ./stacks/llm-service/.env
```

and change any default passwords. If you are adding a custom domain then add this as well. If not, then change this to the IP or address of your machine.

Here is the order of operations:

```bash
sudo ./scripts/setup.sh
```
You can run the next ones as `sudo` or add a new group:

```bash
newgrp docker
```

and then run

```bash
./scripts/monitoring.sh # optional, but you should really do it
./scripts/llm-service.sh
```

### Add TLS certificates (optional)

If you have a custom domain with DNS pointing to your server:
```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.here.com
sudo certbot renew --dry-run  # verify auto-renewal
```

You should now be good to go!

## Penetration Tests

Before doing any kind of port forwarding to connect to the admin panel, run these tests from your local machine.

### Port scan

Only ports 22, 80, and 443 should be open.
```bash
nmap -sV your.url.here.com
```

### TLS configuration (if using certificates)

All ciphers should be grade A, TLS 1.2+ only.
```bash
nmap --script ssl-enum-ciphers -p 443 your.url.here.com
```

### HTTP headers

Check for security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy).
```bash
curl -I https://your.url.here.com
```

### Unauthenticated endpoint scan

Set up an SSH tunnel to access the admin port and grab all endpoints from the OpenAPI spec:
```bash
ssh -fN -L 4000:localhost:4000 -i ~/.ssh/your_key user@your.server.ip
ENDPOINTS=$(curl -s http://localhost:4000/openapi.json | jq -r '.paths | keys[]')
```

Every endpoint should return 401 without an Authorization header:
```bash
for path in $ENDPOINTS; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "https://your.url.here.com${path}")
    if [ "$code" != "401" ]; then
        echo "WARNING: $path returned $code (expected 401)"
    else
        echo "OK: $path"
    fi
done
```

### Blocked endpoints (even with valid auth)

Docs, config, and admin endpoints should return 404 even with a valid key.
```bash
KEY="your_master_key"

for path in /redoc /openapi.json /swagger /test /ui /docs /config/yaml /health/liveliness /health/readiness; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "https://your.url.here.com${path}" \
        -H "Authorization: Bearer ${KEY}")
    if [ "$code" != "404" ]; then
        echo "WARNING: $path returned $code (expected 404)"
    else
        echo "OK: $path"
    fi
done
```

### Privilege escalation

Create a regular (non-admin) user key and check it cannot access admin endpoints.
```bash
KEY="your_regular_user_key"
ADMIN_PATHS="/key/generate /key/list /user/list /model/new /model/delete /config/list /config/yaml /spend/logs /global/spend/logs"

for path in $ENDPOINTS; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:4000${path}" \
        -H "Authorization: Bearer ${KEY}")
    for admin in $ADMIN_PATHS; do
        if [ "$path" = "$admin" ] && [ "$code" = "200" ]; then
            echo "WARNING: Regular key got 200 on admin endpoint $path"
        fi
    done
done
```

### Host header injection

Should return 000 (connection dropped) or 444.
```bash
curl -s -o /dev/null -w "%{http_code}" -H "Host: evil.com" https://your.url.here.com/
```

### HTTP method abuse

All should return 405.
```bash
for method in PUT DELETE PATCH OPTIONS TRACE; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "https://your.url.here.com/" \
        -H "Authorization: Bearer ${KEY}")
    echo "$code $method"
done
```

### Rate limiting

Should see a mix of 401 and 503 responses.
```bash
seq 100 | parallel -j 100 'curl -s -o /dev/null -w "%{http_code}\n" "https://your.url.here.com/health"' | sort | uniq -c
```

### Attack vector paths

All should return 000 (connection dropped) or 401.
```bash
for path in /.env /.git/config /wp-admin /xmlrpc.php /test.php; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "https://your.url.here.com${path}")
    echo "$code $path"
done
```

### Path traversal

All should return 400 or 401.
```bash
for path in \
    "/../../etc/passwd" \
    "/%2e%2e/%2e%2e/etc/passwd" \
    "/..%2f..%2f..%2fetc/passwd" \
    "/v1/..%2f.env" \
    "/health/../../../.env"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "https://your.url.here.com${path}")
    echo "$code $path"
done
```

### SSH hardening (on the server)

Should show `passwordauthentication no` and `permitrootlogin no`.
```bash
sudo sshd -T | grep -E "passwordauthentication|permitrootlogin|permitemptypasswords|x11forwarding"
```

### External listeners (on the server)

Only ports 22, 80, 443 should be bound to 0.0.0.0.
```bash
sudo ss -tlnp | grep -v 127.0.0.1
```

## Adding additional models

As it stands, we have only one model. To add more, you need to alter a couple of files.

### `docker-compose.yml`
If you have multiple GPUs, you can specify which models you want to run on which devices. So change the `devices` section to the following:

```yml
vllm-model-a:
  # ...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ["0", "1"]
            capabilities: [gpu]
  command: >
    --model ${VLLM_MODEL_A}
    --gpu-memory-utilization ${VLLM_GPU_MEMORY_UTILIZATION}
    --tensor-parallel-size 2

vllm-model-b:
  # ...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ["2", "3"]
            capabilities: [gpu]
  command: >
    --model ${VLLM_MODEL_B}
    --gpu-memory-utilization ${VLLM_GPU_MEMORY_UTILIZATION}
    --tensor-parallel-size 2
```

Of course, you'll need to change things like `--tensor-parallel-size` if you have a GPU count that is not 2.

### `litellm_config.yaml`

And now update the LiteLLM config to list your models:

```yaml
model_list:
  - model_name: model-a
    litellm_params:
      model: openai/model-a
      api_base: http://vllm-model-a:8000/v1
      api_key: "none"
  - model_name: model-b
    litellm_params:
      model: openai/model-b
      api_base: http://vllm-model-b:8000/v1
      api_key: "none"
```

## Adding third party providers

Pretty simple really: do it via the LiteLLM admin panel! To access the admin UI, run

```bash
ssh -fN -L 4000:localhost:4000 user@server
```

We have purposefully made the admin panel not accessible online -- you must SSH into the server in order to access it. In this case we are forwarding to our local machine. Then navigate to http://localhost:4000/ui in the browser.

## Additional considerations

Add fail2ban. This will just ban people who try to aggressively attack your public endpoint.

```bash
sudo apt-get install -y fail2ban
```

Then create a `/etc/fail2ban/jail.local`

```ini
[nginx-botsearch]
enabled = true
port = http,https
filter = nginx-botsearch
logpath = /var/log/nginx/access.log
maxretry = 5
bantime = 86400
```