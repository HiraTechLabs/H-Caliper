# Trusted SSH host keys

Place an administrator-verified OpenSSH `known_hosts` file here as `known_hosts`.
The file is mounted read-only into the API container. Obtain host keys and
fingerprints from the Git provider's official documentation or another trusted
channel and verify fingerprints before adding them. Caliper enforces
`StrictHostKeyChecking=yes`; do not use `ssh-keyscan` output without independent
verification. The actual `known_hosts` file is ignored by Git.
