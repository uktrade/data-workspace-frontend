library(stringr)
library(DBI)
getConn <- function(dsn) {
  user <- str_match(dsn, "user=([a-z0-9_]+)")[2]
  password <- str_match(dsn, "password=([a-zA-Z0-9_]+)")[2]
  port <- str_match(dsn, "port=(\\d+)")[2]
  dbname <- str_match(dsn, "dbname=([a-z0-9_\\-]+)")[2]
  host <- str_match(dsn, "host=([a-z0-9_\\-\\.]+)")[2]
  con <- dbConnect(RPostgres::Postgres(), user=user, password=password, host=host, port=port, dbname=dbname)
  return(con)
}
isDsn <- function(name) {
  return(startsWith(name, "DATABASE_DSN__"))
}
niceName <- function(name) {
  return(substring(name, 15))
}
env = Sys.getenv(names=TRUE)
dsns <- env[Vectorize(isDsn)(names(env))]
conn <- Vectorize(getConn)(unname(dsns))
names(conn) <- Vectorize(niceName)(names(dsns))
print(paste("You now have", as.character(length(conn)), "database connections:", sep=" "))
for (name in names(conn)) {
  var_name <- paste("conn", name, sep="_")
  assign(var_name, conn[[c(name)]])
  print(paste(" ", var_name, sep=""))
}
rm(conn,getConn,isDsn,niceName,env,dsns)
