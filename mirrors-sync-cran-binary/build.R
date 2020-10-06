packages <- list("shiny", "aws.s3", "aws.ec2metadata", "ggraph", "igraph", "RPostgres", "text2vec", "tidytext", "tm", "topicmodels", "widyr", "wordcloud2", "tidyverse")
folder_name <- "cran-binary"
file_prefix <- "/src/contrib/"
bucket_name <- Sys.getenv("MIRRORS_BUCKET_NAME") 

# Generate binary packages
for (package in packages) {
  install.packages(package, INSTALL_opts = c("--build"))
}
file_names <- list.files(path = ".", pattern = "*.gz", full.names = TRUE, recursive = FALSE)
new_file_names <- sub("^(.*)_R_.*.tar.gz", "\\1.tar.gz", file_names)
file.rename(from = file_names, to = new_file_names)
# Remove ./ from beginning of file names
files_to_upload <- sub("^\\./(.*)", "\\1", new_file_names)

# Upload binary packages to S3
library("aws.s3")
library("aws.ec2metadata")
for (file_name in files_to_upload) {
  put_object(
    file = file.path(file_name),
    object = paste(folder_name, file_prefix, file_name, sep = ""),
    bucket = bucket_name,
    headers = c("x-amz-server-side-encryption" = "AES256")
  )
}

# Generate PACKAGE files
tools::write_PACKAGES(dir = ".")

# Upload PACKAGE files to S3
for (file_name in list("PACKAGES", "PACKAGES.gz", "PACKAGES.rds")) {
  put_object(
    file = file.path(file_name),
    object = paste(folder_name, file_prefix, file_name, sep = ""),
    bucket = bucket_name,
    headers = c("x-amz-server-side-encryption" = "AES256")
  )
}