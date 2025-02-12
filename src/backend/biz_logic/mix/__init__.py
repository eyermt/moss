"""
The Mix module is for anything related to extracting, joining, transforming, and loading data from one or more 
harvests or bottles and, specifically, providing RESTful CRUD (create, read, update, delete) operations relating to this
transfomed data, providing the interface with our persistance layer.

Included in the mix module will be "cocktail recipies," which correspond to commonly requested datasets / user queries.
Example recipes might include:

* n bottles of GitHub contributor data from harvest x, corresponding to the last n bottles of data collected 
* 1 bottle of GitHub base data from harvest x + 1 bottle of pypi data from harvest x
* The repositories in common between harvest x and harvest y, where x and y are both scrapes of university websites but at two different points in time
"""