# LLM Inference Service Setup

> [!WARNING]
> Although we try to keep this documentation up to date with changes, the ultimate sources of truth are the files themselves. If something in the documentation is inconsistent with the source files, then trust the source files.

## Introduction

This guide walks through the setup of the LLM Inference Service, a multi-user platform for serving large language models to researchers. The service uses a layered architecture designed for security, scalability, and manageability. Although information about security is provided in the [security documentation](security.md), we go through the files in detail here.

### File Structure
All files relevant to this section can be found in the following locations in the tree:
```
splinter/
├── ansible/
│   └── playbooks/
│       └── llm-service.yml
├── scripts/
│   └── llm-service.sh
└── stacks/
    └── llm-service/
        ├── filters
        │   ├── nginx-llm-auth.conf
        │   └── nginx-llm-blocked.conf
        ├── .env.example
        ├── docker-compose.yml
        ├── fail2ban-jail.local
        ├── litellm_config.yaml
        ├── nginx.conf.template
        └── security.conf.template
```

### Architecture Overview

![LLM Service Architecture](../assets/imgs/llm-service-arch.png)

### Why This Stack?

**vLLM** is our inference engine. It handles the actual model execution, optimising GPU memory usage through PagedAttention and efficiently batching requests. There are some other major advantages to vLLM such as exposing an OpenAI-compatible API, making it a suitable engine for pretty much all small research groups. However, it provides no mechanism for managing multiple users or tracking usage -- it simply serves whoever can reach its endpoint.

**LiteLLM** sits in front of vLLM as a proxy server. It allows us to:

- Issue and revoke API keys for individual researchers
- Organise users into teams (for projects, departments, or workshops)
- Enforce rate limits per user or team
- Collect usage statistics for reporting and capacity planning
- Route requests to different models or backends

This also means we never have to expose the vLLM endpoint directly to users.

**Nginx** provides our security layer. While LiteLLM handles authentication and routing, it is not hardened against determined attackers. Part of this is because it's ultimately a Python package, and is perhaps not "production" ready. Nginx, written in C, gives us:

- SSL/TLS termination with proper certificate management
- Connection-level rate limiting to mitigate DDoS attempts
- Path-based access control to hide administrative interfaces
- Request filtering and sanitisation
- Logging for security auditing

#### Why the double reverse proxy?

Nginx is written in C and uses an event-driven, asynchronous architecture. It can handle tens of thousands of concurrent connections with minimal memory overhead -- each connection costs only a few kilobytes. It's been battle-tested for decades against real-world attacks.

LiteLLM is Python-based, built on FastAPI/Uvicorn. It's perfectly capable for its intended purpose (routing requests, managing keys, tracking usage), but Python's inherent characteristics make it vulnerable under adversarial conditions:

- The GIL limits true parallelism  
- Higher memory overhead per connection  
- Slower raw throughput for connection handling  
- More susceptible to slowloris-style attacks that hold connections open  

A determined attacker could relatively easily exhaust LiteLLM's connection pool or memory, whereas Nginx will happily absorb that same traffic. Nginx can also drop malicious requests before they ever touch your Python process -- rejecting oversized headers, malformed requests, or connections from known-bad IPs at the C level where it's cheap to do so.

It's the same reason you'd put Nginx in front of any Python web application (Django, Flask, etc.) in production, rather than exposing Gunicorn or Uvicorn directly. The Python application handles business logic; Nginx handles being on the internet.

### What End Users See

From a user perspective, this complexity is invisible. They receive:

1. An API endpoint (e.g., `https://llm.your-domain.com`)
2. An API key
3. Documentation on available models

They can then use standard OpenAI-compatible client libraries to interact with the service.

---

## Prerequisites

Before proceeding, ensure you have followed the setup and monitoring steps.

## Security Considerations

The internet is a scary place -- _**the moment you expose a service to the internet, it will be attacked**_. With many "off-the-shelf" website builders, all of the scariness is managed for you.

