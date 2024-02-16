import React from "react";
export default function TeamsPrefixMessage({ team, bucketName }) {
  const relativePath = team.prefix.replace(/^teams/, '');
  return (
    <div className="govuk-inset-text">
      <p className="govuk-body">
        Files in the <code>{relativePath}</code> folder are not
        automatically accessible from your tools in the same way other files
        are. However, they can be manually accessed. For example, after
        uploading a file <code>{relativePath}file.csv</code>, you can
        create a Pandas DataFrame in a JupyterLab Python notebook by running the
        following code.
      </p>
      <code>
        <pre>
          {`import os
import pandas as pd 
import boto3 

client = boto3.client('s3', region_name='eu-west-2') 
response = client.get_object(
    Bucket='${bucketName}', 
    Key=os.environ['${team.env_var}'] + 'file.csv' ) 
df = pd.read_csv(response['Body'])
  `}
        </pre>
      </code>
      <p className="govuk-body govuk-!-margin-top-2">
        You can also create a tibble from this file in R by running the
        following code.
      </p>

      <code>
        <pre>{`library("aws.s3")
library("readr")
filename <- "file.csv"
conn = s3connection(paste(c(
    "s3://${bucketName}/",
    Sys.getenv("${team.env_var}"), filename), 
    collapse=""
))

tb = read_csv(conn)
close(conn)
        `}</pre>
      </code>
    </div>
  )
}
