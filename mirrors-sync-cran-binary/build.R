packages <- list('DBI', 'DT', 'RPostgres', 'aws.ec2metadata', 'aws.s3', 'bizdays', 'countrycode', 'flexdashboard', 'flextable', 'formattable', 'ggraph', 'gifski', 'igraph', 'janitor', 'jsonlite', 'kableExtra', 'leaflet', 'lubridate', 'openxlsx', 'plotly', 'quantmod', 'readxl', 'rgdal', 'rmapshaper', 'rworldmap', 'scales', 'sf', 'shiny', 'stringr', 'topicmodels', 'text2vec', 'tidytext', 'tidyverse', 'tm', 'tmap', 'tmaptools', 'widyr', 'wordcloud2', 'zoo', 'XML')
folder_name <- "cran-binary-rv4"
file_prefix <- "/src/contrib/"
bucket_name <- Sys.getenv("MIRRORS_BUCKET_NAME") 

## Standard packages
for (package in packages) {
  writeLines(sprintf("\n\n\n\n\nInstalling package %s\n\n\n\n\n", package))
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
