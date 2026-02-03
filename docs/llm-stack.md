## Testing
First we're going to spin up vLLM and see what happens.

```bash
sudo usermod -aG docker $USER
newgrp docker
```
This grants the user to run docker without having to use `sudo`.

Now
```bash
sudo docker run -d --gpus all \
    -p 8000:8000 \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --name vllm-server \
    vllm/vllm-openai:latest \
    --model openai/gpt-oss-20b
```

We need:
- docker-compose.yml
- litellm_config.yml
- nginx configuration

### docker-compose
```yml
services:
  # Database
  db:
    image: postgres:16-alpine
    container_name: litellm-db
    environment:
      POSTGRES_DB: litellm
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: your_secure_password # change to something non-stupid
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d litellm -U admin"]
      interval: 5s
      timeout: 5s
      retries: 5

  # vLLM
  vllm:
    image: vllm/vllm-openai:latest
    container_name: vllm-server
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1 # obviously N GPUs
              capabilities: [gpu]
    ports:
      - "127.0.0.1:8000:8000"
    command: --model openai/gpt-oss-20b --gpu-memory-utilization 0.95

  # LiteLLM
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: litellm-proxy
    ports:
      - "127.0.0.1:4000:4000"
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: "postgresql://admin:your_secure_password@db:5432/litellm"
      LITELLM_MASTER_KEY: sk-admin-1234
      NO_DOCS: True
      NO_REDOCS: True
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    command: ["--config", "/app/config.yaml", "--detailed_debug"]

volumes:
  postgres_data:
```

### LiteLLM
```yaml
model_list:
  - model_name: openai/gpt-oss-20b 
    litellm_params:
      model: openai/openai/gpt-oss-20b # I think litellm strips the first openai?
      api_base: http://vllm:8000/v1 # docker container name
      api_key: "none" 

general_settings:
  master_key: sk-admin-1234  # change to something non-stupid
  store_model_in_db: True
  ui_access_mode: "admin_only"
  block_robots: True
  disable_generic_signup: True
```

### Nginx

Install:
```
sudo apt install nginx -y
```

Check. First create a symlink from enabled to available.
- Single Source of Truth: If we edit the file in sites-available, the change is instantly reflected in sites-enabled because they are technically the same file. We don't have to keep two copies in sync.

- Quick "Kill Switch": If we want to take our site offline for maintenance, we don't have to delete our hard work. We just delete the "shortcut" (the symlink) from sites-enabled. The original config stays safe in sites-available, waiting to be re-enabled later.

```
sudo ln -s /etc/nginx/sites-available/llm.science.ai.cam.ac.uk /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

needs to go:
```bash
sudo nano /etc/nginx/sites-available/llm.science.ai.cam.ac.uk
```
```yaml
server {
    listen 80;
    server_name llm.antipodesintelligence.com;
    # BLOCK THE UI FROM THE WEB
    location /ui {
        return 403; # Returns "Forbidden" to anyone hitting this via the domain
    }
    location / {
        proxy_pass http://127.0.0.1:4000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

restart:
```
sudo systemctl restart nginx
```

Dashboard can only be accessed by secure tunnel:
```bash
ssh -i /path/to/your/private-key.pem -fN -L 4000:localhost:4000 user@server
```