// Create Datasets database if it doest exist
if (!db._databases().includes("Datasets")){db._createDatabase("Datasets")};

 // Create test collections if they don't already exist
db._useDatabase("Datasets");
if (!db._collections().includes("testcollection1")){db._create("testcollection1")};
if (!db._collections().includes("testcollection2")){db._create("testcollection2")};
