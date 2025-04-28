# Deploying with Caddy on AWS EC2 (Direct Installation Method)

This guide explains how to set up Caddy as a reverse proxy on an AWS EC2 instance to serve your application using the direct binary installation method.

## Prerequisites

- An AWS EC2 instance running Amazon Linux
- An application running on port 8000
- A domain name pointed to your EC2 instance's IP address

## Installation Steps

### 1. Download and Install Caddy Binary

Download the Caddy binary directly and set it up:

```bash
# Download Caddy
sudo curl -o /usr/local/bin/caddy https://caddyserver.com/api/download?os=linux&arch=amd64

# Make it executable
sudo chmod +x /usr/local/bin/caddy
```

### 2. Create System Service

Set up Caddy as a system service:

```bash
# Create a system service for Caddy
sudo curl -s https://raw.githubusercontent.com/caddyserver/dist/master/init/caddy.service -o /etc/systemd/system/caddy.service

# Create user for Caddy
sudo useradd --system --home /var/lib/caddy --shell /usr/sbin/nologin caddy

# Create necessary directories
sudo mkdir -p /etc/caddy /var/lib/caddy /var/log/caddy

# Set permissions
sudo chown -R caddy:caddy /var/lib/caddy /var/log/caddy
```

### 3. Configure Caddy with Password Protection

First, copy the example Caddyfile and prepare for customization:

```bash
# Copy the example Caddyfile
cp Caddyfile.example /etc/caddy/Caddyfile
```

Now, generate a hashed password for basic authentication:

```bash
# Generate a hashed password
sudo caddy hash-password
# Enter your desired password when prompted
```

Edit the Caddyfile to use your username and the generated password hash:

```bash
# Replace placeholders with actual values
sudo sed -i 's/$USERNAME/your_username/' /etc/caddy/Caddyfile
sudo sed -i 's/$HASHED_PASSWORD/JDJhJDE0JHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4/' /etc/caddy/Caddyfile
# Replace the hash above with your actual generated hash
```

Alternatively, you can edit the file directly:

```bash
sudo nano /etc/caddy/Caddyfile
```

Ensure proper permissions:

```bash
# Set proper permissions
sudo chown caddy:caddy /etc/caddy/Caddyfile
sudo chmod 644 /etc/caddy/Caddyfile
```

Your completed Caddyfile should look similar to this (with your actual domain, username, and password hash):

```
notes.emilyflam.be {
    # Handle HTTP to HTTPS redirection
    @http {
        protocol http
    }
    redir @http https://{host}{uri} permanent

    # Apply basic auth and reverse proxy
    basicauth {
        admin $2a$14$xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    }
    reverse_proxy localhost:8000
}
```

### 4. Start and Enable Caddy

```bash
# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Start Caddy
sudo systemctl start caddy

# Enable Caddy to start automatically on system boot
sudo systemctl enable caddy
```

### 5. Verify Caddy is Running

Check the status of the Caddy service:

```bash
sudo systemctl status caddy
```

Verify Caddy is listening on the expected ports:

```bash
sudo ss -tulpn | grep caddy
```

### 6. Security Group Configuration

Ensure your EC2 security group allows incoming traffic on the following ports:
- Port 80 (HTTP)
- Port 443 (HTTPS)

### 7. Troubleshooting

If Caddy fails to start, check the logs:

```bash
sudo journalctl -xeu caddy.service
```

Common issues:
- Port conflicts with other web servers like Nginx or Apache
- DNS issues (domain not pointing to your server)
- Permission problems
- Application not running on the expected port
- Syntax errors in the Caddyfile

### 8. Updating Configuration

After making changes to your Caddyfile, reload Caddy:

```bash
sudo systemctl reload caddy
```

## Additional Resources

- [Caddy Documentation](https://caddyserver.com/docs/)
- [Caddy GitHub Repository](https://github.com/caddyserver/caddy)
- [Caddy Basic Auth Documentation](https://caddyserver.com/docs/caddyfile/directives/basicauth)