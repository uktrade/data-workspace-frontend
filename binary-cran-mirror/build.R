install.packages("aws.s3")
library("aws.s3")

packages = list("httpuv")

for(package in packages) {
  install.packages(package, INSTALL_opts=c('--build'))
}

file_names <- list.files(path = ".", pattern = "*.gz", full.names = TRUE, recursive = FALSE)
new_file_names <- sub("^(.*)_R_.*.tar.gz", "\\1.tar.gz", file_names)
file.rename(from = file_names, to = new_file_names)

tools::write_PACKAGES(dir = ".")

s3sync(bucket = "cran-binary-mirror", prefix = "src/contrib/", direction = "upload")