#!/bin/bash

set -e

mkdir -p /etc/gitlab/

/usr/bin/aws s3 cp "s3://$BUCKET/sshd/ssh_host_ecdsa_key" /etc/gitlab/ssh_host_ecdsa_key
/usr/bin/aws s3 cp "s3://$BUCKET/sshd/ssh_host_ecdsa_key" /etc/gitlab/ssh_host_ecdsa_key.pub
/usr/bin/aws s3 cp "s3://$BUCKET/sshd/ssh_host_ed25519_key" /etc/gitlab/ssh_host_ed25519_key
/usr/bin/aws s3 cp "s3://$BUCKET/sshd/ssh_host_ed25519_key.pub" /etc/gitlab/ssh_host_ed25519_key.pub
/usr/bin/aws s3 cp "s3://$BUCKET/sshd/ssh_host_rsa_key" /etc/gitlab/ssh_host_rsa_key
/usr/bin/aws s3 cp "s3://$BUCKET/sshd/ssh_host_rsa_key.pub" /etc/gitlab/ssh_host_rsa_key.pub
/usr/bin/aws s3 cp "s3://$BUCKET/secrets/gitlab-secrets.json" /etc/gitlab/gitlab-secrets.json

chmod 600 /etc/gitlab/*_key
chmod 600 /etc/gitlab/gitlab-secrets.json

/assets/wrapper
