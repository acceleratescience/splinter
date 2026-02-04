# Getting Started

Here, we detail the initial setup stages. We make some basic assumptions:

1. You have a bare metal server
2. You have no other software installed
3. You have Ubuntu 22.04

We provide two methods of setup: **script** and **ansible**, with the prefered option being ansible.

## Ansible

The process is as follows:

1. Connect to your server (however you do this)
2. Clone this repo (this may require the installation of Git)
3. Generate security keys and deposit the public key on your server in `~/.ssh/authorized_keys`
4. Exit your server
5. Set your inventory.ini target
6. Run the `setup.yml` playbook
7. Run the `monitoring.yml` playbook

In the sections below, we will walk through this process in detail, assuming you have completed steps 1 and 2.

### Security Keys

Ansible connects to your server via SSH using key-based authentication. If you don't already have an SSH key pair, generate one on your local machine:

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

Accept the default location (`~/.ssh/id_ed25519`) or specify a custom path. You can optionally add a passphrase for additional security.

Next, copy your public key to the server. If you're still connected to the server, you can do this manually:

```bash
# On the server
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "your-public-key-content" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Alternatively, from your local machine:

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub ubuntu@<server-ip>
```

Verify the key works by disconnecting and reconnecting without a password:

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@<server-ip>
```

### Setting the Inventory Target

The inventory file tells Ansible which servers to manage. Copy the example file and edit it:

```bash
cd ansible
cp inventory.ini.example inventory.ini
```

Edit `inventory.ini` to add your server details:

```ini
[gpu_servers]
gpu-server ansible_host=<YOUR_SERVER_IP> ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_ed25519
```

Replace `<YOUR_SERVER_IP>` with your server's IP address. If you used a different SSH key path, update `ansible_ssh_private_key_file` accordingly.

Test the connection with:

```bash
ansible gpu_servers -m ping -i ./ansible/inventory.ini
```

The `-i` flag is required to specify the inventory file target location. If you navigate to the ansible folder, you won't need to specify this. You should see a successful pong response.

### Running the Setup Playbook

The setup playbook installs Docker, the NVIDIA Container Toolkit, and other base dependencies. Before running it, ensure you have the required Ansible collections installed on your local machine:

```bash
ansible-galaxy collection install community.docker
```

Then run the playbook:

```bash
ansible-playbook playbooks/setup.yml
```

This playbook will update system packages, install Docker CE, configure the NVIDIA Container Toolkit, and verify GPU access. The process typically takes a few minutes. At the end, you should see the output of `nvidia-smi` confirming your GPU is detected.

### Running the Monitoring Playbook

With the base setup complete, deploy the monitoring stack:

```bash
ansible-playbook playbooks/monitoring.yml
```

This deploys Prometheus, Grafana, node-exporter (for CPU/RAM metrics), and dcgm-exporter (for GPU metrics). The playbook performs health checks on all services before completing.

Once finished, you can access the monitoring interfaces:

| Service | URL | Notes |
|---------|-----|-------|
| Grafana | `http://<server-ip>:3000` | Default login: admin / admin |
| Prometheus | `http://<server-ip>:9090` | Query interface |
| Node Exporter | `http://<server-ip>:9100/metrics` | Raw system metrics |
| DCGM Exporter | `http://<server-ip>:9400/metrics` | Raw GPU metrics |

### Configuring Grafana

On first login to Grafana, you'll be prompted to change the admin password. After that, you need to add Prometheus as a data source:

1. Navigate to **Connections** → **Data sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Set the URL to `http://prometheus:9090` (using the Docker network hostname)
5. Click **Save & test**

To visualise your metrics, import pre-built dashboards:

1. Navigate to **Dashboards** → **Import**
2. Enter the dashboard ID and click **Load**
3. Select your Prometheus data source and click **Import**

Recommended dashboards:

| Dashboard | ID | Description |
|-----------|----|-------------|
| Node Exporter Full | 1860 | Comprehensive system metrics |
| NVIDIA DCGM Exporter | 12239 | GPU utilisation, memory, temperature, power |

### Troubleshooting

**Ansible can't connect to the server**

Check that your SSH key is correctly configured and that the inventory file has the correct IP, username, and key path. Test manually with `ssh -i <key-path> <user>@<ip>`.

**Docker commands fail with permission denied**

The setup playbook adds your user to the docker group, but this requires a new login session to take effect. Either reconnect to the server or run `newgrp docker`.

**DCGM exporter container fails to start**

Ensure the NVIDIA drivers are installed and working (`nvidia-smi` should show your GPU). The NVIDIA Container Toolkit must also be configured correctly. Re-run the setup playbook if needed.

**Grafana can't reach Prometheus**

When adding the data source, use `http://prometheus:9090` (the Docker network hostname), not `localhost`. The containers communicate over the Docker bridge network.


## Script

The security process remains the same, but now we just remain inside the server and run:

```bash
./scripts/setup.sh
```

and then

```bash
./scripts/monitoring
```

Follow the same instructions in the ansible section for Grafana.