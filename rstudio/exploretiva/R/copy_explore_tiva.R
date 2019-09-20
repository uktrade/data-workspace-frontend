copy_explore_tiva <- function(path, ...) {
  dir.create(path, recursive=TRUE, showWarnings=FALSE)
  source <- system.file("templates", "explore_tiva.R", package="exploretiva")
  file.copy(source, path)
}
