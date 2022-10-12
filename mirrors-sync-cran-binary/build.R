packages <- list('DBI', 'DT', 'RPostgres', 'aws.ec2metadata', 'aws.s3', 'bizdays', 'countrycode', 'flexdashboard', 'flextable', 'formattable', 'gert', 'ggraph', 'gifski', 'igraph', 'janitor', 'jsonlite', 'kableExtra', 'leaflet', 'lubridate', 'openxlsx', 'plotly', 'quantmod', 'readxl', 'rgdal', 'rmapshaper', 'rworldmap', 'scales', 'sf', 'shiny', 'stringr', 'topicmodels', 'text2vec', 'tidytext', 'tidyverse', 'tm', 'tmap', 'tmaptools', 'widyr', 'wordcloud2', 'zoo')
folder_name <- "cran-binary"
file_prefix <- "/src/contrib/"
bucket_name <- Sys.getenv("MIRRORS_BUCKET_NAME") 

# Generate binary packages
## Custom packages - the latest packages don't support R v3
writeLines("\n\n\n\n\nInstalling package XML\n\n\n\n\n")
install.packages("https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/src/contrib/bizdays_1.0.8.tar.gz", repos=NULL, type="source", INSTALL_opts = c("--build"))
install.packages("https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/src/contrib/XML_3.98-1.20.tar.gz", repos=NULL, type="source", INSTALL_opts = c("--build"))

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