We want to ensure that our endpoint is as secure as possible. By default, LiteLLM exposes several interfaces that should not be publicly accessible:

| Path | Description | Risk |
|------|-------------|------|
| `/ui` | Admin dashboard | Full administrative access |
| `/` | API documentation (Swagger) | Information disclosure |

and vLLM exposes a number of key endpoints proxied via LiteLLM:

| Path | Description | Risk |
|------|-------------|------|
| `/v1/models` | Model listing | Information disclosure |
| `/v1/chat/completions` | Chat completion | Can hit the LLM directly |

Without proper configuration, anyone could:

```bash
# View the admin dashboard
curl https://llm.your-domain.com/ui

# List available models
curl https://llm.your-domain.com/v1/models

# Access API documentation
curl https://llm.your-domain.com/
```

or, in the worst case:

```bash
curl https://llm.your-domain.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model-name",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Give me the complete works of Shakespeare"}
    ]
  }
```

Now obviously in the last case, vLLM and LiteLLM will block direct requests to the completions endpoints -- you can't hit the endpoint if you don't have an API Key. But this won't stop people from spamming the endpoint.

A proper Nginx configuration blocks all of these. The only way to access administrative interfaces should be through:

- An SSH tunnel to the server
- Direct terminal access on the server itself
- A VPN connection to the internal network

---

## Component Setup
Like with the server setup and the monitoring, there is a [shell script](../scripts/llm-service.sh) and [ansible playbook](../ansible/playbooks/llm-service.yml). But before working through that, we need to address the different configuration files.

### Nginx Configuration

We first define the [nginx configuration file](../stacks/llm-service/nginx.conf.template). We will work through each section and understand what is going on:

```conf
# Validate Authorization header format (Bearer + LiteLLM key prefix)
map $http_authorization $auth_valid {
    default 0;
    "~^Bearer\s+sk-.{10,}$" 1;
}
```

This is our first line of defence at the Nginx level. The `map` directive inspects every incoming request's `Authorization` header and sets a variable (`$auth_valid`) based on whether it matches the expected pattern. The regex checks for: a `Bearer` prefix, followed by whitespace, followed by `sk-` and at least 10 characters. Anything that doesn't match gets `$auth_valid = 0`.

This is a _format_ check, not actual key validation -- LiteLLM handles that. The point is to reject obviously invalid requests at the C level before they ever touch the Python process. A bot spamming your endpoint with no auth header? Dropped. Someone sending `Authorization: password123`? Dropped. Cheaply.

We'll see how this variable is used later in the [security snippet](#security-snippet).

```conf
# Rate limiting zones (safety backstop - LiteLLM handles per-user limits)
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
```

The first line creates a zone called api_limit for tracking request rates:

