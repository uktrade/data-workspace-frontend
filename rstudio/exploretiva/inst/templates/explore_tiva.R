# To run all of the code make sure the cursor is at the top
# of the file, and press CTRL+ALT+E. Some of the commands
# may take a few minutes to run

source('/etc/rstudio/connections/datasets_1.R')

# Schemas
dbListObjects(con)

# Tables in the oecd.tiva schema
dbListObjects(con, Id(schema = "oecd.tiva"))

# Fields in the L1 table in the oecd.tiva schema
dbListFields(con, Id(schema = "oecd.tiva", table= "L1"))

# Retrieve the first 5 rows with the highest ids
dbGetQuery(con, '
    SELECT *
    FROM "oecd.tiva"."L1"
    ORDER BY id DESC
    OFFSET 0
    LIMIT 5;
')

# Retrieve the next 5 rows with the highest ids
dbGetQuery(con, '
    SELECT *
    FROM "oecd.tiva"."L1"
    ORDER BY id DESC
    OFFSET 5
    LIMIT 5;
')

# The number of distinct source counties, and the total number of rows
dbGetQuery(con, '
    SELECT
      COUNT(*) AS total_rows,
      COUNT(DISTINCT(source_country)) AS number_countries 
    FROM "oecd.tiva"."L1"
')

# Only show rows where exporting country is the United Kingdom
dbGetQuery(con, '
    SELECT year, source_country, exporting_country, value_world  
    FROM "oecd.tiva"."L1"
    WHERE exporting_country = \'United Kingdom\' 
    LIMIT 5;
')

# Total export value, average export value, and number of rows for each source country
dbGetQuery(con, '
    SELECT
      source_country,
      SUM(value_world) AS total_value, 
      AVG(value_world) AS average_value,
      COUNT(value_world) AS number_rows
     FROM "oecd.tiva"."L1"
     WHERE exporting_country = \'United Kingdom\'
     GROUP BY source_country
     LIMIT 5;
')

# Query total export value, average export value and number of rows for each source country in the dataset 
# and order the results by total export value
dbGetQuery(con, '
    SELECT source_country, 
      SUM(value) as total_value, 
      AVG(value) as average_value,
      COUNT(value) as number_rows  
     FROM "oecd.tiva"."L1"
     WHERE exporting_country = \'United Kingdom\'
     GROUP BY source_country
     ORDER BY SUM(value) desc
     LIMIT 8;
')

# Get total export value from UK to each EU country in 2011
df <- dbGetQuery(con, '
    SELECT
      exporting_country,
      SUM(value) AS total_export
    FROM "oecd.tiva"."L1"
    WHERE
      year=\'2011\' 
      AND source_country=\'United Kingdom\' 
      AND exporting_country_eu=\'True\'
      AND exporting_country!=\'United Kingdom\' 
    GROUP BY
      exporting_country,
      source_country
    ORDER BY SUM(value) DESC
')
head(df)

# Set index as the exporting country column
rownames(df) <- df$exporting_country

# Remove the exporting country column from the df
df$exporting_country <- NULL

# Plot the results in a barplot
barplot(t(as.matrix(as.data.frame(df))), las=2) # make label text perpendicular to axis
