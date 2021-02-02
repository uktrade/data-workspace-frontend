resource "aws_key_pair" "shared" {
  key_name = "${var.prefix}"
  public_key = "${var.shared_keypair_public_key}"
}