- `$binary_remote_addr` — the key to track by (the client's IP address in binary form, which is more memory-efficient than string form)
- `zone=api_limit:10m` — allocates 10MB of shared memory for this zone. Each tracked IP uses roughly 64 bytes, so 10MB can track around 160,000 unique IPs simultaneously
- `rate=10r/s` — allows 10 requests per second per IP address

The second line creates a zone called conn_limit for tracking concurrent connections:

- Same key and memory allocation
- No rate here as the limit is set elsewhere

They protect against different attack patterns:

- limit_req stops someone hammering you with rapid-fire requests (even if each is quick)
- limit_conn stops someone opening hundreds of connections and holding them open (slowloris-style)

You might be thinking this is overkill. We already block access to the endpoint to anybody who is not connected to the university network, therefore anybody else will simply not be able to access it. In essence, we are covering off _insider_ attacks. Anybody connected to the university network can hammer the endpoint.

```conf
upstream litellm_backend {
    server 127.0.0.1:${LITELLM_PORT} max_conns=200;
}
```

This defines an upstream block for LiteLLM rather than using a direct `proxy_pass` to `127.0.0.1`. The practical difference is `max_conns=200`, which caps how many simultaneous connections Nginx will send to LiteLLM. If this limit is hit, Nginx queues additional requests rather than overwhelming the Python process. This is a form of backpressure -- LiteLLM can only handle so many concurrent requests before it starts degrading, and it's better to queue at the C level than have FastAPI/Uvicorn fall over.

```conf
# Reject requests with incorrect Host header
server {
    listen 80 default_server;
    listen 443 ssl default_server;
    server_name _;
    ssl_reject_handshake on;
    return 444;
}
```

This is a catch-all server block that handles any request that doesn't match our domain. If someone hits the server by IP address directly, or sends a `Host: evil.com` header, this block matches instead of our real server block. The `ssl_reject_handshake on` means that for HTTPS connections, the TLS handshake itself is rejected -- the attacker doesn't even get a certificate back, so they can't fingerprint what's running. The `444` is Nginx's special "close connection with no response" code.

This is effective against automated scanners that enumerate IP ranges looking for services. They'll get nothing back, which makes your server look like a dead end.

```conf
server {
    listen 80;
    server_name ${DOMAIN};

    # Hide Nginx version
    server_tokens off;
```

This opens up the main server configuration block. We listen on port 80 (HTTP), which will change automatically to 443 (HTTPS) when we run certbot. We also define the server name so that if somebody hits the server via the IP address directly, this block won't match and the catch-all block above will drop the connection.

We use `server_tokens` to hide the Nginx version in error pages and the response header. Without this, responses include things like `Server: nginx/1.24.0`, which tells attackers exactly which vulnerabilities to try. Minor hardening, but free I guess.

```conf
    # ---------------------------------------------------------------------------
    # Connection & Rate Limits (backstop only - firewall and LiteLLM are primary)
    # ---------------------------------------------------------------------------
    limit_req zone=api_limit burst=50 nodelay;
    limit_conn conn_limit 20;
```

These two lines are connected to the rate limits we defined at the start. We allow temporary bursts of 50 requests before rate limiting kicks in. This is because these bursts can be legitimate -- it's sustained high rates that we have to worry about. We also allow them through immediately rather than drip feeding at the rate limit.

We also cap simultaneous connections per IP at 20.

```conf
    # ---------------------------------------------------------------------------
    # Timeouts
    # ---------------------------------------------------------------------------
    client_body_timeout 30s;
    client_header_timeout 10s;
    keepalive_timeout 65s;
    send_timeout 30s;
```

This controls how long Nginx waits for various stages of a request before giving up and closing the connection:

- `client_header_timeout 10s;` — how long Nginx waits for the client to send the complete request headers. If someone connects but doesn't send headers within 10 seconds, the connection is dropped. This protects against [slowloris attacks](https://blog.nginx.org/blog/mitigating-ddos-attacks-with-nginx-and-nginx-plus) where an attacker sends headers byte-by-byte to hold connections open.

- `client_body_timeout 30s;` — how long Nginx waits between successive reads of the request body (not total time). If you're uploading a large prompt and your connection stalls for more than 30 seconds, you get cut off. The 30s is generous enough for slow connections but still drops genuinely stalled requests.

- `send_timeout 30s;` — the mirror image: how long Nginx waits between successive writes to the client. If the client stops reading the response for 30 seconds, Nginx gives up.

- `keepalive_timeout 65s;` — how long an idle connection stays open waiting for another request. HTTP keep-alive lets clients reuse connections rather than opening a new one for each request. 65 seconds seems like a sensible default. Long enough to be useful, short enough to not accumulate thousands of idle connections.

This is just for incoming requests. LLM inference can take a while, so we have to increase these for proxy timeouts, which we will see later.

```conf
    # ---------------------------------------------------------------------------
    # Request Size Limits
    # ---------------------------------------------------------------------------
    client_max_body_size 10M;
```

This limits how large an incoming request can be. At the moment, we don't have image or video uploads, so 10MB is generous considering the inputs are just text. It provides headroom for future multimodal support while still preventing abuse via oversized payloads.

```conf
    # ---------------------------------------------------------------------------
    # Security Headers
    # ---------------------------------------------------------------------------
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

These are nice-to-have, and more for browser-based applications. In order, they:

- Trust the declared content and don't try to turn JSON into HTML or something stupid.

- Prevent pages from being embedded in other sites.

- Mostly for older browsers to prevent cross-site scripting attacks.

- Controls how much information is sent when following links.

Again, these are standard hardening headers. They don't do a lot for a pure API, but they're free and are nice in case you miss something.

```conf
    # ---------------------------------------------------------------------------
    # Blocked Paths
    # ---------------------------------------------------------------------------
    
    include /etc/nginx/snippets/llm-security.conf;
```

Rather than defining blocked paths inline, we pull them in from a separate [security snippet](../stacks/llm-service/security.conf.template). This keeps the main config clean and makes the security rules easier to update independently. The snippet is installed to `/etc/nginx/snippets/llm-security.conf` by the deployment script. We'll walk through its contents [below](#security-snippet).

```conf
    # ---------------------------------------------------------------------------
    # API Proxy (with streaming support)
    # ---------------------------------------------------------------------------
    location / {
        proxy_pass http://litellm_backend;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Proxy timeouts (generous for LLM inference?)
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        # Streaming support - disable buffering
        proxy_buffering off;
        proxy_cache off;
        
        # SSE (Server-Sent Events) support
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
```

So this is the core of the config that makes the service work properly -- everything else is to stop malicious requests and attacks. We forward requests to the `litellm_backend` upstream we defined earlier, which handles connection pooling and backpressure.

The headers block preserves information about the original request that would otherwise be lost when Nginx proxies to LiteLLM. Without these, LiteLLM would see every request as coming from `127.0.0.1` over HTTP -- it wouldn't know the client's real IP, the original domain, or whether HTTPS was used. This matters for logging, per-user rate limiting, and generating correct URLs in responses.

The timeouts block dictate how long to wait for LiteLLM to: accept the connection, receive data, and respond.

The streaming section is so that users can get that nice streaming response -- each token appears on the screen as it is generated. Otherwise you'd have seconds or minutes just staring at a blank screen.

> [!NOTE]
> You can see when developers have not implemented this in their chatbots, because you'll send a request and just see those three dots. In order to implement streaming you also need to correctly pass through the python generator to your frontend. In other words, streaming is a pain. The OpenAI Python client handles this automatically if you pass stream=True, so researchers don't need to worry about the implementation details — that's more of a concern for people building web frontends.

```conf
    # ---------------------------------------------------------------------------
    # Health Check Endpoint
    # ---------------------------------------------------------------------------
    location /health {
        proxy_pass http://litellm_backend/health;
        proxy_set_header Host $host;
        
        # Tighter timeout for health checks
        proxy_connect_timeout 5s;
        proxy_read_timeout 5s;
    }
}
```

This final section is just a health check connection for monitoring services. Technically, LiteLLM already has a health endpoint, but here we can tune things explicitly.

> [!NOTE]
> The `/health` endpoint is subject to the same auth check as everything else (via the security snippet). This means external monitoring tools will need a valid API key to hit it. If you need unauthenticated health checks for uptime monitoring, you'll need to add an exemption in the security snippet.

---

### Security Snippet

The security rules are defined in a separate file ([security.conf.template](../stacks/llm-service/security.conf.template)) which gets installed to `/etc/nginx/snippets/llm-security.conf`. This is included in the main server block via the `include` directive we saw above.

```conf
# Require Authorization header on all requests
if ($auth_valid = 0) {
    return 401;
}
```

This is where the `$auth_valid` variable from the `map` block gets used. Every request that doesn't have a properly formatted `Authorization` header is immediately rejected with a 401. This happens before any `location` block is evaluated, so there's no way to reach any endpoint without at least _looking_ like you have a valid key. The actual key validation still happens at the LiteLLM layer -- this just prevents the obvious junk from getting that far.

```conf
# Block docs and test endpoints
location ~ ^/(redoc|docs|openapi\.json|swagger|test) {
    return 404;
}

# Block admin UI
location /ui {
    return 404;
}
```

These block the LiteLLM documentation pages and admin interface. We return 404 rather than 403 -- there's no reason to confirm to an attacker that these paths exist but are forbidden. As far as they can tell, there's nothing there. The admin UI is only accessible via an SSH tunnel to the server.

```conf
# Block common attack vectors
location ~* (\.php|\.asp|\.aspx|\.jsp|\.cgi|\.env|\.git|\.sql|\.bak|\.swp) {
    return 444;
}

# Block WordPress probes
location ~* (wp-admin|wp-login|xmlrpc\.php) {
    return 444;
}
```

Here we block requests to common attack target files and WordPress probes. These are more about not populating our logs with bullshit -- every server on the internet gets bombarded with these. We return 444 (drop connection silently) rather than any HTTP response, which gives scanners nothing to work with and feeds into our fail2ban rules.

```conf
# Block config endpoint
location /config {
    return 404;
}

# Block health sub-endpoints (keep /health which requires auth)
location /health/liveliness {
    return 404;
}

location /health/readiness {
    return 404;
}
```

LiteLLM exposes several endpoints that leak configuration details or bypass the main health check. We block these individually. The main `/health` endpoint remains available (with auth) for monitoring, but the sub-endpoints that Kubernetes would typically use are hidden since we're not running in a Kubernetes environment.

So that's quite a lot of information!

---

### LiteLLM Configuration

Now let's look at the [LiteLLM configuration](../stacks/llm-service/litellm_config.yaml). Mercifully, this is shorter.

```yaml
model_list:
  - model_name: openai/gpt-oss-20b
    litellm_params:
      model: openai/openai/gpt-oss-20b
      api_base: http://vllm:8000/v1
      api_key: "none"
      stream: true
```

Perhaps unsurprisingly, this section defines which models we want to serve. We only have one: `gpt-oss-20b` from OpenAI. For the `litellm_params` we have to double up the `openai` because LiteLLM will strip the first one to group providers together. Using `vllm` as the hostname means this is resolved via Docker networking, so LiteLLM and vLLM should be on the same Docker network, which they are. vLLM is not exposed externally, so we don't need a key.

```yaml
general_settings:
  store_model_in_db: true
  ui_access_mode: "admin_only"
  block_robots: true
  disable_generic_signup: true
```
We'll touch on this later, but we attach a database to LiteLLM to save keys, users, and model configurations. We also restrict access to the UI to admin users only (even though are blocking it in Nginx anyway). `block_robots` prevents search engines indexing exposed pages. We also prevent random people from self-registering accounts.

> [!NOTE]
> You might have noticed a lot of redundancy in what we are doing. Things like preventing people from registering and accessing the UI at both the LiteLLM level and the Nginx level is cheap and easy to do. This is generally called [defence in depth](https://en.wikipedia.org/wiki/Defense_in_depth_(computing)).

```yaml
litellm_settings:
  drop_params: true
  set_verbose: false
```
The final section drops unsupported parameters instead of throwing an error and crashing the entire service. We also aren't interested in massive logs in production.


---

### The docker compose file
Let's briefly touch on the difference services in the [docker compose file](../stacks/llm-service/docker-compose.yml). Docker compose can seen frightening, but it's just a way to combine different docker services into one convenient file.

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: litellm-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d ${POSTGRES_DB} -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 5
```
This defines the PostgreSQL database that stores LiteLLM's state -- API keys, users, teams, and usage statistics. We use the Alpine-based image for a smaller footprint, persist data to a named volume so it survives container restarts, and configure a health check so LiteLLM won't start until the database is ready to accept connections.

```yaml
  vllm:
    image: vllm/vllm-openai:latest
    container_name: vllm-server
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    environment:
      - VLLM_MODEL=${VLLM_MODEL}
    command: >
      --model ${VLLM_MODEL}
      --gpu-memory-utilization ${VLLM_GPU_MEMORY_UTILIZATION}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 180s
```
This is the vLLM inference server -- the engine behind the whole thing. It reserves all available GPUs and exposes an OpenAI-compatible API on port 8000 — but only within the Docker network, so it's not accessible externally. The model and GPU memory utilisation are configured via environment variables. We have a healthcheck to ensure that LiteLLM doesn't start accepting requests until the model is loaded. We wait 180s (3 minutes) for the model to load.

```yaml
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: litellm-proxy
    restart: unless-stopped
    ports:
      - "127.0.0.1:${LITELLM_PORT}:4000"  # Make sure bound to localhost
    depends_on:
      db:
        condition: service_healthy
      vllm:
        condition: service_healthy
    environment:
      DATABASE_URL: "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY}
      NO_DOCS: "True"
      NO_REDOCS: "True"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml:ro
    command: ["--config", "/app/config.yaml"]

volumes:
  postgres_data:
```
Finally, this is the LiteLLM proxy that sits between Nginx and vLLM, handling authentication and request management. It connects to Postgres for state, routes inference requests to vLLM, and exposes its API only to localhost where Nginx can proxy to it. The `NO_DOCS` and `NO_REDOCS` environment variables disable the Swagger and ReDoc API documentation pages at `/` -- defence in depth.

### The launch script

The final stage is to check out the [llm service launch script](../scripts/llm-service.sh). Again, there is an [ansible equivalent](../ansible/playbooks/llm-service.yml). This script deploys the entire stack.

```bash
set -euo pipefail

# Determine script and stack directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if we're running from the scripts directory or the stack directory
if [[ "$(basename "$SCRIPT_DIR")" == "scripts" ]]; then
    # Running from repo root via ./scripts/llm-service.sh
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
    STACK_DIR="${REPO_ROOT}/stacks/llm-service"
else
    # Running directly from stack directory
    STACK_DIR="$SCRIPT_DIR"
fi
```

This part is similar to the setup -- we are making sure the script exits if something fails. We also figure out where it's being run from so it can find the stack directory. This lets you run it either from the repo root (`./scripts/llm-service.sh`) or directly from the stack directory.

```bash
# nginx
if ! command -v nginx &> /dev/null; then
    echo "Nginx not found. Installing..."
    sudo apt-get update && sudo apt-get install -y nginx
fi
```

Before anything else, we check that Nginx is installed. If not, we install it. This runs before the numbered steps since Nginx is a hard dependency for everything that follows.

```bash
# Check for .env file
if [ ! -f "${STACK_DIR}/.env" ]; then
    echo "ERROR: .env file not found at ${STACK_DIR}/.env"
    echo ""
    echo "Create it from the example:"
    echo "  cp ${STACK_DIR}/.env.example ${STACK_DIR}/.env"
    echo "  nano ${STACK_DIR}/.env"
    exit 1
fi
```

This checks that `.env` exists before doing anything. Failing early with a clear error is much better than getting halfway through and having `envsubst` silently produce a broken config.

```bash
# Load environment variables
export $(cat "${STACK_DIR}/.env" | grep -v '^#' | grep -v '^$' | xargs)

# Validate required variables
REQUIRED_VARS="POSTGRES_PASSWORD LITELLM_MASTER_KEY DOMAIN LITELLM_PORT"
for var in $REQUIRED_VARS; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var is not set in .env"
        exit 1
    fi
done
```

This loads your `.env` file into the shell environment (filtering out comments and blank lines), then checks that all required variables are actually set. If any are missing, the script exits with a clear error message rather than continuing and producing broken configs.

Now we get into the numbered deployment steps:

```bash
echo "[1/7] Generating Nginx configuration..."
envsubst '${DOMAIN} ${LITELLM_PORT}' < "${STACK_DIR}/nginx.conf.template" > "${STACK_DIR}/${DOMAIN}"
echo "      Generated: ${STACK_DIR}/${DOMAIN}"
```

This takes the Nginx template and substitutes the environment variables to produce the final config. The `envsubst` command replaces `${DOMAIN}` and `${LITELLM_PORT}` with their actual values, outputting a file named after your domain (e.g., `llm.science.ai.cam.ac.uk`).

```bash
echo "[2/7] Installing security snippet..."
sudo mkdir -p /etc/nginx/snippets
sudo cp "${STACK_DIR}/security.conf.template" /etc/nginx/snippets/llm-security.conf
```

This installs the [security snippet](../stacks/llm-service/security.conf.template) we walked through in the Nginx section. The main Nginx config references it via `include /etc/nginx/snippets/llm-security.conf`, so it needs to be in place before we test the config. We create the snippets directory if it doesn't already exist.

```bash
echo "[3/7] Installing Nginx configuration..."
sudo cp "${STACK_DIR}/${DOMAIN}" /etc/nginx/sites-available/
if [ ! -L "/etc/nginx/sites-enabled/${DOMAIN}" ]; then
    sudo ln -s "/etc/nginx/sites-available/${DOMAIN}" /etc/nginx/sites-enabled/
fi

# Remove default Nginx site if present
if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm /etc/nginx/sites-enabled/default
fi
```

This copies the generated config to Nginx's `sites-available` directory, then creates a symlink in `sites-enabled` if one doesn't already exist. Nginx only loads configs that are symlinked into `sites-enabled`, so this pattern lets you easily enable/disable sites without deleting the config file.

We also remove the default Nginx site if it's present. On a fresh Ubuntu install, Nginx ships with a default "Welcome to nginx" page. If we leave it enabled, it can conflict with our server block -- and more importantly, it responds to requests on port 80 for any hostname, which undermines our catch-all block that's supposed to drop those connections silently.

```bash
echo "[4/7] Testing Nginx configuration..."
sudo nginx -t

echo "[5/7] Reloading Nginx..."
sudo systemctl reload nginx
```

We validate the Nginx config with `nginx -t` (which catches syntax errors before you break anything), then reload Nginx to apply the changes without dropping existing connections. Because of `set -e` at the top, if the Nginx test fails, the script stops here and won't continue with a broken config.

```bash
echo "[6/7] Installing and configuring fail2ban..."
if ! command -v fail2ban-server &> /dev/null; then
    sudo apt-get update && sudo apt-get install -y fail2ban
fi

sudo cp "${STACK_DIR}/fail2ban-jail.local" /etc/fail2ban/jail.local
sudo cp "${STACK_DIR}/filters/nginx-llm-blocked.conf" /etc/fail2ban/filter.d/
sudo cp "${STACK_DIR}/filters/nginx-llm-auth.conf" /etc/fail2ban/filter.d/
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
```

This installs and configures [fail2ban](https://github.com/fail2ban/fail2ban) with two custom jails that monitor our Nginx access logs. The `nginx-llm-blocked` jail watches for repeated hits on attack vector paths (the ones returning 444) and bans the IP for 24 hours after 5 attempts. The `nginx-llm-auth` jail watches for repeated 401s (failed authentication) and bans for 1 hour after 10 attempts. The filter files define the regex patterns that match the relevant log lines.

```bash
echo "[7/7] Starting Docker stack..."
cd "${STACK_DIR}"
docker compose up -d
```

Finally, we start the Docker stack in detached mode. This pulls and starts PostgreSQL, vLLM, and LiteLLM. Because of the `depends_on` and health check configuration in the compose file, the services start in the correct order: PostgreSQL first, then vLLM, then LiteLLM once both dependencies are healthy.


## References

- [vLLM Documentation](https://docs.vllm.ai/)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [Nginx Documentation](https://nginx.org/en/docs/)