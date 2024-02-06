resource "aws_efs_file_system" "notebooks" {
  creation_token = "${var.prefix}-notebooks"
  encrypted = true

  tags = {
    Name = "${var.prefix}-notebooks"
  }
}

resource "aws_efs_file_system_policy" "notebooks" {
  file_system_id = "${aws_efs_file_system.notebooks.id}"
  policy = "${data.aws_iam_policy_document.aws_efs_file_system_policy_notebooks.json}"
}

data "aws_iam_policy_document" "aws_efs_file_system_policy_notebooks" {
  # This may look like it does nothing, but it overrides the default policy that gives everyone
  # access to the whole of the filesystem with a no-access policy, so each user's individual role
  # can allow access to only their own access point
  #
  # You can't use a global "Deny" here, since the effect of a Deny action can't be undone by the
  # policies associated with individual roles.
  #
  # Even though the documentation suggests the resource policy on an EFS filesystem is similar to
  # the resource policy on an S3 bucket, the slightly scary difference is that in EFS, the default
  # is to allow everyone to connect to the filesystem, including as root. This means that it's very
  # easy to accidentally open up access to all notebooks, so if changing anything below, you should
  # verify that if a role is _not_ given permission to mount the filesystem, then it can't.
  #
  # The suspected cause for this difference is that IAM control on EFS was added after initial
  # launch, and AWS tried to make it backwards compatible
  #
  # Note also, we don't give permission to individuals in the file system policy, partially because
  # according to https://docs.aws.amazon.com/efs/latest/ug/iam-access-control-nfs-efs.html it's
  # quite inflexible to any changes:
  # > If you grant permission to an individual IAM user or role in a file system policy, don't
  # > delete or recreate that user or role while the policy is still in effect on the file system.
  # > If this happens, that user or role is effectively locked out from file system and will not
  # > be able to access it.
  statement {
    principals {
      type = "AWS"
      identifiers = ["*"]
    }

    actions = [""]

    resources = [
      "${aws_efs_file_system.notebooks.arn}",
    ]
  }
}

resource "aws_efs_mount_target" "notebooks" {
  file_system_id = "${aws_efs_file_system.notebooks.id}"
  subnet_id      = "${aws_subnet.private_with_egress.*.id[0]}"

  security_groups = ["${aws_security_group.efs_mount_target_notebooks.id}"]
}

resource "aws_vpc_endpoint" "efs_notebooks" {
  vpc_id            = "${aws_vpc.main.id}"
  service_name      = "com.amazonaws.${data.aws_region.aws_region.name}.elasticfilesystem"
  vpc_endpoint_type = "Interface"
  security_group_ids = ["${aws_security_group.efs_notebooks.id}"]

  policy = "${data.aws_iam_policy_document.aws_vpc_endpoint_s3_notebooks.json}"

  timeouts {}

}

data "aws_iam_policy_document" "aws_vpc_endpoint_efs" {
  statement {
    principals {
      type = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "elasticfilesystem:ClientMount",
      "elasticfilesystem:ClientWrite",
    ]

    resources = [
      "${aws_efs_file_system.notebooks.arn}",
    ]
  }
}
